# Web-Browse Skill V2 需求文档

## 一、Skill 定位

**Web-Browse Skill** 是一个通用网页内容获取工具，支持从静态页面到需要人工登录的复杂网站的内容获取。

### V2 版本新增

在原有**三层架构**基础上，增加**第四层：系统浏览器人工交互模式**，专门解决以下场景：
- 网站反自动化检测严格（如小红书）
- 用户已有浏览器登录态，希望复用
- 需要人工操作后才能获取内容

## 二、四层架构设计

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
│  第三层：interactive (Selenium + Brave)                              │
│  Selenium 驱动 Brave 浏览器，自动注入 Cookies，自动检测登录状态         │
│  使用独立的 Brave 实例，与用户系统浏览器隔离                            │
└─────────────────────────┬───────────────────────────────────────────┘
                          │ 失败/被反检测/需要真实浏览器环境
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  第四层：system_browser (新增)                                       │
│  使用系统默认浏览器，复用用户已有登录态，人工操作后获取内容            │
└─────────────────────────────────────────────────────────────────────┘
```

## 三、第四层：system_browser 模式详解

### 3.1 设计目标

1. **绕过反自动化检测**：使用用户日常使用的浏览器，避免被检测
2. **复用登录态**：直接使用用户已有的 Cookie/Session
3. **人机协作**：用户负责操作（登录、搜索、导航），Skill 负责提取内容
4. **灵活等待**：支持自动检测和手动确认两种等待方式
5. **浏览器隔离**：第三层和第四层使用独立的 Brave 浏览器，不干扰用户个人浏览器

### 3.2 交互流程

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

### 3.3 浏览器打开方式

**重要：第三层和第四层统一使用 Brave 浏览器**

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
        # 使用已安装的 Brave 浏览器
        brave_path = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        if os.path.exists(brave_path):
            subprocess.Popen([brave_path, url])
        else:
            # 回退到 open 命令（可能打开其他浏览器）
            subprocess.Popen(["open", "-a", "Brave Browser", url])
    elif system == "Windows":
        # Windows 上的 Brave 路径
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

### 3.4 内容获取方案

| 方案 | 原理 | 优先级 | 适用场景 |
|------|------|--------|----------|
| **A. 浏览器扩展** | 扩展提取 DOM 数据，通过 WebSocket 发送 | ⭐ 首选 | 用户已安装扩展 |
| **B. 剪贴板** | 用户复制内容，Skill 读取剪贴板 | 备选 | 简单文本内容 |
| **C. 文件导出** | 扩展导出 JSON 文件，Skill 读取 | 备选 | 大量数据 |
| **D. 手动输入** | 用户直接粘贴内容到终端 | 保底 | 任何场景 |

### 3.5 等待用户完成的机制

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
        # 自动检测：通过扩展或文件标记
        return _wait_with_auto_detection(timeout)
    else:
        # 手动确认：用户按 Enter 或创建标记文件
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

## 四、接口设计（V2 更新）

### 4.1 新增参数

```python
def smart_fetch(
    url: str,
    mode: str = "auto",           # 新增: "system_browser"
    output_format: str = "html",  # "html" | "markdown" | "json" | "text"
    timeout: int = 30,
    # 新增参数:
    system_browser_mode: str = "manual",  # "manual" | "auto"
    keyword: str = None,                   # 搜索关键词（可选）
    extract_rules: dict = None            # 内容提取规则（可选）
) -> dict:
```

### 4.2 调用示例

```python
from skills.web_browse import smart_fetch

# 自动模式（四层自动降级）
result = smart_fetch("https://www.xiaohongshu.com/search_result?keyword=小升初")

# 指定 system_browser 模式
result = smart_fetch(
    url="https://www.xiaohongshu.com",
    mode="system_browser",
    keyword="小升初",
    system_browser_mode="manual",  # 手动确认
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
    "mode_used": "system_browser",
    "url": "https://...",
    "title": "页面标题"
}
```

### 4.3 CLI 用法

```bash
# 自动模式
python -m skills.web_browse "https://www.xiaohongshu.com/search_result?keyword=小升初"

# 指定 system_browser 模式
python -m skills.web_browse "https://www.xiaohongshu.com" \
    --mode system_browser \
    --keyword "小升初" \
    --system-browser-mode manual \
    --format json
```

## 五、文件结构更新

```
skills/web-browse/                    # 现有结构
├── skill.json                        # 更新: 添加 system_browser 模式
├── __init__.py                       # 导出 smart_fetch
├── __main__.py                       # CLI 入口
├── core/
│   ├── __init__.py
│   ├── fetcher.py                    # 更新: 添加 system_browser 调度逻辑
│   ├── detector.py                   # 现有: 登录检测
│   ├── history.py                    # 现有: 历史记录
│   ├── cookies.py                    # 现有: Cookie 管理
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

## 六、核心模块设计

### 6.1 system_browser.py

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
        final_url = f"{url}?keyword={keyword}'"
    
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

## 七、与现有代码的整合

### 7.1 fetcher.py 更新

在 `smart_fetch` 函数的调度逻辑中，添加 `system_browser` 模式：

```python
def smart_fetch(url: str, mode: str = "auto", output_format: str = "html", 
                timeout: int = 30, **kwargs) -> Dict[str, Any]:
    
    # ... 现有逻辑 ...
    
    # 第四层：system_browser
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

### 7.2 skill.json 更新

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
      "enum": ["auto", "web_fetch", "headless", "interactive", "system_browser"],
      "description": "获取模式：auto=自动选择（默认），system_browser=系统浏览器人工交互",
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
      "description": "搜索关键词（可选，用于 system_browser 模式）",
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

## 八、使用场景示例

### 8.1 小红书搜索

```python
from skills.web_browse import smart_fetch

# 自动模式：四层自动降级
result = smart_fetch(
    "https://www.xiaohongshu.com/search_result?keyword=小升初",
    mode="auto"
)

# 指定 system_browser 模式
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

### 8.2 知乎热榜

```python
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

## 九、浏览器隔离说明

### 9.1 为什么使用 Brave 而非系统默认浏览器

| 对比项 | 系统默认浏览器（Chrome/Safari/Edge） | Brave 浏览器（推荐） |
|--------|-------------------------------------|---------------------|
| **登录态** | 复用用户个人登录态 | 独立的登录态 |
| **Cookie 隔离** | 与用户个人 Cookie 混合 | 完全隔离 |
| **隐私** | Agent 操作会留下历史记录 | 无痕模式，不保留历史 |
| **反检测** | 容易被网站识别为自动化工具 | 真实浏览器，更难检测 |
| **干扰用户** | 会打断用户当前浏览 | 完全独立，不影响用户 |

### 9.2 三层 vs 四层浏览器使用

| 层级 | 浏览器 | 说明 |
|------|--------|------|
| 第一层 web_fetch | 无 | HTTP 请求 |
| 第二层 headless | Brave（无头模式） | Selenium 控制，无界面 |
| 第三层 interactive | Brave（有界面） | Selenium 控制，有界面 |
| 第四层 system_browser | Brave（有界面） | 用户手动操作 |

**所有需要浏览器的地方都使用 Brave，确保与用户个人浏览器完全隔离。**

## 十、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 用户未安装 Brave | 无法打开 | 检测并提示用户安装 |
| Brave 打开失败 | 任务失败 | 降级到 interactive 模式 |
| 用户操作超时 | 任务失败 | 合理设置超时，友好提示 |
| IDE 环境不支持 input | 手动确认失效 | 使用文件标记作为备选 |
| 内容提取失败 | 返回空结果 | 提供原始 HTML 作为备选 |

## 十一、功能实现状态

### 11.1 已实现功能

| 层级 | 功能 | 状态 | 说明 |
|------|------|------|------|
| 第一层 | HTTP 静态请求 | ✅ 已实现 | `web_fetch` 基础请求 |
| 第一层 | User-Agent 伪装 | ✅ 已实现 | 模拟浏览器请求头 |
| 第一层 | 超时控制 | ✅ 已实现 | 可配置超时时间 |
| 第二层 | 无头浏览器渲染 | ✅ 已实现 | Selenium + Brave 无头模式 |
| 第二层 | Cookie 复用 | ✅ 已实现 | 从文件读取历史 Cookie |
| 第二层 | JS 动态内容获取 | ✅ 已实现 | 等待页面加载完成 |
| 第三层 | 交互式浏览器 | ✅ 已实现 | Selenium + Brave 有界面模式 |
| 第三层 | 自动注入 Cookie | ✅ 已实现 | 自动填充登录态 |
| 第三层 | 登录状态检测 | ✅ 已实现 | 基于 HTML 文本分析 |
| 第三层 | 验证码检测 | ✅ 已实现 | 检测验证码关键词 |
| 第三层 | 登录弹窗检测 | ✅ 已实现 | 检测 Modal/Dialog 结构 |
| 第三层 | 超时等待机制 | ✅ 已实现 | 默认 120 秒超时 |
| 第三层 | 浏览器横幅提示 | ✅ 已实现 | 注入"已完成"按钮 |
| 第四层 | 系统浏览器打开 | 📝 待实现 | `system_browser.py` 模块 |
| 第四层 | Brave 浏览器调用 | 📝 待实现 | 跨平台 Brave 路径检测 |
| 第四层 | 手动确认机制 | 📝 待实现 | `input()` + 文件标记备选 |
| 第四层 | 内容获取（剪贴板） | 📝 待实现 | 读取剪贴板内容 |
| 第四层 | 内容获取（文件） | 📝 待实现 | 读取扩展导出的文件 |
| 第四层 | 内容获取（扩展） | 📝 待实现 | WebSocket/HTTP 接收数据 |
| 第四层 | 自动检测模式 | 📝 待实现 | 需浏览器扩展配合 |
| 全局 | 四层自动降级 | ✅ 已实现 | `auto` 模式自动选择 |
| 全局 | 历史记录管理 | ✅ 已实现 | `history.py` |
| 全局 | Cookie 持久化 | ✅ 已实现 | `cookies.py` |
| 全局 | 多格式输出 | ✅ 已实现 | html/markdown/json/text |
| 全局 | CLI 命令行支持 | ✅ 已实现 | `__main__.py` |

### 11.2 正在调试/待实现功能

| 功能 | 状态 | 问题/待办 |
|------|------|----------|
| **登录检测准确性** | 🔧 调试中 | 基于 HTML 文本检测对 JS 动态渲染页面不准确，需改为 DOM 结构检测 |
| **自动检测循环** | 🔧 调试中 | 某些环境下循环无法正确退出，需改进检测逻辑 |
| **IDE 环境 input() 支持** | 🔧 调试中 | IDE 中 `input()` 会卡住，需完善文件标记备选方案 |
| **system_browser.py 模块** | 📝 待实现 | 需创建完整的第四层实现代码 |
| **Brave 路径自动检测** | 📝 待实现 | macOS/Windows/Linux 的 Brave 安装路径检测 |
| **浏览器扩展开发** | 📝 待实现 | Chrome/Firefox 扩展，自动提取页面内容 |
| **扩展通信机制** | 📝 待实现 | WebSocket 本地服务接收扩展发送的数据 |
| **小红书提取规则** | 📝 待实现 | 预定义小红书的 CSS 选择器规则 |
| **知乎提取规则** | 📝 待实现 | 预定义知乎的 CSS 选择器规则 |
| **剪贴板读取** | 📝 待实现 | 跨平台剪贴板内容读取 |
| **内容解析优化** | 📝 待实现 | 针对 SPA 网站的动态内容解析 |
| **错误重试机制** | 📝 待实现 | 失败时自动重试和降级 |
| **日志记录** | 📝 待实现 | 详细的操作日志和调试信息 |
| **配置管理** | 📝 待实现 | 用户配置文件支持 |

### 11.3 已知问题

| 问题 | 影响 | 优先级 | 解决方案 |
|------|------|--------|----------|
| 登录检测对 JS 渲染页面不准确 | 高 | 🔴 高 | 改用 DOM 结构 + API 响应检测 |
| IDE 环境不支持长时间运行 | 高 | 🔴 高 | 文件标记 + 异步检测 |
| 自动检测循环可能卡住 | 中 | 🟡 中 | 添加超时和心跳机制 |
| 内容提取依赖 CSS 选择器 | 中 | 🟡 中 | 提供网站预定义规则 |
| 缺乏浏览器扩展 | 低 | 🟢 低 | 开发 Chrome/Firefox 扩展 |

## 十二、后续扩展

1. **浏览器扩展**：开发 Chrome/Firefox 扩展，自动提取页面内容
2. **更多网站规则**：预定义小红书、知乎、微博等网站的提取规则
3. **批量操作**：支持连续搜索多个关键词
4. **数据导出**：支持导出为 Excel、CSV 等格式
5. **剪贴板集成**：自动读取剪贴板内容作为输入
