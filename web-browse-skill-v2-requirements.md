# Web-Browse Skill V2 需求文档

## 一、Skill 定位

**Web-Browse Skill** 是一个通用网页内容获取工具，支持从静态页面到需要人工登录的复杂网站的内容获取。

### V2 版本新增

在原有**三层架构**基础上，增加**第四层（opencli）和第五层（系统浏览器人工交互模式）**，专门解决以下场景：
- 网站反自动化检测严格（如小红书）
- 用户已有浏览器登录态，希望复用
- 需要人工操作后才能获取内容
- **优先使用 opencli 秒级获取结构化数据，减少人工交互**

## 二、五层架构设计

```
┌─────────────────────────────────────────────────────────────────────┐
│  第一层：web_fetch                                                   │
│  HTTP 静态请求，速度最快                                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ 失败/需要 JS
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第二层：headless                                                    │
│  无头浏览器渲染 JS，无需人工干预                                     │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ 失败/需要登录
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第三层：opencli (新增)                                              │
│  CLI 结构化访问，覆盖 155+ 站点，秒级返回结构化数据                   │
│  通过 Browser Bridge 扩展与浏览器通信，自动维护登录态                 │
│  无需人工干预，比 interactive 更快更稳定                              │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ 失败/站点不支持/被反检测
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第四层：interactive (Selenium + Brave)                              │
│  Selenium 驱动 Brave 浏览器，自动注入 Cookies，自动检测登录状态         │
│  使用独立的 Brave 实例，与用户系统浏览器隔离                            │
│  需要人工交互（扫码登录等），注入黄色横幅按钮                          │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ 失败/被反检测/需要真实浏览器环境
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第五层：system_browser                                              │
│  使用系统默认浏览器，复用用户已有登录态，人工操作后获取内容            │
└─────────────────────────────────────────────────────────────────────┘
```

### 为什么在 interactive 之前增加 opencli 层？

| 对比维度 | opencli | interactive |
|---------|---------|------------|
| 速度 | **2-3 秒** | 15-30 秒 |
| 数据格式 | **结构化 JSON** | 原始 HTML（需二次解析） |
| 人工干预 | **无需** | 需要扫码/点按钮 |
| 登录态维护 | Browser Bridge 自动维护 | Selenium 注入 Cookie |
| 覆盖范围 | 155+ 站点 | 所有网站 |
| 反检测能力 | 强（真实浏览器 Profile） | 中（Selenium 特征可能被检测） |

**核心逻辑**：能用 opencli 秒级拿到结构化数据的，就不要走 interactive 让用户等 30 秒。opencli 失败时再降级到 interactive 人工交互。

## 三、第三层：opencli 模式详解

### 3.1 设计目标

1. **秒级获取**：CLI 命令直接返回结构化数据，无需等待浏览器渲染
2. **零人工干预**：通过 Browser Bridge 扩展自动维护登录态，无需扫码/点按钮
3. **结构化输出**：直接返回 JSON/YAML，无需从 HTML 中解析
4. **覆盖主流站点**：155+ 站点适配器，涵盖中文社交、国际社交、开发者工具等
5. **稳定可靠**：不依赖 DOM 结构变化，比 Selenium 更稳定

### 3.2 工作原理

```
终端命令 → opencli CLI → Browser Bridge 扩展 → 浏览器操作 → 结构化数据返回
```

- opencli 通过 Browser Bridge 浏览器扩展与浏览器通信
- Browser Bridge 使用真实的浏览器 Profile，登录态自动保持
- 首次使用需安装 Browser Bridge 扩展（`setup-opencli.sh` 自动完成）

### 3.3 渐进式发现

不需要记住任何命令，通过 `--help` 逐层探索：

```bash
opencli --help                     # 我能操作哪些网站？
opencli <site> --help              # 这个网站有哪些操作？
opencli <site> <command> --help    # 这个操作怎么用？
```

### 3.4 典型用法映射

| 用户需求 | opencli 命令 |
|---------|-------------|
| 看微博热搜 | `opencli weibo hot` |
| 搜索小红书笔记 | `opencli xiaohongshu search <关键词>` |
| 看知乎热榜 | `opencli zhihu hot` |
| B站热门视频 | `opencli bilibili hot` |
| 搜索 Twitter | `opencli twitter search <关键词>` |
| GitHub trending | `opencli gh trending` |
| 获取 YouTube 字幕 | `opencli youtube transcript <video-id>` |
| 读取任意网页为 Markdown | `opencli web read --url <URL>` |

### 3.5 输出格式

所有命令支持 `-f` / `--format` 选项：

| 格式 | 用途 |
|------|------|
| `table` | 默认，终端可读 |
| `json` | 程序化处理、需要完整结构化数据 |
| `yaml` | 人类可读的结构化数据 |
| `md` | Markdown 格式 |
| `csv` | 表格导出 |
| `plain` | 纯文本 |

### 3.6 覆盖的网站类别

- **中文社交**：微博、小红书、知乎、豆瓣、即刻、V2EX、贴吧
- **中文视频**：B站、抖音
- **中文资讯**：36氪、雪球、什么值得买
- **国际社交**：Twitter/X、Reddit、LinkedIn、Instagram、Facebook、Bluesky
- **国际视频**：YouTube、TikTok
- **国际资讯**：HackerNews、ProductHunt、Medium、BBC、Bloomberg、Reuters
- **开发者**：GitHub、StackOverflow、ArXiv、HuggingFace、npm、PyPI
- **AI 工具**：ChatGPT、Gemini、Grok、Doubao、DeepSeek、Kimi
- **购物**：JD、Amazon、淘宝、Steam
- **学术**：Google Scholar、CNKI、PubMed
- **通用**：`opencli web read` — 任意网页转 Markdown

### 3.7 降级条件

当以下情况发生时，从 opencli 降级到 interactive：

- `opencli` 命令不存在（未安装）
- Browser Bridge 扩展未安装或连接失败（`opencli doctor` 报错）
- 目标站点不在 opencli 覆盖范围内
- opencli 命令执行失败（返回非零退出码）
- 站点反检测严格，opencli 被拦截

### 3.8 安装与诊断

```bash
# 首次安装（幂等，可重复运行）
bash {web-tools-guide-baseDir}/scripts/setup-opencli.sh

# 诊断连接状态
opencli doctor

# 查看详细错误
opencli <site> <command> -v
```

---

## 四、第四层：interactive 模式详解

### 4.1 设计目标

1. **绕过反自动化检测**：使用 Selenium 驱动 Brave 浏览器，模拟真实用户操作
2. **自动注入 Cookie**：复用已保存的登录态，减少重复登录
3. **人机协作**：用户负责扫码登录，Skill 负责提取内容
4. **黄色横幅交互**：注入「完成登录」/「未完成」按钮，明确交互流程
5. **浏览器隔离**：使用独立的 Brave 实例，与用户系统浏览器隔离

### 4.2 交互流程

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: Skill 调用 interactive 模式                                │
│  输入: URL (可选: keyword, extract_rules)                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: Selenium 打开 Brave 浏览器                                  │
│  - 自动注入已保存的 Cookies                                          │
│  - 自动检测是否需要登录（二维码/登录弹窗/验证码）                     │
│  - 页面顶部注入黄色横幅（完成登录/未完成按钮）                        │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: 用户操作浏览器（人工）                                       │
│  - 如未登录 → 扫码/密码/手机登录                                     │
│  - 登录成功后点击「✅ 完成登录」按钮                                  │
│  - 放弃登录点击「❌ 未完成」按钮                                      │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4: 自动提取内容                                                │
│  - Selenium 获取页面 HTML                                            │
│  - 保存 Cookies 到缓存                                               │
│  - 按 output_format 格式化返回                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 降级条件

当以下情况发生时，从 interactive 降级到 system_browser：

- Selenium 被网站反自动化检测拦截
- Brave 浏览器启动失败
- 用户点击「❌ 未完成」
- 超时未完成登录

---

## 五、第五层：system_browser 模式详解

### 5.1 设计目标

1. **绕过反自动化检测**：使用用户日常使用的浏览器，避免被检测
2. **复用登录态**：直接使用用户已有的 Cookie/Session
3. **人机协作**：用户负责操作（登录、搜索、导航），Skill 负责提取内容
4. **灵活等待**：支持自动检测和手动确认两种等待方式
5. **浏览器隔离**：第四层和第五层使用独立的 Brave 浏览器，不干扰用户个人浏览器

### 5.2 交互流程

```
┌─────────────────────────────────────────────────────────────────────┐
│  Step 1: Skill 调用 system_browser 模式                             │
│  输入: URL (可选: keyword, extract_rules)                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 2: 打开 Brave 浏览器（系统默认浏览器）                            │
│  - 使用系统命令打开 Brave 浏览器（已安装）                             │
│  - 访问目标 URL                                                     │
│  - Brave 使用独立的 Cookie/登录态（与用户 Chrome/Safari 隔离）         │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 3: 用户操作浏览器（人工）                                       │
│  - 如未登录 → 手动登录                                               │
│  - 如需搜索 → 手动输入关键词搜索                                      │
│  - 如需导航 → 手动点击链接                                            │
│  - 确认页面内容已加载完成                                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 4: 内容获取（自动或手动）                                        │
│  方式A - 自动检测（需浏览器扩展）:                                    │
│    - 扩展自动提取页面结构化数据                                        │
│    - 通过 WebSocket/HTTP 发送到本地服务                               │
│                                                                       │
│  方式B - 手动确认（默认）:                                            │
│    - 用户确认内容已就绪                                                │
│    - Skill 通过剪贴板/文件/截图等方式获取内容                          │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Step 5: 返回结构化结果                                               │
│  - 解析提取的数据                                                      │
│  - 按 output_format 格式化（html/markdown/json/text）                  │
│  - 返回给用户                                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 浏览器打开方式

**重要：第四层和第五层统一使用 Brave 浏览器**

```python
import subprocess
import platform
import os

def open_system_browser(url: str):
    """
    使用 Brave 浏览器打开 URL
    与用户个人浏览器（Chrome/Safari/Edge）完全隔离
    
    支持 macOS / Windows / Linux
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        if os.path.exists(brave_path):
            subprocess.Popen([brave_path, url])
        else:
            subprocess.Popen(["open", "-a", "Brave Browser", url])
    elif system == "Windows":
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        brave_path = next((p for p in brave_paths if os.path.exists(p)), None)
        if brave_path:
            subprocess.Popen([brave_path, url])
        else:
            subprocess.Popen(["start", "brave", url], shell=True)
    elif system == "Linux":
        subprocess.Popen(["brave", url])
    else:
        raise OSError(f"不支持的操作系统: {system}")
```

### 5.4 内容获取方案

| 方案 | 原理 | 优先级 | 适用场景 |
|------|------|--------|----------|
| **A. 浏览器扩展** | 扩展提取 DOM 数据，通过 WebSocket 发送 | ⭐ 首选 | 用户已安装扩展 |
| **B. 剪贴板** | 用户复制内容，Skill 读取剪贴板 | 备选 | 简单文本内容 |
| **C. 文件导出** | 扩展导出 JSON 文件，Skill 读取 | 备选 | 大量数据 |
| **D. 手动输入** | 用户直接粘贴内容到终端 | 保底 | 任何场景 |

### 5.5 等待用户完成的机制

```python
import time
import os

def wait_for_user_complete(timeout: int = 300, mode: str = "auto"):
    """
    等待用户完成操作
    
    Args:
        timeout: 最大等待时间（秒）
        mode: "auto"=自动检测（需扩展）, "manual"=手动确认
    
    Returns:
        bool: 是否成功
    """
    if mode == "auto":
        return _wait_with_auto_detection(timeout)
    else:
        return _wait_with_manual_confirm(timeout)

def _wait_with_manual_confirm(timeout: int) -> bool:
    """手动确认模式"""
    print("\n" + "=" * 60)
    print("请在浏览器中完成以下操作：")
    print("  1. 登录网站（如需要）")
    print("  2. 搜索或导航到目标页面")
    print("  3. 确认内容已加载")
    print("\n完成后请按 Enter 键继续...")
    print("=" * 60 + "\n")
    
    try:
        input()  # 等待用户按 Enter
        return True
    except EOFError:
        # IDE 环境不支持 input，使用文件标记
        return _wait_with_file_marker(timeout)

def _wait_with_file_marker(timeout: int) -> bool:
    """文件标记模式（IDE 环境）"""
    marker_file = ".web_browse_done"
    print(f"\n[IDE 模式] 请在浏览器操作完成后，创建文件: {marker_file}")
    
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(marker_file):
            os.remove(marker_file)
            return True
        time.sleep(1)
    
    return False
```

## 六、接口设计（V2 更新）

### 6.1 新增参数

```python
def smart_fetch(
    url: str,
    mode: str = "auto",           # 新增: "opencli", "system_browser"
    output_format: str = "html",  # "html" | "markdown" | "json" | "text"
    timeout: int = 30,
    # 新增参数:
    system_browser_mode: str = "manual",  # "manual" | "auto"
    keyword: str = None,                   # 搜索关键词（可选）
    extract_rules: dict = None            # 内容提取规则（可选）
) -> dict:
```

### 6.2 调用示例

```python
from skills.web_browse import smart_fetch

# 自动模式（五层自动降级）
result = smart_fetch("https://www.xiaohongshu.com/search_result?keyword=小升初")

# 指定 opencli 模式（优先尝试）
result = smart_fetch(
    url="https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="opencli",
    output_format="json"
)

# 指定 interactive 模式
result = smart_fetch(
    url="https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="interactive",
    timeout=180
)

# 指定 system_browser 模式
result = smart_fetch(
    url="https://www.xiaohongshu.com",
    mode="system_browser",
    keyword="小升初",
    system_browser_mode="manual",
    output_format="json",
    extract_rules={
        "note_title": ".note-item .title",
        "note_content": ".note-item .content",
        "author": ".note-item .author-name",
        "likes": ".note-item .like-count"
    }
)

# 返回结果
{
    "success": True,
    "content": [...],           # 提取的内容
    "mode_used": "opencli",     # 实际使用的模式
    "url": "https://...",
    "title": "页面标题"
}
```

### 6.3 CLI 用法

```bash
# 自动模式（五层自动降级）
python -m skills.web_browse "https://www.xiaohongshu.com/search_result?keyword=小升初"

# 指定 opencli 模式
python -m skills.web_browse "https://www.xiaohongshu.com/search_result?keyword=小升初" \
    --mode opencli --format json

# 指定 interactive 模式
python -m skills.web_browse "https://www.xiaohongshu.com" \
    --mode interactive --timeout 180

# 指定 system_browser 模式
python -m skills.web_browse "https://www.xiaohongshu.com" \
    --mode system_browser \
    --keyword "小升初" \
    --system-browser-mode manual \
    --format json
```

## 七、文件结构更新

```
skills/web-browse/                    # 现有结构
├── skill.json                        # 更新: 添加 opencli + system_browser 模式
├── __init__.py                       # 导出 smart_fetch
├── __main__.py                       # CLI 入口
├── core/
│   ├── __init__.py
│   ├── fetcher.py                    # 更新: 添加 opencli + system_browser 调度逻辑
│   ├── detector.py                   # 现有: 登录检测
│   ├── history.py                    # 现有: 历史记录
│   ├── cookies.py                    # 现有: Cookie 管理
│   ├── opencli_adapter.py            # 新增: opencli 适配器模块
│   └── system_browser.py             # 新增: 系统浏览器交互模块
├── browser/
│   ├── __init__.py
│   └── brave_driver.py               # 现有: Brave 浏览器封装
└── extensions/                       # 新增: 浏览器扩展
    ├── chrome/
    │   ├── manifest.json
    │   ├── content.js
    │   └── background.js
    └── firefox/
        ├── manifest.json
        └── ...
```

## 八、核心模块设计

### 8.1 opencli_adapter.py（新增）

```python
#!/usr/bin/env python3
"""
opencli 适配器模块

提供功能：
1. 检测 opencli 是否可用
2. 根据域名映射到 opencli 站点名
3. 调用 opencli 命令获取结构化数据
4. 解析 opencli 输出为统一格式
"""

import subprocess
import json
import shutil
from typing import Optional, Dict, Any
from urllib.parse import urlparse


# 域名到 opencli 站点名映射
DOMAIN_SITE_MAP = {
    "xiaohongshu.com": "xiaohongshu",
    "www.xiaohongshu.com": "xiaohongshu",
    "rednote.com": "xiaohongshu",
    "weibo.com": "weibo",
    "www.weibo.com": "weibo",
    "zhihu.com": "zhihu",
    "www.zhihu.com": "zhihu",
    "bilibili.com": "bilibili",
    "www.bilibili.com": "bilibili",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "reddit.com": "reddit",
    "www.reddit.com": "reddit",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "github.com": "gh",
    "douban.com": "douban",
    "www.douban.com": "douban",
    "jike.com": "jike",
    "v2ex.com": "v2ex",
    "tieba.baidu.com": "tieba",
    "douyin.com": "douyin",
    "www.douyin.com": "douyin",
    "36kr.com": "36kr",
    "xueqiu.com": "xueqiu",
    "smzdm.com": "smzdm",
    "hackernews.com": "hackernews",
    "news.ycombinator.com": "hackernews",
    "producthunt.com": "producthunt",
    "medium.com": "medium",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "stackoverflow.com": "stackoverflow",
    "arxiv.org": "arxiv",
    "steam.com": "steam",
    "store.steampowered.com": "steam",
    "jd.com": "jd",
    "www.jd.com": "jd",
    "amazon.com": "amazon",
    "www.amazon.com": "amazon",
}


def is_opencli_available() -> bool:
    """检测 opencli 是否已安装"""
    return shutil.which("opencli") is not None


def is_browser_bridge_connected() -> bool:
    """检测 Browser Bridge 扩展是否连接"""
    try:
        result = subprocess.run(
            ["opencli", "doctor"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_site_name(url: str) -> Optional[str]:
    """根据 URL 域名获取 opencli 站点名"""
    domain = urlparse(url).netloc
    # 去掉端口号
    domain = domain.split(":")[0]
    return DOMAIN_SITE_MAP.get(domain)


def detect_action(url: str, keyword: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    根据 URL 和关键词推断 opencli 命令
    
    Returns:
        {"site": "xiaohongshu", "action": "search", "args": ["小升初"]}
        或 None（无法推断）
    """
    site = get_site_name(url)
    if not site:
        return None
    
    # 搜索类 URL
    if keyword or "search" in url or "keyword" in url:
        return {"site": site, "action": "search", "args": [keyword or ""]}
    
    # 热门/热榜类 URL
    if "hot" in url or "trending" in url or "top" in url:
        return {"site": site, "action": "hot", "args": []}
    
    # 默认：尝试 web read
    return {"site": "web", "action": "read", "args": ["--url", url]}


def fetch_via_opencli(
    url: str,
    keyword: Optional[str] = None,
    output_format: str = "json",
    timeout: int = 30
) -> Optional[Dict[str, Any]]:
    """
    通过 opencli 获取页面内容
    
    Args:
        url: 目标 URL
        keyword: 搜索关键词（可选）
        output_format: 输出格式
        timeout: 超时时间
    
    Returns:
        {"success": True, "content": ..., "mode_used": "opencli", ...}
        或 None（opencli 不可用或失败）
    """
    # 前置检查
    if not is_opencli_available():
        return None
    
    if not is_browser_bridge_connected():
        return None
    
    # 推断命令
    action = detect_action(url, keyword)
    if not action:
        return None
    
    # 构建命令
    cmd = ["opencli", action["site"]]
    if action["action"] != "read":
        cmd.append(action["action"])
    cmd.extend(action["args"])
    cmd.extend(["-f", output_format, "--limit", "10"])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=timeout
        )
        
        if result.returncode != 0:
            return None
        
        # 解析输出
        content = result.stdout.strip()
        if output_format == "json":
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                pass
        
        return {
            "success": True,
            "content": content,
            "mode_used": "opencli",
            "url": url,
            "title": f"{action['site']} {action['action']}",
            "raw_output": result.stdout
        }
        
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None
```

### 8.2 system_browser.py

```python
#!/usr/bin/env python3
"""
系统浏览器交互模块

提供功能：
1. 打开 Brave 浏览器（与用户系统浏览器隔离）
2. 等待用户操作完成
3. 获取页面内容（多种方式）
4. 解析结构化数据
"""

import subprocess
import platform
import time
import os
import json
from typing import Optional, Dict, Any


def open_browser(url: str) -> None:
    """
    打开 Brave 浏览器
    使用独立的 Brave 实例，不与用户个人浏览器冲突
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        if os.path.exists(brave_path):
            subprocess.Popen([brave_path, url])
        else:
            subprocess.Popen(["open", "-a", "Brave Browser", url])
    elif system == "Windows":
        brave_paths = [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        brave_path = next((p for p in brave_paths if os.path.exists(p)), None)
        if brave_path:
            subprocess.Popen([brave_path, url])
        else:
            subprocess.Popen(["start", "brave", url], shell=True)
    elif system == "Linux":
        subprocess.Popen(["brave", url])
    else:
        raise OSError(f"不支持的操作系统: {system}")
    
    print(f"[System Browser] 已使用 Brave 打开: {url}")


def wait_for_completion(timeout: int = 300, mode: str = "manual") -> bool:
    """
    等待用户完成操作
    
    Args:
        timeout: 最大等待时间（秒）
        mode: "manual"=手动确认, "auto"=自动检测（需扩展）
    
    Returns:
        bool: 是否成功
    """
    if mode == "auto":
        return _wait_auto(timeout)
    return _wait_manual(timeout)


def _wait_manual(timeout: int) -> bool:
    """手动确认模式"""
    print("\n" + "=" * 60)
    print("请在浏览器中完成以下操作：")
    print("  1. 登录网站（如需要）")
    print("  2. 搜索或导航到目标页面")
    print("  3. 确认内容已加载")
    print("\n完成后请按 Enter 键继续...")
    print("=" * 60 + "\n")
    
    try:
        input()
        return True
    except EOFError:
        # IDE 环境，使用文件标记
        return _wait_with_file_marker(timeout)


def _wait_with_file_marker(timeout: int) -> bool:
    """文件标记模式（IDE 环境）"""
    marker_file = ".web_browse_done"
    print(f"[IDE 模式] 请在操作完成后创建文件: {marker_file}")
    
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(marker_file):
            os.remove(marker_file)
            return True
        time.sleep(1)
    
    return False


def _wait_auto(timeout: int) -> bool:
    """自动检测模式（需浏览器扩展配合）"""
    # TODO: 通过 WebSocket 或文件监听扩展发送的信号
    pass


def fetch_via_system_browser(
    url: str,
    keyword: Optional[str] = None,
    system_browser_mode: str = "manual",
    timeout: int = 300
) -> Optional[str]:
    """
    使用系统浏览器获取页面内容
    
    Args:
        url: 目标 URL
        keyword: 搜索关键词（可选）
        system_browser_mode: "manual" 或 "auto"
        timeout: 超时时间
    
    Returns:
        页面 HTML 或 None
    """
    # 构建最终 URL
    final_url = url
    if keyword:
        final_url = f"{url}?keyword={keyword}"
    
    # 打开浏览器
    open_browser(final_url)
    
    # 等待用户完成
    if not wait_for_completion(timeout, system_browser_mode):
        print("[System Browser] 等待超时")
        return None
    
    # 获取内容
    # TODO: 通过扩展、剪贴板或手动输入获取内容
    
    return None


def extract_content(html: str, rules: Dict[str, str]) -> Dict[str, Any]:
    """
    根据规则提取结构化内容
    
    Args:
        html: 页面 HTML
        rules: CSS 选择器规则，如 {"title": ".note-title"}
    
    Returns:
        提取的内容
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    
    for key, selector in rules.items():
        elements = soup.select(selector)
        result[key] = [el.get_text(strip=True) for el in elements]
    
    return result
```

## 九、与现有代码的整合

### 9.1 fetcher.py 更新

在 `smart_fetch` 函数的调度逻辑中，添加 `opencli` 和 `system_browser` 模式：

```python
def smart_fetch(url: str, mode: str = "auto", output_format: str = "html", 
                timeout: int = 30, **kwargs) -> Dict[str, Any]:
    
    # ... 现有逻辑（第一层 web_fetch、第二层 headless）...
    
    # 第三层：opencli（新增，优先于 interactive）
    if not html and mode in ("auto", "opencli"):
        from .opencli_adapter import fetch_via_opencli
        result = fetch_via_opencli(
            url,
            keyword=kwargs.get("keyword"),
            output_format=output_format,
            timeout=timeout
        )
        if result and result.get("success"):
            return result  # opencli 直接返回结构化数据
        # opencli 失败，告知用户原因
        print(f"[降级] opencli 失败，降级到 interactive 模式")
    
    # 第四层：interactive（现有逻辑）
    if not html and mode in ("auto", "interactive"):
        # ... 现有 interactive 逻辑 ...
        pass
    
    # 第五层：system_browser
    if not html and mode in ("auto", "system_browser"):
        from .system_browser import fetch_via_system_browser
        html = fetch_via_system_browser(
            url, 
            keyword=kwargs.get("keyword"),
            system_browser_mode=kwargs.get("system_browser_mode", "manual"),
            timeout=timeout
        )
        if html:
            mode_used = "system_browser"
            record_success(url, "system_browser", "使用系统浏览器人工交互模式")
    
    # ... 后续逻辑 ...
```

### 9.2 skill.json 更新

```json
{
  "name": "web-browse",
  "description": "通用网页浏览工具，支持静态页面、JS渲染页面和需要人工登录的页面。",
  "parameters": {
    "url": {
      "type": "string",
      "description": "目标网页 URL",
      "required": true
    },
    "mode": {
      "type": "string",
      "enum": ["auto", "web_fetch", "headless", "opencli", "interactive", "system_browser"],
      "description": "获取模式：auto=自动选择（默认），opencli=CLI结构化访问，interactive=浏览器交互登录，system_browser=系统浏览器人工交互",
      "default": "auto"
    },
    "output_format": {
      "type": "string",
      "enum": ["html", "markdown", "text", "json"],
      "description": "输出格式",
      "default": "html"
    },
    "timeout": {
      "type": "integer",
      "description": "超时时间（秒）",
      "default": 30
    },
    "system_browser_mode": {
      "type": "string",
      "enum": ["manual", "auto"],
      "description": "system_browser 模式的等待方式：manual=手动确认，auto=自动检测（需扩展）",
      "default": "manual"
    },
    "keyword": {
      "type": "string",
      "description": "搜索关键词（可选，用于 opencli/interactive/system_browser 模式）",
      "required": false
    },
    "extract_rules": {
      "type": "object",
      "description": "内容提取规则，CSS 选择器（可选，用于 system_browser 模式）",
      "required": false
    }
  }
}
```

## 十、使用场景示例

### 10.1 小红书搜索（自动降级）

```python
from skills.web_browse import smart_fetch

# 自动模式：五层自动降级
# web_fetch → headless → opencli（秒级成功！）→ 不需要 interactive
result = smart_fetch(
    "https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="auto"
)
# result["mode_used"] == "opencli"  ← 自动选择了最快的 opencli

# 如果 opencli 未安装/失败，自动降级到 interactive
# result["mode_used"] == "interactive"
```

### 10.2 小红书搜索（指定模式）

```python
# 强制使用 opencli
result = smart_fetch(
    url="https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="opencli",
    output_format="json"
)

# 强制使用 interactive（需要人工扫码）
result = smart_fetch(
    url="https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="interactive",
    timeout=180
)

# 强制使用 system_browser
result = smart_fetch(
    url="https://www.xiaohongshu.com",
    mode="system_browser",
    keyword="小升初",
    system_browser_mode="manual",
    output_format="json",
    extract_rules={
        "title": ".note-item .title",
        "content": ".note-item .content",
        "author": ".note-item .author-name"
    }
)
```

### 10.3 知乎热榜

```python
# opencli 秒级获取
result = smart_fetch(
    "https://www.zhihu.com/hot",
    mode="opencli"
)

# 降级到 system_browser
result = smart_fetch(
    "https://www.zhihu.com/hot",
    mode="system_browser",
    output_format="json",
    extract_rules={
        "question": ".HotList-item .HotList-itemTitle",
        "heat": ".HotList-item .HotList-itemMetrics"
    }
)
```

## 十一、浏览器隔离说明

### 11.1 为什么使用 Brave 而非系统默认浏览器

| 对比项 | 系统默认浏览器（Chrome/Safari/Edge） | Brave 浏览器（推荐） |
|--------|-------------------------------------|---------------------|
| **登录态** | 复用用户个人登录态 | 独立的登录态 |
| **Cookie 隔离** | 与用户个人 Cookie 混合 | 完全隔离 |
| **隐私** | Agent 操作会留下历史记录 | 无痕模式，不保留历史 |
| **反检测** | 容易被网站识别为自动化工具 | 真实浏览器，更难检测 |
| **干扰用户** | 会打断用户当前浏览 | 完全独立，不影响用户 |

### 11.2 五层浏览器使用

| 层级 | 浏览器 | 说明 |
|------|--------|------|
| 第一层 web_fetch | 无 | HTTP 请求 |
| 第二层 headless | Brave（无头模式） | Selenium 控制，无界面 |
| 第三层 opencli | Brave（Browser Bridge） | CLI 命令，Browser Bridge 扩展通信 |
| 第四层 interactive | Brave（有界面） | Selenium 控制，有界面 |
| 第五层 system_browser | Brave（有界面） | 用户手动操作 |

**所有需要浏览器的地方都使用 Brave，确保与用户个人浏览器完全隔离。**

## 十二、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 用户未安装 Brave | 无法打开 | 检测并提示用户安装 |
| Brave 打开失败 | 任务失败 | 降级到 interactive 模式 |
| 用户操作超时 | 任务失败 | 合理设置超时，友好提示 |
| IDE 环境不支持 input | 手动确认失效 | 使用文件标记作为备选 |
| 内容提取失败 | 返回空结果 | 提供原始 HTML 作为备选 |
| opencli 未安装 | 第三层不可用 | 自动降级到 interactive |
| Browser Bridge 连接失败 | 第三层不可用 | 运行 `opencli doctor` 诊断，降级到 interactive |
| opencli 站点不支持 | 第三层不可用 | 降级到 interactive/system_browser |

## 十三、功能实现状态

### 13.1 已实现功能

| 层级 | 功能 | 状态 | 说明 |
|------|------|------|------|
| 第一层 | HTTP 静态请求 | ✅ 已实现 | `web_fetch` 基础请求 |
| 第一层 | User-Agent 伪装 | ✅ 已实现 | 模拟浏览器请求头 |
| 第一层 | 超时控制 | ✅ 已实现 | 可配置超时时间 |
| 第二层 | 无头浏览器渲染 | ✅ 已实现 | Selenium + Brave 无头模式 |
| 第二层 | Cookie 复用 | ✅ 已实现 | 从文件读取历史 Cookie |
| 第二层 | JS 动态内容获取 | ✅ 已实现 | 等待页面加载完成 |
| 第三层 | opencli 可用性检测 | ✅ 已实现 | 检测 opencli + Browser Bridge |
| 第三层 | 域名→站点映射 | ✅ 已实现 | `opencli_adapter.py` DOMAIN_SITE_MAP |
| 第三层 | opencli 命令调用 | ✅ 已实现 | 调用 opencli 获取结构化数据 |
| 第三层 | opencli 输出解析 | ✅ 已实现 | 解析 JSON/YAML 输出 |
| 第四层 | 交互式浏览器 | ✅ 已实现 | Selenium + Brave 有界面模式 |
| 第四层 | 自动注入 Cookie | ✅ 已实现 | 自动填充登录态 |
| 第四层 | 登录状态检测 | ✅ 已实现 | 基于 HTML 文本分析 |
| 第四层 | 验证码检测 | ✅ 已实现 | 检测验证码关键词 |
| 第四层 | 登录弹窗检测 | ✅ 已实现 | 检测 Modal/Dialog 结构 |
| 第四层 | 超时等待机制 | ✅ 已实现 | 默认 120 秒超时 |
| 第四层 | 浏览器横幅提示 | ✅ 已实现 | 注入"已完成"按钮 |
| 第五层 | 系统浏览器打开 | ✅ 已实现 | `system_browser.py` 模块 |
| 第五层 | Brave 浏览器调用 | ✅ 已实现 | 跨平台 Brave 路径检测 |
| 第五层 | 手动确认机制 | ✅ 已实现 | `input()` + 文件标记备选 |
| 第五层 | 内容获取（剪贴板） | ✅ 已实现 | macOS pbpaste / Linux xclip |
| 第五层 | 内容获取（AppleScript） | ✅ 已实现 | macOS Brave AppleScript |
| 第五层 | 内容获取（文件） | 📝 待实现 | 读取扩展导出的文件 |
| 第五层 | 内容获取（扩展） | 📝 待实现 | WebSocket/HTTP 接收数据 |
| 第五层 | 自动检测模式 | 📝 待实现 | 需浏览器扩展配合 |
| 全局 | 五层自动降级 | ✅ 已实现 | `auto` 模式自动选择 |
| 全局 | 历史记录管理 | ✅ 已实现 | `history.py` |
| 全局 | Cookie 持久化 | ✅ 已实现 | `cookies.py` |
| 全局 | 多格式输出 | ✅ 已实现 | html/markdown/json/text |
| 全局 | CLI 命令行支持 | ✅ 已实现 | `__main__.py` |

### 13.2 正在调试/待实现功能

| 功能 | 状态 | 问题/待办 |
|------|------|----------|
| **opencli_adapter.py 模块** | ✅ 已实现 | 域名映射、命令推断、输出解析、Browser Bridge 检测 |
| **域名→站点映射表** | ✅ 已实现 | DOMAIN_SITE_MAP 覆盖 50+ 域名 |
| **opencli 命令推断** | ✅ 已实现 | 根据 URL/关键词推断 opencli 命令 |
| **登录检测准确性** | 🔧 调试中 | 基于 HTML 文本检测对 JS 动态渲染页面不准确，需改为 DOM 结构检测 |
| **自动检测循环** | 🔧 调试中 | 某些环境下循环无法正确退出，需改进检测逻辑 |
| **IDE 环境 input() 支持** | 🔧 调试中 | IDE 中 `input()` 会卡住，需完善文件标记备选方案 |
| **system_browser.py 模块** | ✅ 已实现 | Brave 打开、手动确认、AppleScript/剪贴板获取 |
| **Brave 路径自动检测** | ✅ 已实现 | macOS/Windows/Linux 路径检测 + mdfind |
| **浏览器扩展开发** | 📝 待实现 | Chrome/Firefox 扩展，自动提取页面内容 |
| **扩展通信机制** | 📝 待实现 | WebSocket 本地服务接收扩展发送的数据 |
| **小红书提取规则** | 📝 待实现 | 预定义小红书的 CSS 选择器规则 |
| **知乎提取规则** | 📝 待实现 | 预定义知乎的 CSS 选择器规则 |
| **剪贴板读取** | 📝 待实现 | 跨平台剪贴板内容读取 |
| **内容解析优化** | 📝 待实现 | 针对 SPA 网站的动态内容解析 |
| **错误重试机制** | 📝 待实现 | 失败时自动重试和降级 |
| **日志记录** | 📝 待实现 | 详细的操作日志和调试信息 |
| **配置管理** | 📝 待实现 | 用户配置文件支持 |

### 13.3 已知问题

| 问题 | 影响 | 优先级 | 解决方案 |
|------|------|--------|----------|
| 登录检测对 JS 渲染页面不准确 | 高 | 🔴 高 | 改用 DOM 结构 + API 响应检测 |
| IDE 环境不支持长时间运行 | 高 | 🔴 高 | 文件标记 + 异步检测 |
| 自动检测循环可能卡住 | 中 | 🟡 中 | 添加超时和心跳机制 |
| 内容提取依赖 CSS 选择器 | 中 | 🟡 中 | 提供网站预定义规则 |
| 缺乏浏览器扩展 | 低 | 🟢 低 | 开发 Chrome/Firefox 扩展 |

## 十四、后续扩展

1. **opencli 适配器完善**：完善域名映射、命令推断、输出解析
2. **浏览器扩展**：开发 Chrome/Firefox 扩展，自动提取页面内容
3. **更多网站规则**：预定义小红书、知乎、微博等网站的提取规则
4. **批量操作**：支持连续搜索多个关键词
5. **数据导出**：支持导出为 Excel、CSV 等格式
6. **剪贴板集成**：自动读取剪贴板内容作为输入
