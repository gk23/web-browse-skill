#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cookie 持久化管理模块
"""

import os
import json
from typing import Optional

COOKIE_DIR = os.path.expanduser("~/.web_skill_cache/cookies")


def save_cookies(domain: str, cookies: list):
    """保存 cookies 供后续复用"""
    os.makedirs(COOKIE_DIR, exist_ok=True)
    cookie_file = os.path.join(COOKIE_DIR, f"{domain}.json")
    with open(cookie_file, 'w') as f:
        json.dump(cookies, f)
    print(f"[Cookie] 已保存到: {cookie_file}")


def load_cookies(domain: str) -> Optional[list]:
    """加载已保存的 cookies"""
    cookie_file = os.path.join(COOKIE_DIR, f"{domain}.json")
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None
