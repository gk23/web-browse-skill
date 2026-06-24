# Web-Browse Skill

通用网页浏览技能 — CodeBuddy 插件，支持任意 URL 的智能内容获取。

## 功能

- **自动模式选择**：`web_fetch`（静态页）→ `headless`（JS 渲染）→ `interactive`（需登录）
- **交互登录**：页面顶部注入「✅ 完成登录 / ❌ 未完成」双按钮横幅
- **Cookie 持久化**：登录后自动保存，下次免登
- **二维码/扫码登录**：自动检测并等待扫码

## 安装

将本目录放到 CodeBuddy 的 skills 目录下：

```
~/.codebuddy/skills/web_browse_skill/
```

## 使用

```python
from web_browse_skill import smart_fetch

result = smart_fetch("https://example.com", mode="auto")
print(result["content"])
```

CLI：

```bash
python -m web_browse_skill "https://example.com"
python -m web_browse_skill "https://example.com" --mode interactive --timeout 180
```

## 模块结构

```
web_browse_skill/
├── __init__.py          # 入口：smart_fetch
├── __main__.py          # CLI
├── SKILL.md             # 技能描述与触发条件
├── core/
│   ├── fetcher.py       # 核心获取 + 交互横幅
│   ├── detector.py      # 登录墙/二维码检测
│   ├── cookies.py       # Cookie 持久化
│   └── history.py       # 模式选择历史
├── browser/
│   └── brave_driver.py  # Brave/Chrome WebDriver
└── utils/
```

## 依赖

- Python 3.8+
- Selenium
- Brave 或 Chrome 浏览器 + 对应 WebDriver
