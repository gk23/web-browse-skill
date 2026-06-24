#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web-Browse Skill CLI 入口

用法:
    # 方式1: 从项目父目录用包名运行
    cd /path/to/skill_projects
    python3 -m web_browse "https://example.com"
    
    # 方式2: 直接运行本文件（自动处理路径）
    python3 /path/to/web-browse-skill/__main__.py "https://example.com"
    
    # 选项:
    --mode headless --output-format markdown
    --history
    --clear-history
"""

import sys
import os
import argparse

# 支持直接运行 __main__.py（非 -m 方式）
_this_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

# 包名映射: web-browse-skill 目录 -> web_browse 包
# 需要确保 sys.path 中有 skill_projects 目录，且目录名合法
# 由于目录名含连字符，需要特殊处理
_pkg_name = os.path.basename(_this_dir).replace('-', '_')

# 尝试导入
try:
    from web_browse.core.fetcher import smart_fetch
    from web_browse.core.history import load_history, print_history
except ImportError:
    # 回退: 将当前目录也加入 path，用相对导入
    if _this_dir not in sys.path:
        sys.path.insert(0, _this_dir)
    # 创建一个临时软链接或直接修改导入
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "web_browse", 
        os.path.join(_this_dir, "__init__.py"),
        submodule_search_locations=[_this_dir]
    )
    web_browse = importlib.util.module_from_spec(spec)
    sys.modules["web_browse"] = web_browse
    spec.loader.exec_module(web_browse)
    
    from web_browse.core.fetcher import smart_fetch
    from web_browse.core.history import load_history, print_history


def main():
    parser = argparse.ArgumentParser(description='通用网页浏览工具')
    parser.add_argument('url', nargs='?', help='目标 URL')
    parser.add_argument(
        '--mode',
        choices=['auto', 'web_fetch', 'headless', 'opencli', 'interactive'],
        default='auto',
        help='获取模式 (默认: auto)'
    )
    parser.add_argument(
        '--output-format',
        choices=['html', 'markdown', 'text', 'json'],
        default='html',
        help='输出格式 (默认: html)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='超时时间（秒）(默认: 30)'
    )
    parser.add_argument('--keyword', help='搜索关键词（opencli 模式使用）')
    parser.add_argument('--history', action='store_true', help='查看历史记录')
    parser.add_argument('--clear-history', action='store_true', help='清除历史记录')
    parser.add_argument('--output', '-o', help='输出文件路径')
    
    args = parser.parse_args()
    
    # 处理历史记录命令
    if args.clear_history:
        import os
        from .core.history import HISTORY_FILE
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print("历史记录已清除")
        return
    
    if args.history:
        print_history()
        return
    
    # 检查 URL 参数
    if not args.url:
        parser.print_help()
        return
    
    # 执行获取
    result = smart_fetch(
        args.url,
        mode=args.mode,
        output_format=args.output_format,
        timeout=args.timeout,
        keyword=args.keyword
    )
    
    if result["success"]:
        print(f"\n成功获取内容")
        print(f"模式: {result['mode_used']}")
        print(f"标题: {result['title']}")
        print(f"内容长度: {len(result['content'])} 字符")
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result['content'])
            print(f"内容已保存到: {args.output}")
        else:
            # 预览前 1500 字符
            preview = result['content'][:1500]
            print(f"\n内容预览:\n{preview}\n...")
    else:
        print("\n获取失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
