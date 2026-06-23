"""
Web-Browse Skill - 通用网页浏览工具

用法:
    from skills.web_browse import smart_fetch
    
    result = smart_fetch("https://example.com", mode="auto", output_format="html")
    print(result["content"])
"""

from .core.fetcher import smart_fetch

__all__ = ["smart_fetch"]
