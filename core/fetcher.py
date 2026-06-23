#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用网页获取模块 - 三层降级策略

调度逻辑：
1. 查历史记录 → 有则直接用
2. 按优先级 web_fetch → headless → interactive 依次尝试
3. 成功后记录网站+模式+原因
"""

import os
import sys
import re
import time
from typing import Optional, Dict, Any

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .history import (
    get_domain, load_history, get_site_mode,
    record_success, record_failure
)
from .cookies import save_cookies, load_cookies
from .detector import detect_login_required, has_core_content, detect_qrcode_login
from ..browser.brave_driver import create_driver

DEFAULT_TIMEOUT = 30


# ============================================================================
# 模式1: Web Fetch (静态请求)
# ============================================================================

def fetch_via_web(url: str, timeout: int = 15) -> Optional[str]:
    """静态 HTTP 请求获取"""
    print(f"\n[模式1] Web Fetch: {url}")
    
    try:
        import urllib.request
        import urllib.error
        
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                print(f"[模式1] HTTP 状态码: {response.status}")
                return None
            
            html = response.read().decode('utf-8', errors='ignore')
            
            if has_core_content(html):
                print("[模式1] 成功获取核心内容")
                return html
            else:
                print("[模式1] 未检测到核心内容（可能需 JS 渲染或登录）")
                return None
                
    except urllib.error.HTTPError as e:
        print(f"[模式1] HTTP 错误: {e.code}")
        return None
    except Exception as e:
        print(f"[模式1] 请求失败: {e}")
        return None


# ============================================================================
# 模式2: Headless Browser (无头浏览器)
# ============================================================================

def fetch_via_headless(url: str, timeout: int = 30) -> tuple:
    """
    无头浏览器获取
    
    Returns:
        (html, needs_login): HTML内容和是否需要登录的标志
    """
    print(f"\n[模式2] Headless Browser: {url}")
    
    driver = None
    try:
        driver = create_driver(headless=True)
        driver.get(url)
        
        # 等待页面加载
        print("[模式2] 等待页面加载...")
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # 额外等待 JS 渲染
        time.sleep(3)
        
        html = driver.page_source
        
        # 检测是否需要登录
        if detect_login_required(html):
            print("[模式2] 检测到登录/验证码要求，需切换到交互模式")
            return None, True
        
        if has_core_content(html):
            print("[模式2] 成功获取核心内容")
            return html, False
        else:
            print("[模式2] 未检测到核心内容")
            return None, False
            
    except TimeoutException:
        print("[模式2] 页面加载超时")
        return None, False
    except Exception as e:
        print(f"[模式2] 执行失败: {e}")
        return None, False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ============================================================================
# 模式2+: Headless + Cookie 复用
# ============================================================================

def fetch_via_headless_with_cookies(url: str, timeout: int = 30) -> tuple:
    """
    无头浏览器 + 复用已保存的 cookies
    
    Returns:
        (html, needs_login): HTML内容和是否需要登录的标志
    """
    domain = get_domain(url)
    cookies = load_cookies(domain)
    
    if not cookies:
        return None, False
    
    print(f"\n[模式2+] Headless + Cookie 复用: {url}")
    
    driver = None
    try:
        # 先访问域名设置 cookies
        driver = create_driver(headless=True)
        driver.get(f"https://{domain}")
        time.sleep(1)
        
        # 注入 cookies
        for cookie in cookies:
            try:
                cookie_copy = cookie.copy()
                cookie_copy.pop('sameSite', None)
                cookie_copy.pop('storeId', None)
                cookie_copy.pop('session', None)
                driver.add_cookie(cookie_copy)
            except Exception:
                pass
        
        print(f"[模式2+] 已注入 {len(cookies)} 个 cookies")
        
        # 刷新页面
        driver.get(url)
        
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)
        
        html = driver.page_source
        
        if detect_login_required(html):
            print("[模式2+] Cookie 已过期，仍需登录")
            return None, True
        
        if has_core_content(html):
            print("[模式2+] Cookie 复用成功，获取核心内容")
            return html, False
        else:
            print("[模式2+] Cookie 复用后仍未获取到核心内容")
            return None, False
            
    except Exception as e:
        print(f"[模式2+] 执行失败: {e}")
        return None, False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ============================================================================
# 模式3: Interactive (人工交互)
# ============================================================================

def _inject_banner(driver, url: str, timeout: int, is_qrcode: bool = False):
    """注入登录提示横幅，包含「✅ 完成登录」和「❌ 未完成」双按钮"""
    if is_qrcode:
        title_text = "请先登录 - 扫码登录"
        hint_text = "扫码 / 密码 / 手机登录均可"
        icon_text = "🔐"
    else:
        title_text = "需要登录 / 验证码验证"
        hint_text = "请在页面中完成登录或验证码验证"
        icon_text = "🔐"

    banner_js = f'''
    (function() {{
        var old = document.getElementById('__wb_login_banner__');
        if (old) old.remove();

        var banner = document.createElement('div');
        banner.id = '__wb_login_banner__';
        banner.innerHTML =
            '<div style="display:flex;align-items:center;justify-content:center;gap:14px;padding:8px 20px;font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;flex-wrap:wrap;">' +
                '<span style="font-size:18px;">{icon_text}</span>' +
                '<div style="text-align:center;">' +
                    '<div style="font-weight:bold;font-size:13px;color:#333;">{title_text}</div>' +
                    '<div style="font-size:11px;color:#888;">{hint_text}</div>' +
                '</div>' +
                '<div style="display:flex;gap:8px;">' +
                    '<button id="__wb_btn_done__" style="padding:5px 16px;border:none;border-radius:6px;font-size:12px;font-weight:bold;cursor:pointer;background:#07c160;color:#fff;box-shadow:0 2px 6px rgba(7,193,96,0.3);">✅ 完成登录</button>' +
                    '<button id="__wb_btn_fail__" style="padding:5px 12px;border:1px solid #ddd;border-radius:6px;font-size:12px;cursor:pointer;background:#fff;color:#666;">❌ 未完成</button>' +
                '</div>' +
                '<span id="__wb_countdown__" style="font-size:12px;color:#e74c3c;font-weight:bold;font-variant-numeric:tabular-nums;min-width:90px;text-align:center;"></span>' +
            '</div>';
        banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;background:linear-gradient(135deg,#fffbeb,#fff7cd);border-bottom:2px solid #f59e0b;box-shadow:0 2px 12px rgba(0,0,0,0.08);';

        document.body.insertBefore(banner, document.body.firstChild);

        // 按钮状态标志（Python 端检测）
        window.__wb_login_done__ = false;
        window.__wb_login_failed__ = false;

        document.getElementById('__wb_btn_done__').addEventListener('click', function() {{
            window.__wb_login_done__ = true;
            window.__wb_login_failed__ = false;
            this.style.background = '#06b050';
            this.textContent = '✅ 已确认';
            document.getElementById('__wb_btn_fail__').style.opacity = '0.5';
        }});

        document.getElementById('__wb_btn_fail__').addEventListener('click', function() {{
            window.__wb_login_failed__ = true;
            window.__wb_login_done__ = false;
            this.style.background = '#fef2f2';
            this.style.borderColor = '#fca5a5';
            this.textContent = '❌ 已放弃';
            document.getElementById('__wb_btn_done__').style.opacity = '0.5';
        }});

        // 倒计时
        var remaining = {timeout};
        var countdownEl = document.getElementById('__wb_countdown__');
        var timer = setInterval(function() {{
            remaining--;
            if (remaining <= 0) {{
                clearInterval(timer);
                if (countdownEl) countdownEl.textContent = '⏰';
                return;
            }}
            var min = Math.floor(remaining / 60);
            var sec = remaining % 60;
            var timeStr = min > 0 ? min + '分' + sec + '秒' : sec + '秒';
            if (countdownEl) {{
                countdownEl.textContent = '⏱ ' + timeStr;
                countdownEl.style.color = remaining < 30 ? '#e74c3c' : remaining < 60 ? '#f39c12' : '#666';
            }}
        }}, 1000);
    }})();
    '''
    try:
        driver.execute_script(banner_js)
    except Exception as e:
        print(f"[模式3] 注入横幅失败: {e}")


def _wait_with_countdown(driver, url: str, timeout: int = 120, is_qrcode: bool = False) -> bool:
    """
    等待用户操作：按钮点击（主）+ 自动检测（辅）

    判定优先级：
    1. 用户点击 ✅ 完成登录 → 立即返回 True
    2. 用户点击 ❌ 未完成 → 返回 False
    3. 自动检测到登录完成 → 返回 True
    4. 超时 → 返回 True（降级获取当前页面）

    Returns:
        True:  登录完成或超时（继续获取内容）
        False: 用户主动放弃
    """
    start = time.time()
    last_print = 0
    initial_url = driver.current_url
    initial_content_len = 0

    if is_qrcode:
        try:
            initial_content_len = len(driver.page_source)
        except Exception:
            pass

    print(f"\n[模式3] 等待用户操作（超时: {timeout}秒）")
    print(f"  方式：登录后点击页面顶部横幅 → ✅ 完成登录")
    print(f"       未登录 / 不想登录 → ❌ 未完成")
    print("=" * 60)

    while True:
        elapsed = time.time() - start
        remaining = timeout - int(elapsed)

        if remaining <= 0:
            print("\n⏰ 等待超时！将获取当前页面内容。")
            return True

        # ── 1. 按钮状态检测（最高优先级）──
        try:
            done = driver.execute_script("return window.__wb_login_done__ || false")
            failed = driver.execute_script("return window.__wb_login_failed__ || false")

            if done:
                print(f"\n✅ 用户点击「完成登录」！({int(elapsed)}秒)")
                time.sleep(1)
                try:
                    driver.execute_script("""
                        var b = document.getElementById('__wb_login_banner__');
                        if (b) {
                            b.style.background = 'linear-gradient(135deg,#ecfdf5,#d1fae5)';
                            b.style.borderColor = '#10b981';
                            b.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 20px;font-family:system-ui;">' +
                                '<span style="font-size:18px;">✅</span>' +
                                '<div style="font-weight:bold;font-size:13px;color:#065f46;">登录已确认，正在提取内容...</div></div>';
                        }
                    """)
                except Exception:
                    pass
                return True

            if failed:
                print(f"\n❌ 用户点击「未完成」({int(elapsed)}秒)")
                try:
                    driver.execute_script("""
                        var b = document.getElementById('__wb_login_banner__');
                        if (b) {
                            b.style.background = 'linear-gradient(135deg,#fef2f2,#fee2e2)';
                            b.style.borderColor = '#ef4444';
                            b.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 20px;font-family:system-ui;">' +
                                '<span style="font-size:18px;">❌</span>' +
                                '<div style="font-weight:bold;font-size:13px;color:#991b1b;">登录未完成</div>' +
                                '<button onclick="location.reload()" style="padding:5px 12px;border:none;border-radius:6px;font-size:11px;cursor:pointer;background:#ef4444;color:#fff;">🔄 重试</button></div>';
                        }
                    """)
                except Exception:
                    pass
                return False
        except Exception:
            pass

        # ── 2. 自动检测（辅助）──
        try:
            html = driver.page_source
            current_url = driver.current_url
            content_found = has_core_content(html)
            login_still = detect_login_required(html, driver) or detect_qrcode_login(html)
            url_changed = (current_url != initial_url)
            content_grown = (len(html) > max(initial_content_len, 1) * 1.5)

            if not login_still and content_found and (url_changed or content_grown):
                print(f"\n🎉 自动检测到登录成功！({int(elapsed)}秒)")
                try:
                    driver.execute_script("""
                        var b = document.getElementById('__wb_login_banner__');
                        if (b) {
                            b.style.background = 'linear-gradient(135deg,#ecfdf5,#d1fae5)';
                            b.style.borderColor = '#10b981';
                            b.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;gap:12px;padding:8px 20px;font-family:system-ui;">' +
                                '<span style="font-size:18px;">🎉</span>' +
                                '<div style="font-weight:bold;font-size:13px;color:#065f46;">自动检测到登录成功！正在提取内容...</div></div>';
                        }
                    """)
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # ── 3. 每 10 秒打印状态 ──
        if int(elapsed) > 0 and int(elapsed) - last_print >= 10:
            last_print = int(elapsed)
            m = remaining // 60
            s = remaining % 60
            ts = f"{m}分{s}秒" if m > 0 else f"{s}秒"
            try:
                ls = "是" if login_still else "否"
            except Exception:
                ls = "?"
            try:
                uc = "是" if url_changed else "否"
            except Exception:
                uc = "?"
            print(f"  ⏱ 剩余 {ts} | 登录元素:{ls} | URL变:{uc}")

        time.sleep(1.5)


def fetch_via_interactive(url: str, timeout: int = 120) -> Optional[str]:
    """
    人工交互模式：打开有头浏览器，等待用户完成登录/验证码
    
    流程：
    1. 启动有头 Brave 浏览器
    2. 打开目标 URL（优先加载已保存的 cookies）
    3. 检测登录类型（二维码/密码），注入对应横幅
    4. 终端显示倒计时，等待用户操作
    5. 获取页面内容 + 保存 cookies
    6. 关闭浏览器
    """
    print(f"\n[模式3] Interactive Mode: {url}")
    print("=" * 60)
    
    driver = None
    try:
        driver = create_driver(headless=False)
        
        # 先访问域名首页以加载 cookies
        domain = get_domain(url)
        cookies = load_cookies(domain)
        if cookies:
            driver.get(f"https://{domain}")
            time.sleep(1)
            for cookie in cookies:
                try:
                    cookie_copy = cookie.copy()
                    cookie_copy.pop('sameSite', None)
                    cookie_copy.pop('storeId', None)
                    cookie_copy.pop('session', None)
                    driver.add_cookie(cookie_copy)
                except Exception:
                    pass
            print(f"[模式3] 已加载 {len(cookies)} 个 cookies")
            driver.get(url)
        else:
            driver.get(url)
        
        time.sleep(2)
        
        # ── 检测登录类型 ──
        initial_html = driver.page_source
        is_qrcode = detect_qrcode_login(initial_html)
        
        if is_qrcode:
            print(f"[模式3] 检测到「二维码登录」页面")
        else:
            print(f"[模式3] 检测到「密码/验证码登录」页面")
        
        print(f"[模式3] 等待时限: {timeout // 60}分{timeout % 60}秒")
        print("")
        
        if is_qrcode:
            print("📱 二维码/扫码登录模式：")
            print("  在 Brave 浏览器中完成登录（扫码/密码/手机均可）")
            print("  登录成功后 → 点击页面顶部黄色横幅中的「✅ 完成登录」")
            print("  无法登录 / 不想登录 → 点击「❌ 未完成」")
        else:
            print("🔐 密码/验证码登录模式：")
            print("  在 Brave 浏览器中完成登录或验证码验证")
            print("  登录成功后 → 点击页面顶部黄色横幅中的「✅ 完成登录」")
            print("  无法登录 / 不想登录 → 点击「❌ 未完成」")
        print("  系统也会自动检测登录状态作为辅助判断")
        print("=" * 60)

        # 注入登录提示横幅（根据类型显示不同文案）
        _inject_banner(driver, url, timeout, is_qrcode=is_qrcode)
        print("\n浏览器已打开，页面顶部已显示登录提示横幅")

        # 带倒计时的等待（按钮驱动 + 自动检测辅助）
        success = _wait_with_countdown(driver, url, timeout, is_qrcode=is_qrcode)

        # 如果用户主动放弃
        if not success:
            print("[模式3] 用户放弃登录")
            return None

        # 等待页面稳定
        time.sleep(2)

        # 移除横幅，获取纯净 HTML
        try:
            driver.execute_script("""
                var b = document.getElementById('__wb_login_banner__');
                if (b) b.remove();
            """)
        except Exception:
            pass
        
        html = driver.page_source
        
        # 诊断信息
        content_found = has_core_content(html)
        
        text_for_diag = html
        for tag in ['script', 'style']:
            text_for_diag = re.sub(
                f'<{tag}[^>]*>.*?</{tag}>', '', text_for_diag,
                flags=re.DOTALL | re.IGNORECASE
            )
        clean_for_diag = re.sub('<[^>]+>', '', text_for_diag)
        clean_for_diag = re.sub(r'\s+', ' ', clean_for_diag).strip()
        text_len = len(clean_for_diag)
        
        print(f"[模式3] 诊断: 核心内容={'是' if content_found else '否'}, 纯文本长度={text_len}, HTML长度={len(html)}")
        
        if content_found:
            print("[模式3] 成功获取核心内容")
            
            # 保存 cookies
            try:
                cookies = driver.get_cookies()
                save_cookies(domain, cookies)
                print(f"[模式3] 已保存 {len(cookies)} 个 cookies 到缓存")
            except Exception as e:
                print(f"[模式3] 保存 cookies 失败: {e}")
            
            return html
        else:
            # 宽容判断：如果页面有足够文本，也认为成功
            if text_len > 2000:
                print(f"[模式3] 页面文本充足({text_len}字符)，视为获取成功")
                
                try:
                    cookies = driver.get_cookies()
                    save_cookies(domain, cookies)
                    print(f"[模式3] 已保存 {len(cookies)} 个 cookies 到缓存")
                except Exception as e:
                    print(f"[模式3] 保存 cookies 失败: {e}")
                
                return html
            
            print(f"[模式3] 未检测到核心内容（纯文本仅{text_len}字符）")
            return None
            
    except Exception as e:
        print(f"[模式3] 执行失败: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ============================================================================
# 格式转换
# ============================================================================

def html_to_text(html: str) -> str:
    """将 HTML 转换为纯文本"""
    # 移除 script/style
    text = html
    for tag in ['script', 'style']:
        text = re.sub(
            f'<{tag}[^>]*>.*?</{tag}>', '', text,
            flags=re.DOTALL | re.IGNORECASE
        )
    # 移除所有标签
    text = re.sub('<[^>]+>', '', text)
    # 合并空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def html_to_markdown(html: str) -> str:
    """
    将 HTML 转换为 Markdown（简化版）
    
    注意：完整版需要引入 readability-lxml 和 markdownify
    这里提供基础实现，如需更好效果可安装：
    pip install readability-lxml markdownify
    """
    try:
        from readability import Document
        from markdownify import markdownify as md
        
        doc = Document(html)
        return md(doc.summary())
    except ImportError:
        # 降级为纯文本
        print("[提示] 未安装 readability-lxml / markdownify，降级为纯文本输出")
        print("[提示] 安装命令: pip install readability-lxml markdownify")
        return html_to_text(html)


def convert_format(html: str, output_format: str) -> str:
    """根据输出格式转换 HTML"""
    if output_format == 'html':
        return html
    elif output_format == 'markdown':
        return html_to_markdown(html)
    elif output_format == 'text':
        return html_to_text(html)
    else:
        return html


# ============================================================================
# 智能调度器
# ============================================================================

def smart_fetch(
    url: str,
    mode: str = "auto",
    output_format: str = "html",
    timeout: int = 30
) -> Dict[str, Any]:
    """
    智能获取网页内容
    
    调度流程：
    1. 查历史记录 → 有则直接用对应模式
    2. web_fetch → headless → headless+cookies → interactive
    3. 成功后记录
    
    Args:
        url: 目标 URL
        mode: 获取模式 ('auto', 'web_fetch', 'headless', 'interactive')
        output_format: 输出格式 ('html', 'markdown', 'text')
        timeout: 超时时间（秒）
    
    Returns:
        {
            "success": bool,
            "content": str,
            "mode_used": str,
            "url": str,
            "title": str
        }
    """
    print(f"\n{'='*60}")
    print(f"智能获取: {url}")
    print(f"模式: {mode}, 输出格式: {output_format}")
    print(f"{'='*60}")
    
    domain = get_domain(url)
    html = None
    mode_used = None
    
    # ---- 1. 查询历史记录（仅在 auto 模式下）----
    if mode == 'auto':
        record = get_site_mode(url)
        if record and record.get('mode') not in ('failed', None):
            hist_mode = record['mode']
            print(f"[历史] {domain} -> 模式: {hist_mode}, 原因: {record.get('reason')}")
            
            if hist_mode == 'web_fetch':
                html = fetch_via_web(url, timeout=min(timeout, 15))
                if html:
                    mode_used = 'web_fetch'
            elif hist_mode == 'headless':
                html, _ = fetch_via_headless_with_cookies(url, timeout=timeout)
                if html:
                    mode_used = 'headless'
                else:
                    html, _ = fetch_via_headless(url, timeout=timeout)
                    if html:
                        mode_used = 'headless'
            elif hist_mode == 'interactive':
                html = fetch_via_interactive(url, timeout=timeout)
                if html:
                    mode_used = 'interactive'
            
            if not html:
                print("[历史] 历史模式失败，重新尝试...")
    
    # ---- 2. 按优先级尝试 ----
    if not html:
        modes_to_try = []
        if mode == 'auto':
            modes_to_try = ['web_fetch', 'headless', 'interactive']
        else:
            modes_to_try = [mode]
        
        for try_mode in modes_to_try:
            if try_mode == 'web_fetch':
                html = fetch_via_web(url, timeout=min(timeout, 15))
                if html and has_core_content(html):
                    mode_used = 'web_fetch'
                    record_success(url, 'web_fetch', "静态页面，无需JS渲染")
                    break
            
            elif try_mode == 'headless':
                # 先尝试 cookie 复用
                html, needs_login = fetch_via_headless_with_cookies(url, timeout=timeout)
                if html and has_core_content(html):
                    mode_used = 'headless'
                    record_success(url, 'headless', "Cookie复用+JS渲染")
                    break
                
                # 纯 headless
                html, needs_login = fetch_via_headless(url, timeout=timeout)
                if html and has_core_content(html):
                    mode_used = 'headless'
                    record_success(url, 'headless', "SPA应用，需JS渲染")
                    break
                
                # 如果检测到需要登录，且 interactive 在尝试列表中
                if needs_login and 'interactive' in modes_to_try:
                    print("[调度] 检测到登录需求，跳转到交互模式...")
                    html = fetch_via_interactive(url, timeout=timeout)
                    if html and has_core_content(html):
                        mode_used = 'interactive'
                        record_success(url, 'interactive', "需要登录或验证码验证")
                        break
            
            elif try_mode == 'interactive':
                html = fetch_via_interactive(url, timeout=timeout)
                if html and has_core_content(html):
                    mode_used = 'interactive'
                    record_success(url, 'interactive', "需要登录或验证码验证")
                    break
    
    # ---- 3. 构建返回结果 ----
    if html:
        # 提取标题
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else ""
        
        # 转换格式
        content = convert_format(html, output_format)
        
        print(f"\n成功获取内容，长度: {len(content)} 字符")
        
        return {
            "success": True,
            "content": content,
            "mode_used": mode_used or mode,
            "url": url,
            "title": title
        }
    
    # ---- 4. 全部失败 ----
    record_failure(url, "所有模式均无法获取核心内容")
    print(f"\n无法获取: {url}")
    
    return {
        "success": False,
        "content": "",
        "mode_used": "failed",
        "url": url,
        "title": ""
    }
