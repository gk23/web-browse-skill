#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
opencli 适配器模块（第三层）

提供功能：
1. 检测 opencli 是否可用
2. 根据域名映射到 opencli 站点名
3. 调用 opencli 命令获取结构化数据
4. 解析 opencli 输出为统一格式

降级条件：opencli 未安装 / Browser Bridge 未连接 / 站点不支持 / 命令执行失败
"""

import subprocess
import json
import shutil
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs


# 域名到 opencli 站点名映射
DOMAIN_SITE_MAP = {
    # 中文社交
    "xiaohongshu.com": "xiaohongshu",
    "www.xiaohongshu.com": "xiaohongshu",
    "rednote.com": "xiaohongshu",
    "weibo.com": "weibo",
    "www.weibo.com": "weibo",
    "zhihu.com": "zhihu",
    "www.zhihu.com": "zhihu",
    "douban.com": "douban",
    "www.douban.com": "douban",
    "jike.com": "jike",
    "v2ex.com": "v2ex",
    "www.v2ex.com": "v2ex",
    "tieba.baidu.com": "tieba",
    # 中文视频
    "bilibili.com": "bilibili",
    "www.bilibili.com": "bilibili",
    "douyin.com": "douyin",
    "www.douyin.com": "douyin",
    # 中文资讯
    "36kr.com": "36kr",
    "www.36kr.com": "36kr",
    "xueqiu.com": "xueqiu",
    "www.xueqiu.com": "xueqiu",
    "smzdm.com": "smzdm",
    "www.smzdm.com": "smzdm",
    "zhihu.com": "zhihu",
    # 国际社交
    "twitter.com": "twitter",
    "x.com": "twitter",
    "reddit.com": "reddit",
    "www.reddit.com": "reddit",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "bsky.app": "bluesky",
    # 国际视频
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    # 国际资讯
    "news.ycombinator.com": "hackernews",
    "producthunt.com": "producthunt",
    "medium.com": "medium",
    "bbc.com": "bbc",
    "www.bbc.com": "bbc",
    "bloomberg.com": "bloomberg",
    "reuters.com": "reuters",
    # 开发者
    "github.com": "gh",
    "stackoverflow.com": "stackoverflow",
    "arxiv.org": "arxiv",
    "huggingface.co": "huggingface",
    "npmjs.com": "npm",
    "www.npmjs.com": "npm",
    "pypi.org": "pypi",
    # AI 工具
    "chatgpt.com": "chatgpt",
    "gemini.google.com": "gemini",
    # 购物
    "jd.com": "jd",
    "www.jd.com": "jd",
    "amazon.com": "amazon",
    "www.amazon.com": "amazon",
    "taobao.com": "taobao",
    "www.taobao.com": "taobao",
    "store.steampowered.com": "steam",
    "steam.com": "steam",
    # 学术
    "scholar.google.com": "scholar",
    "cnki.net": "cnki",
    "pubmed.ncbi.nlm.nih.gov": "pubmed",
}


def is_opencli_available() -> bool:
    """检测 opencli 是否已安装"""
    return shutil.which("opencli") is not None


def is_browser_bridge_connected() -> bool:
    """
    检测 Browser Bridge 扩展是否连接
    
    运行 opencli doctor 检查连接状态。
    超时 10 秒避免阻塞。
    """
    try:
        result = subprocess.run(
            ["opencli", "doctor"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_site_name(url: str) -> Optional[str]:
    """
    根据 URL 域名获取 opencli 站点名
    
    支持精确匹配和子域名回退：
    - www.xiaohongshu.com → xiaohongshu
    - explore.xiaohongshu.com → xiaohongshu（回退到父域名）
    """
    domain = urlparse(url).netloc
    # 去掉端口号
    domain = domain.split(":")[0]
    
    # 精确匹配
    if domain in DOMAIN_SITE_MAP:
        return DOMAIN_SITE_MAP[domain]
    
    # 子域名回退：逐级去掉前缀
    parts = domain.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in DOMAIN_SITE_MAP:
            return DOMAIN_SITE_MAP[parent]
    
    return None


def _extract_keyword_from_url(url: str) -> Optional[str]:
    """
    从 URL 中提取搜索关键词
    
    支持的 URL 格式：
    - ?keyword=xxx
    - ?q=xxx
    - ?query=xxx
    - ?search=xxx
    - /search/xxx
    - /search_result?keyword=xxx
    """
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    
    # 常见搜索参数
    for param in ["keyword", "q", "query", "search", "kw", "wd"]:
        if param in qs and qs[param][0]:
            return qs[param][0]
    
    # 路径中的搜索词：/search/xxx
    path_match = re.search(r'/search/([^/?]+)', parsed.path)
    if path_match:
        return path_match.group(1)
    
    return None


def detect_action(url: str, keyword: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    根据 URL 和关键词推断 opencli 命令
    
    Returns:
        {"site": "xiaohongshu", "action": "search", "args": ["小升初"]}
        或 None（无法推断）
    """
    site = get_site_name(url)
    if not site:
        # 未知站点，尝试 web read
        return {"site": "web", "action": "read", "args": ["--url", url]}
    
    # 提取关键词：优先使用传入的 keyword，其次从 URL 中提取
    kw = keyword or _extract_keyword_from_url(url)
    
    # 搜索类 URL
    if kw:
        return {"site": site, "action": "search", "args": [kw]}
    
    # 热门/热榜类 URL
    url_lower = url.lower()
    if any(x in url_lower for x in ["hot", "trending", "top", "explore"]):
        return {"site": site, "action": "hot", "args": []}
    
    # 详情页（含 ID 路径）
    id_match = re.search(r'/(note|post|article|status|tweet|video|item|question|topic)/([a-zA-Z0-9]+)', url)
    if id_match:
        return {"site": site, "action": "read", "args": [id_match.group(2)]}
    
    # 默认：尝试 web read
    return {"site": "web", "action": "read", "args": ["--url", url]}


def _parse_opencli_output(raw: str, output_format: str) -> Any:
    """
    解析 opencli 的输出
    
    Args:
        raw: opencli 的 stdout 输出
        output_format: 请求的输出格式
    
    Returns:
        解析后的内容（可能是 dict/list/str）
    """
    if output_format == "json":
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    
    if output_format in ("yaml", "yml"):
        try:
            import yaml
            return yaml.safe_load(raw)
        except ImportError:
            pass
        except Exception:
            pass
    
    # 降级为纯文本
    return raw


def fetch_via_opencli(
    url: str,
    keyword: Optional[str] = None,
    output_format: str = "json",
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """
    通过 opencli 获取页面内容（第三层）
    
    Args:
        url: 目标 URL
        keyword: 搜索关键词（可选）
        output_format: 输出格式 (json/yaml/table/md/plain)
        timeout: 超时时间
    
    Returns:
        {"success": True, "content": ..., "mode_used": "opencli", ...}
        或 None（opencli 不可用或失败）
    """
    print(f"\n[模式3] opencli: {url}")
    
    # ── 前置检查 ──
    if not is_opencli_available():
        print("[模式3] opencli 未安装，跳过")
        return None
    
    # Browser Bridge 连接检查（快速检测，不阻塞）
    bridge_ok = is_browser_bridge_connected()
    if not bridge_ok:
        print("[模式3] Browser Bridge 未连接（尝试继续，可能需要登录）")
    
    # ── 推断命令 ──
    action = detect_action(url, keyword)
    if not action:
        print("[模式3] 无法推断 opencli 命令，跳过")
        return None
    
    # ── 构建命令 ──
    cmd = ["opencli", action["site"]]
    if action["action"] not in ("read",):
        cmd.append(action["action"])
    cmd.extend(action["args"])
    cmd.extend(["-f", output_format])
    
    print(f"[模式3] 执行命令: {' '.join(cmd)}")
    
    # ── 执行命令 ──
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout
        )
        
        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            print(f"[模式3] opencli 执行失败 (exit={result.returncode})")
            if stderr:
                print(f"[模式3] 错误信息: {stderr[:200]}")
            return None
        
        # ── 解析输出 ──
        raw_output = result.stdout.strip()
        if not raw_output:
            print("[模式3] opencli 返回空内容")
            return None
        
        content = _parse_opencli_output(raw_output, output_format)
        
        # 提取标题
        title = f"{action['site']} {action['action']}"
        if isinstance(content, dict):
            title = content.get("title", title)
        elif isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict):
                title = first.get("title", title)
        
        print(f"[模式3] opencli 成功获取内容 (长度: {len(raw_output)})")
        
        return {
            "success": True,
            "content": content,
            "mode_used": "opencli",
            "url": url,
            "title": title,
            "raw_output": raw_output
        }
        
    except subprocess.TimeoutExpired:
        print(f"[模式3] opencli 执行超时 ({timeout}秒)")
        return None
    except FileNotFoundError:
        print("[模式3] opencli 命令未找到")
        return None
    except Exception as e:
        print(f"[模式3] opencli 执行异常: {e}")
        return None


def get_supported_sites() -> List[str]:
    """获取 opencli 支持的站点列表"""
    if not is_opencli_available():
        return []
    
    try:
        result = subprocess.run(
            ["opencli", "--help"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # 简单解析 help 输出中的站点列表
            lines = result.stdout.strip().split("\n")
            sites = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith("-") and not line.startswith("Usage"):
                    # 取第一个词作为站点名
                    parts = line.split()
                    if parts:
                        sites.append(parts[0])
            return sites
    except Exception:
        pass
    
    return list(set(DOMAIN_SITE_MAP.values()))
