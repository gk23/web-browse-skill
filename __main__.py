#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web-Browse Skill CLI 入口

用法:
    python -m skills.web_browse "https://example.com"
    python -m skills.web_browse "https://example.com" --mode headless --output-format markdown
    python -m skills.web_browse --history
    python -m skills.web_browse --clear-history
"""

import sys
import argparse
from .core.fetcher import smart_fetch
from .core.history import load_history


def main():
    parser = argparse.ArgumentParser(description='通用网页浏览工具')
    parser.add_argument('url', nargs='?', help='目标 URL')
    parser.add_argument(
        '--mode',
        choices=['auto', 'web_fetch', 'headless', 'interactive'],
        default='auto',
        help='获取模式 (默认: auto)'
    )
    parser.add_argument(
        '--output-format',
        choices=['html', 'markdown', 'text'],
        default='html',
        help='输出格式 (默认: html)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='超时时间（秒）(默认: 30)'
    )
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
        history = load_history()
        if history:
            print("\n历史记录:")
            for domain, record in history.items():
                mode = record.get('mode', 'N/A')
                reason = record.get('reason', 'N/A')
                count = record.get('success_count', 0)
                last = record.get('last_success', record.get('last_failure', 'N/A'))
                print(f"  {domain}: 模式={mode}, 原因={reason}, 成功次数={count}, 最后={last}")
        else:
            print("暂无历史记录")
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
        timeout=args.timeout
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
