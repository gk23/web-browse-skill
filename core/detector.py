#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用页面内容检测和登录检测模块
"""

import re
from typing import Optional


def detect_login_required(html: str, driver=None) -> bool:
    """
    检测页面是否被登录弹窗/遮罩层阻挡
    
    策略：检测是否存在 Modal/Dialog + 登录表单的组合
    
    Args:
        html: 页面 HTML
        driver: 可选的 WebDriver 实例，用于检测元素可见性
    """
    # 验证码关键词（出现即判定需要人工）
    captcha_keywords = ['验证码', 'captcha', '滑块验证', '拼图验证', '请依次点击']
    for kw in captcha_keywords:
        if kw in html:
            return True
    
    # 策略1：检测常见的登录弹窗 DOM 结构
    modal_login_patterns = [
        r'class="[^"]*[Mm]odal[^"]*"[^>]*>.*?(?:密码|手机号|账号|登录方式)',
        r'class="[^"]*[Dd]ialog[^"]*"[^>]*>.*?(?:密码|手机号|账号|登录方式)',
        r'class="[^"]*login[^"]*[Ff]orm',
        r'class="[^"]*[Ss]ign[Ii]n[^"]*[Ff]orm',
    ]
    for pattern in modal_login_patterns:
        if re.search(pattern, html, re.DOTALL | re.IGNORECASE):
            return True
    
    # 策略2：检测遮罩层 + 登录表单的组合
    has_overlay = bool(re.search(
        r'class="[^"]*(?:overlay|backdrop|mask|遮罩)[^"]*"', 
        html, re.IGNORECASE
    ))
    has_login_form = bool(re.search(
        r'(?:type="password"|placeholder.*?(?:密码|手机号|验证码)|登录方式|密码登录|短信登录)', 
        html, re.IGNORECASE
    ))
    if has_overlay and has_login_form:
        return True
    
    # 策略3：通过 driver 检测可见的密码输入框
    if driver is not None:
        try:
            has_password_visible = driver.execute_script("""
                var inputs = document.querySelectorAll('input[type="password"]');
                for (var i = 0; i < inputs.length; i++) {
                    var style = window.getComputedStyle(inputs[i]);
                    if (style.display !== 'none' && style.visibility !== 'hidden' 
                        && inputs[i].offsetParent !== null) {
                        return true;
                    }
                }
                return false;
            """)
            if has_password_visible:
                return True
        except Exception:
            pass
    
    return False


def detect_qrcode_login(html: str) -> bool:
    """
    检测页面是否为二维码登录页
    
    场景：用户需要扫码登录（如微信、企业微信），而不是输入密码。
    二维码页面的特征与密码登录页完全不同，需要独立检测。
    
    判定策略：
    - canvas 元素（二维码通常用 canvas 渲染）
    - 二维码相关关键词
    - 同时排除已登录页面的特征（避免对内容页误判 ugly）
    
    Args:
        html: 页面 HTML
    
    Returns:
        True: 这是一个二维码登录页面
    """
    html_lower = html.lower()
    
    # ---- 1. 二维码关键词检测 ----
    qr_text_keywords = [
        '二维码', '扫码登录', '扫一扫', '扫码',
        'qrcode', 'qr-code', 'qr_code', 'scan.*qr',
    ]
    has_qr_text = False
    for kw in qr_text_keywords:
        if re.search(kw, html, re.IGNORECASE):
            has_qr_text = True
            break
    
    if not has_qr_text:
        return False
    
    # ---- 2. Canvas 元素检测（二维码渲染载体）----
    has_canvas = bool(re.search(r'<canvas[^>]*>', html_lower))
    
    # qrcode 相关 class/id
    has_qr_element = bool(re.search(
        r'(?:id|class)\s*=\s*["\'][^"\']*qrcode[^"\']*["\']',
        html, re.IGNORECASE
    ))
    
    # ---- 3. 排除已登录页面的特征 ----
    # 如果页面同时有丰富的文章/内容结构，则更可能是已登录的内容页
    # 而不是二维码页（避免对包含"扫码"等词的内容页误判）
    content_indicators = [
        '<article', '<main', 'class="content"', 'class="article"',
        'class="post"', 'class="feed"', 'class="timeline"',
    ]
    content_score = sum(1 for ind in content_indicators if ind.lower() in html_lower)
    
    # 如果有明确的内容结构标签（≥3），即使含二维码相关词也判定为内容页
    if content_score >= 3:
        return False
    
    # ---- 4. 综合判定 ----
    # 有二维码文本 + (有 canvas 或 qrcode 元素) → 二维码登录页
    if has_canvas or has_qr_element:
        return True
    
    # 仅有二维码文本但无 canvas → 可能是密码+扫码混合页
    # 检查是否同时有密码框（说明用户可以选择扫码或密码登录）
    has_password_input = bool(re.search(
        r'<input[^>]*type\s*=\s*["\']password["\']',
        html, re.IGNORECASE
    ))
    
    # 有二维码文本 + 无密码框 → 纯二维码登录页
    if not has_password_input:
        return True
    
    # 有二维码文本 + 有密码框 → 混合页，仍可走二维码路径
    return True


def has_core_content(html: str) -> bool:
    """
    检测 HTML 是否包含核心内容（通用版）
    
    Args:
        html: 页面 HTML 内容
    """
    if not html or len(html) < 200:
        return False
    
    # 移除 script/style 等标签后检查纯文本
    text_content = html
    for tag in ['script', 'style']:
        text_content = re.sub(
            f'<{tag}[^>]*>.*?</{tag}>', '', text_content,
            flags=re.DOTALL | re.IGNORECASE
        )
    
    clean_text = re.sub('<[^>]+>', '', text_content)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    # 纯文本长度 > 100 即认为有内容
    if len(clean_text) > 100:
        return True
    
    # 通用内容指标
    indicators = [
        '<article', '<main', '<div class="content"',
        '<h1', '<h2', '<h3', '<p>', '<p '
    ]
    
    html_lower = html.lower()
    content_score = sum(1 for ind in indicators if ind.lower() in html_lower)
    
    return content_score >= 2
