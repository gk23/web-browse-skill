#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史记录管理模块
"""

import os
import json
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

HISTORY_FILE = os.path.expanduser("~/.web_skill_cache/site_modes.json")


def get_domain(url: str) -> str:
    """从 URL 提取域名作为记录 key"""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def load_history() -> Dict[str, Any]:
    """加载历史记录"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_history(record: Dict[str, Any]):
    """保存历史记录"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    history = load_history()
    history.update(record)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_site_mode(url: str) -> Optional[Dict[str, Any]]:
    """获取网站的历史模式记录"""
    domain = get_domain(url)
    return load_history().get(domain)


def record_success(url: str, mode: str, reason: str):
    """记录成功获取"""
    domain = get_domain(url)
    history = load_history()
    existing = history.get(domain, {})
    record = {
        domain: {
            'mode': mode,
            'reason': reason,
            'last_success': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'success_count': existing.get('success_count', 0) + 1
        }
    }
    save_history(record)
    print(f"[记录] {domain} -> 模式: {mode}, 原因: {reason}")


def record_failure(url: str, reason: str):
    """记录失败获取"""
    domain = get_domain(url)
    record = {
        domain: {
            'mode': 'failed',
            'reason': reason,
            'last_failure': time.strftime('%Y-%m-%dT%H:%M:%S')
        }
    }
    save_history(record)
    print(f"[记录] {domain} -> 失败: {reason}")
