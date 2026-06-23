---
name: web-browse
description: |
  通用网页浏览与内容获取技能。支持静态页面、JS 动态渲染页面、以及需要登录/验证码的页面。
  自动选择最优获取方式：web_fetch（轻量）→ headless（JS渲染）→ interactive（带登录按钮交互）。
  当用户提到以下意图时使用此技能：打开网页、浏览网页、检索网页、搜索网页、查看页面、
  抓取内容、获取页面、访问链接、打开XX网站、看看XX首页、帮我看下这个链接、
  提取网页内容、截图网页、web browse、fetch url、open page、以及任何包含 URL 的浏览请求。
---

# Web-Browse Skill — 通用网页浏览工具

支持任意 URL 的智能内容获取，自动处理三类页面：

| 模式 | 适用场景 | 特点 |
|------|---------|------|
| `auto`（默认） | 所有页面 | 自动按历史记录选择最优模式 |
| `web_fetch` | 静态页面 | 最快，无浏览器开销 |
| `headless` | JS 渲染页面 | 无头浏览器，自动 wait |
| `interactive` | 需要登录/验证码 | 打开可见浏览器，注入双按钮交互横幅 |

## 交互登录模式（interactive）

当页面需要登录时，自动在页面顶部注入黄色横幅：

```
┌──────────────────────────────────────────────────────────┐
│ 🔐 请先登录                                               │
│    扫码 / 密码 / 手机登录均可                              │
│    [✅ 完成登录]  [❌ 未完成]              ⏱ 剩余 2分50秒   │
└──────────────────────────────────────────────────────────┘
```

- 用户完成登录后点击「✅ 完成登录」→ 自动提取内容并保存 Cookies
- 用户放弃登录点击「❌ 未完成」→ 返回 None
- 系统同时自动检测登录状态作为辅助判断

## 快速使用

```python
from web_browse import smart_fetch

# 获取任意网页内容
result = smart_fetch("https://example.com", mode="auto", output_format="html")
print(result["content"])  # HTML 内容
print(result["title"])    # 页面标题
print(result["mode_used"])# 实际使用的模式
```

### CLI 用法

```bash
# 自动模式
python -m skills.web_browse "https://example.com"

# 指定交互模式（含登录横幅）
python -m skills.web_browse "https://example.com" --mode interactive --timeout 180

# 查看历史记录
python -m skills.web_browse --history
```

## 模块结构

```
web-browse/
├── __init__.py          # 入口：smart_fetch
├── __main__.py          # CLI
├── core/
│   ├── fetcher.py       # 核心获取逻辑 + 交互横幅
│   ├── detector.py      # 登录墙/二维码检测
│   ├── cookies.py       # Cookie 持久化（~/.web_skill_cache/）
│   └── history.py       # 模式选择历史记录
├── browser/
│   └── brave_driver.py  # Brave/Chrome WebDriver 管理
└── utils/
```

## Cookies 缓存

登录成功后自动保存到 `~/.web_skill_cache/cookies/{domain}.json`，下次访问同域名自动加载，减少重复登录。
