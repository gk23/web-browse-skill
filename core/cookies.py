#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie 持久化管理模块

支持 Selenium（JSON 文件存储）和 Playwright 两种格式的 cookie 读写。
"""

import os
import json
from typing import Optional, List, Dict, Any

COOKIE_DIR = os.path.expanduser("~/.web_skill_cache/cookies")


def save_cookies(domain: str, cookies: list):
    """保存 cookies 供后续复用（Selenium 格式）"""
    os.makedirs(COOKIE_DIR, exist_ok=True)
    cookie_file = os.path.join(COOKIE_DIR, f"{domain}.json")
    with open(cookie_file, 'w') as f:
        json.dump(cookies, f)
    print(f"[Cookie] 已保存到: {cookie_file}")


def load_cookies(domain: str) -> Optional[list]:
    """加载已保存的 cookies（Selenium 格式）"""
    cookie_file = os.path.join(COOKIE_DIR, f"{domain}.json")
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def load_cookies_for_playwright(domain: str) -> List[Dict[str, Any]]:
    """
    加载已保存的 cookies，转换为 Playwright 兼容格式。

    Selenium 的 cookie 格式使用 'expiry' 字段（float 时间戳），
    Playwright 使用 'expires' 字段（Unix 秒级时间戳）。
    此函数自动做字段映射。

    Returns:
        Playwright 兼容的 cookie 列表，可直接传给 page.context.add_cookies()
    """
    selenium_cookies = load_cookies(domain)
    if not selenium_cookies:
        return []

    pw_cookies = []
    for c in selenium_cookies:
        pw = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        # Selenium: 'secure' (bool), Playwright: 同名
        if "secure" in c:
            pw["secure"] = c["secure"]
        # Selenium: 'httpOnly' (bool), Playwright: 同名
        if "httpOnly" in c:
            pw["httpOnly"] = c["httpOnly"]
        # Selenium: 'sameSite' (str: Lax/Strict/None), Playwright: 同名
        if "sameSite" in c:
            pw["sameSite"] = c["sameSite"].capitalize() if c["sameSite"].lower() in ("lax", "strict", "none") else "Lax"
        # Selenium: 'expiry' (float 时间戳), Playwright: 'expires' (int 秒级)
        if "expiry" in c:
            pw["expires"] = int(c["expiry"])

        pw_cookies.append(pw)

    return pw_cookies


def save_cookies_from_playwright(domain: str, pw_cookies: List[Dict[str, Any]]):
    """
    将 Playwright 格式的 cookies 保存为 Selenium 兼容格式。

    这样无论用 Selenium 还是 Playwright 登录，cookie 都能互通。
    """
    selenium_cookies = []
    for c in pw_cookies:
        sc = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        if "secure" in c:
            sc["secure"] = c["secure"]
        if "httpOnly" in c:
            sc["httpOnly"] = c["httpOnly"]
        if "sameSite" in c:
            sc["sameSite"] = c["sameSite"]
        # Playwright: 'expires' (int 秒级), Selenium: 'expiry' (float)
        if "expires" in c and c["expires"] and c["expires"] > 0:
            sc["expiry"] = float(c["expires"])

        selenium_cookies.append(sc)

    save_cookies(domain, selenium_cookies)
