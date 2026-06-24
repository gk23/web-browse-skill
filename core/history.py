#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史记录管理模块

支持两级记录：
1. 域名级（domain_mode）：域名 → 最优模式，用于快速跳层
2. URL 级（url_layer）：URL pattern → 使用层，用于精确跳层

URL pattern 匹配规则：
- 精确匹配：完整 URL
- 路径模式：域名 + 路径前缀（如 github.com/login → interactive）
- 域名回退：仅域名匹配（如 github.com → headless）
"""

import os
import json
import time
import re
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse

HISTORY_FILE = os.path.expanduser("~/.web_skill_cache/site_modes.json")

# 层优先级（数字越小越优先）
LAYER_PRIORITY = {
    'web_fetch': 1,
    'headless': 2,
    'opencli': 3,
    'interactive': 4,
    'system_browser': 5,
    'failed': 99,
}


def get_domain(url: str) -> str:
    """从 URL 提取域名作为记录 key"""
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _normalize_url(url: str) -> str:
    """标准化 URL：去掉 fragment、trailing slash、排序 query params"""
    parsed = urlparse(url)
    # 去掉 fragment
    path = parsed.path.rstrip('/') or '/'
    # 排序 query
    if parsed.query:
        params = sorted(parsed.query.split('&'))
        query = '&'.join(params)
    else:
        query = ''
    return f"{parsed.scheme}://{parsed.netloc.lower()}{path}" + (f"?{query}" if query else "")


def _extract_path_pattern(url: str) -> str:
    """
    从 URL 提取路径模式（域名 + 路径前缀）
    
    例：
    - https://github.com/login → github.com/login
    - https://github.com/user/repo/issues/123 → github.com/user/repo/issues
    - https://example.com/ → example.com/
    """
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.rstrip('/') or '/'
    
    # 对于深层路径，截取前2-3级
    parts = [p for p in path.split('/') if p]
    if len(parts) > 3:
        # 保留前3级，后面的视为动态ID
        parts = parts[:3]
    elif len(parts) > 2:
        # 保留前2级
        parts = parts[:2]
    
    pattern_path = '/' + '/'.join(parts) if parts else '/'
    return f"{domain}{pattern_path}"


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
    """获取网站的历史模式记录（域名级）"""
    domain = get_domain(url)
    return load_history().get(domain)


def get_url_layer(url: str) -> Optional[Dict[str, Any]]:
    """
    查询 URL 对应的使用层记录
    
    查找优先级：
    1. 精确 URL 匹配
    2. 路径模式匹配（域名+路径前缀）
    3. 域名级匹配
    
    Returns:
        {"mode": "interactive", "reason": "...", "skip_layers": ["web_fetch", "headless", "opencli"]}
        或 None（无记录）
    """
    history = load_history()
    domain = get_domain(url)
    normalized = _normalize_url(url)
    path_pattern = _extract_path_pattern(url)
    
    # 1. 精确 URL 匹配
    url_records = history.get('_url_layers', {})
    if normalized in url_records:
        record = url_records[normalized]
        if record.get('mode') not in ('failed', None):
            skip_layers = _compute_skip_layers(record['mode'])
            return {**record, 'skip_layers': skip_layers, 'match_type': 'exact'}
    
    # 2. 路径模式匹配
    for pattern, record in url_records.items():
        # pattern 可能是 "github.com/login" 这种格式
        if pattern == domain:
            continue  # 跳过纯域名，留给第3步
        if normalized.startswith(pattern) or path_pattern == pattern:
            if record.get('mode') not in ('failed', None):
                skip_layers = _compute_skip_layers(record['mode'])
                return {**record, 'skip_layers': skip_layers, 'match_type': 'path_pattern'}
    
    # 3. 域名级匹配
    domain_record = history.get(domain)
    if domain_record and domain_record.get('mode') not in ('failed', None):
        skip_layers = _compute_skip_layers(domain_record['mode'])
        return {**domain_record, 'skip_layers': skip_layers, 'match_type': 'domain'}
    
    return None


def _compute_skip_layers(target_mode: str) -> List[str]:
    """
    根据目标模式计算需要跳过的层
    
    例：target_mode='interactive' → 跳过 ['web_fetch', 'opencli']
    注意：interactive 不跳过 headless，因为 headless+cookie 可能已足够
    """
    target_priority = LAYER_PRIORITY.get(target_mode, 99)
    skip = []
    for mode, priority in LAYER_PRIORITY.items():
        if priority < target_priority and mode != 'failed':
            # interactive 模式保留 headless 层（cookie 复用可能已足够）
            if target_mode == 'interactive' and mode == 'headless':
                continue
            skip.append(mode)
    return skip


def record_success(url: str, mode: str, reason: str):
    """
    记录成功获取（同时更新域名级和 URL 级记录）
    
    Args:
        url: 完整 URL
        mode: 使用的模式（web_fetch/headless/opencli/interactive/system_browser）
        reason: 成功原因
    """
    domain = get_domain(url)
    normalized = _normalize_url(url)
    path_pattern = _extract_path_pattern(url)
    now = time.strftime('%Y-%m-%dT%H:%M:%S')
    
    # 加载现有记录
    history = load_history()
    
    # ── 更新域名级记录 ──
    existing_domain = history.get(domain, {})
    domain_record = {
        'mode': mode,
        'reason': reason,
        'last_success': now,
        'success_count': existing_domain.get('success_count', 0) + 1
    }
    history[domain] = domain_record
    
    # ── 更新 URL 级记录 ──
    if '_url_layers' not in history:
        history['_url_layers'] = {}
    
    url_layers = history['_url_layers']
    
    # 精确 URL 记录
    existing_url = url_layers.get(normalized, {})
    url_layers[normalized] = {
        'mode': mode,
        'reason': reason,
        'last_success': now,
        'success_count': existing_url.get('success_count', 0) + 1,
        'domain': domain,
    }
    
    # 路径模式记录（仅当模式与域名级不同时才记录，避免冗余）
    if mode != existing_domain.get('mode'):
        existing_path = url_layers.get(path_pattern, {})
        url_layers[path_pattern] = {
            'mode': mode,
            'reason': reason,
            'last_success': now,
            'success_count': existing_path.get('success_count', 0) + 1,
            'domain': domain,
        }
    
    # 保存
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print(f"[记录] {domain} -> 模式: {mode}, 原因: {reason}")
    if mode != existing_domain.get('mode'):
        print(f"[记录] URL路径 {path_pattern} -> 模式: {mode} (与域名级不同，单独记录)")


def record_failure(url: str, reason: str):
    """记录失败获取"""
    domain = get_domain(url)
    normalized = _normalize_url(url)
    now = time.strftime('%Y-%m-%dT%H:%M:%S')
    
    history = load_history()
    
    # 域名级
    history[domain] = {
        'mode': 'failed',
        'reason': reason,
        'last_failure': now
    }
    
    # URL 级
    if '_url_layers' not in history:
        history['_url_layers'] = {}
    history['_url_layers'][normalized] = {
        'mode': 'failed',
        'reason': reason,
        'last_failure': now,
        'domain': domain,
    }
    
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print(f"[记录] {domain} -> 失败: {reason}")


def get_skip_layers_for_url(url: str) -> List[str]:
    """
    获取 URL 应跳过的层列表（用于智能调度器直接跳层）
    
    Returns:
        需要跳过的模式列表，如 ['web_fetch', 'headless', 'opencli']
        空列表表示无历史记录，应从第一层开始
    """
    record = get_url_layer(url)
    if record:
        return record.get('skip_layers', [])
    return []


def print_history():
    """打印所有历史记录（含 URL 级）"""
    history = load_history()
    
    if not history:
        print("暂无历史记录")
        return
    
    print("\n=== 域名级记录 ===")
    for key, record in history.items():
        if key == '_url_layers':
            continue
        mode = record.get('mode', 'N/A')
        reason = record.get('reason', 'N/A')
        count = record.get('success_count', 0)
        last = record.get('last_success', record.get('last_failure', 'N/A'))
        print(f"  {key}: 模式={mode}, 原因={reason}, 成功次数={count}, 最后={last}")
    
    url_layers = history.get('_url_layers', {})
    if url_layers:
        print("\n=== URL/路径级记录 ===")
        for pattern, record in url_layers.items():
            mode = record.get('mode', 'N/A')
            reason = record.get('reason', 'N/A')
            count = record.get('success_count', 0)
            last = record.get('last_success', record.get('last_failure', 'N/A'))
            domain = record.get('domain', '')
            print(f"  {pattern}: 模式={mode}, 原因={reason}, 成功次数={count}, 最后={last} (域名: {domain})")
