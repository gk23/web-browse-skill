#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统浏览器交互模块（第五层）

提供功能：
1. 打开 Brave 浏览器（与用户系统浏览器隔离）
2. 等待用户操作完成
3. 获取页面内容（通过 AppleScript / xclip / 文件标记）
4. 解析结构化数据

降级条件：Brave 未安装 / 超时 / 用户放弃
"""

import subprocess
import platform
import time
import os
import json
import re
from typing import Optional, Dict, Any


def _find_brave_path() -> Optional[str]:
    """跨平台查找 Brave 浏览器路径"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        paths = [
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        # 尝试通过 mdfind 查找
        try:
            result = subprocess.run(
                ["mdfind", "kMDItemCFBundleIdentifier == com.brave.Browser"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                app_path = result.stdout.strip().split("\n")[0]
                brave_bin = os.path.join(app_path, "Contents/MacOS/Brave Browser")
                if os.path.exists(brave_bin):
                    return brave_bin
        except Exception:
            pass
    
    elif system == "Windows":
        paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for p in paths:
            if os.path.exists(p):
                return p
    
    elif system == "Linux":
        paths = [
            "/usr/bin/brave-browser",
            "/usr/bin/brave",
            "/snap/bin/brave",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
    
    return None


def open_browser(url: str) -> bool:
    """
    打开 Brave 浏览器访问指定 URL
    
    使用独立的 Brave 实例，不与用户个人浏览器冲突。
    
    Returns:
        bool: 是否成功打开
    """
    system = platform.system()
    brave_path = _find_brave_path()
    
    try:
        if brave_path:
            subprocess.Popen([brave_path, url])
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "Brave Browser", url])
        elif system == "Windows":
            subprocess.Popen(["start", "brave", url], shell=True)
        elif system == "Linux":
            subprocess.Popen(["brave-browser", url])
        else:
            print(f"[System Browser] 不支持的操作系统: {system}")
            return False
        
        print(f"[System Browser] 已使用 Brave 打开: {url}")
        return True
        
    except FileNotFoundError:
        print("[System Browser] Brave 浏览器未找到，请安装: https://brave.com/download/")
        return False
    except Exception as e:
        print(f"[System Browser] 打开浏览器失败: {e}")
        return False


def _wait_with_file_marker(timeout: int, marker_file: str = ".web_browse_done") -> bool:
    """
    文件标记模式等待（IDE 环境）
    
    用户在浏览器操作完成后创建标记文件，脚本检测到后继续。
    """
    # 清除旧标记
    if os.path.exists(marker_file):
        try:
            os.remove(marker_file)
        except Exception:
            pass
    
    print(f"[System Browser] 等待标记文件: {marker_file}")
    print(f"[System Browser] 操作完成后请创建此文件: touch {marker_file}")
    
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(marker_file):
            try:
                os.remove(marker_file)
            except Exception:
                pass
            return True
        time.sleep(1)
    
    return False


def _wait_manual(timeout: int) -> bool:
    """
    手动确认模式等待
    
    在终端中等待用户按 Enter 确认。
    IDE 环境中 input() 可能不可用，降级到文件标记模式。
    """
    print("\n" + "=" * 60)
    print("请在浏览器中完成以下操作：")
    print("  1. 登录网站（如需要）")
    print("  2. 搜索或导航到目标页面")
    print("  3. 确认内容已加载")
    print("\n完成后请按 Enter 键继续...")
    print("=" * 60 + "\n")
    
    try:
        input()
        return True
    except EOFError:
        # IDE 环境，降级到文件标记
        print("[System Browser] 检测到 IDE 环境，切换到文件标记模式")
        return _wait_with_file_marker(timeout)


def wait_for_completion(timeout: int = 300, mode: str = "manual") -> bool:
    """
    等待用户完成操作
    
    Args:
        timeout: 最大等待时间（秒）
        mode: "manual"=手动确认, "auto"=自动检测（需扩展）
    
    Returns:
        bool: 是否成功
    """
    start = time.time()
    
    if mode == "auto":
        # TODO: 通过 WebSocket 或文件监听扩展发送的信号
        # 目前降级到 manual
        print("[System Browser] auto 模式暂未实现，使用 manual 模式")
        return _wait_manual(timeout)
    
    return _wait_manual(timeout)


def _get_content_via_applescript() -> Optional[str]:
    """
    通过 AppleScript 获取 Brave 浏览器当前页面内容（仅 macOS）
    
    Returns:
        页面 HTML 或 None
    """
    if platform.system() != "Darwin":
        return None
    
    try:
        # 尝试获取 Brave 的页面内容
        result = subprocess.run(
            ['osascript', '-e',
             'tell application "Brave Browser"\n'
             '    set pageContent to execute active tab of first window javascript '
             '"document.documentElement.outerHTML"\n'
             '    return pageContent\n'
             'end tell'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def _get_content_via_clipboard() -> Optional[str]:
    """
    通过剪贴板获取内容
    
    用户在浏览器中 Ctrl+A, Ctrl+C 后，脚本读取剪贴板。
    """
    system = platform.system()
    
    try:
        if system == "Darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        elif system == "Linux":
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                                    capture_output=True, text=True, timeout=5)
        elif system == "Windows":
            result = subprocess.run(["powershell", "-command", "Get-Clipboard"],
                                    capture_output=True, text=True, timeout=5)
        else:
            return None
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    
    return None


def extract_content(html: str, rules: Dict[str, str]) -> Dict[str, Any]:
    """
    根据 CSS 选择器规则提取结构化内容
    
    Args:
        html: 页面 HTML
        rules: CSS 选择器规则，如 {"title": ".note-title"}
    
    Returns:
        提取的内容字典
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[System Browser] 需要安装 beautifulsoup4: pip install bs4")
        return {"raw_html": html[:5000]}
    
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    
    for key, selector in rules.items():
        elements = soup.select(selector)
        if len(elements) == 1:
            result[key] = elements[0].get_text(strip=True)
        elif len(elements) > 1:
            result[key] = [el.get_text(strip=True) for el in elements]
        else:
            result[key] = None
    
    return result


def fetch_via_system_browser(
    url: str,
    keyword: Optional[str] = None,
    system_browser_mode: str = "manual",
    timeout: int = 300,
    extract_rules: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    使用系统浏览器获取页面内容（第五层）
    
    流程：
    1. 打开 Brave 浏览器访问 URL
    2. 等待用户完成操作（登录/搜索/导航）
    3. 通过 AppleScript/剪贴板获取页面内容
    4. 按 extract_rules 提取结构化数据（可选）
    
    Args:
        url: 目标 URL
        keyword: 搜索关键词（可选，会附加到 URL）
        system_browser_mode: "manual" 或 "auto"
        timeout: 超时时间
        extract_rules: CSS 选择器提取规则（可选）
    
    Returns:
        {"success": True, "content": ..., "mode_used": "system_browser", ...}
        或 None（失败）
    """
    print(f"\n[模式5] System Browser: {url}")
    print("=" * 60)
    
    # ── 构建最终 URL ──
    final_url = url
    if keyword:
        # 如果 URL 已有查询参数，用 & 连接；否则用 ?
        if "?" in url:
            final_url = f"{url}&keyword={keyword}"
        else:
            final_url = f"{url}?keyword={keyword}"
    
    # ── 打开浏览器 ──
    if not open_browser(final_url):
        print("[模式5] 无法打开浏览器，跳过")
        return None
    
    # ── 等待用户完成 ──
    print(f"[模式5] 等待用户操作（超时: {timeout}秒）")
    if not wait_for_completion(timeout, system_browser_mode):
        print("[模式5] 等待超时或用户放弃")
        return None
    
    # ── 获取内容 ──
    html = None
    
    # 方式1: AppleScript（仅 macOS + Brave）
    html = _get_content_via_applescript()
    
    # 方式2: 剪贴板
    if not html:
        print("[模式5] AppleScript 获取失败，请复制页面内容到剪贴板")
        print("[模式5] 在浏览器中: Ctrl+A (全选) → Ctrl+C (复制)")
        print("[模式5] 然后按 Enter...")
        try:
            input()
        except EOFError:
            time.sleep(3)
        html = _get_content_via_clipboard()
    
    if not html:
        print("[模式5] 无法获取页面内容")
        return None
    
    # ── 提取结构化数据 ──
    content = html
    if extract_rules:
        content = extract_content(html, extract_rules)
    
    # ── 提取标题 ──
    title = ""
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()
    
    print(f"[模式5] 成功获取内容 (长度: {len(html)})")
    
    return {
        "success": True,
        "content": content,
        "mode_used": "system_browser",
        "url": final_url,
        "title": title
    }
