#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brave 浏览器 WebDriver 封装

环境准备：
1. 安装 Python 依赖：
   pip install selenium webdriver-manager -i https://pypi.tuna.tsinghua.edu.cn/simple

2. 安装 Brave 浏览器：
   https://github.com/brave/brave-browser/releases

3. 安装 WebDriver：
   https://googlechromelabs.github.io/chrome-for-testing/#stable
   下载与 Brave 浏览器版本匹配的 ChromeDriver
"""

import os
import json
import atexit
import tempfile
from typing import Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Brave 浏览器和 ChromeDriver 路径配置
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROMEDRIVER_PATH = os.path.expanduser("~/chromedriver-mac-arm64/chromedriver")

# 全局单例：同一时间只允许一个 WebDriver 控制的 Brave 进程
_active_driver: Optional[webdriver.Chrome] = None


def _cleanup_active_driver():
    """安全关闭当前活跃的 driver（进程退出时自动调用）"""
    global _active_driver
    if _active_driver is not None:
        try:
            _active_driver.quit()
        except Exception:
            pass
        _active_driver = None


# 注册退出清理
atexit.register(_cleanup_active_driver)


def _disable_brave_p3a_popup(user_data_dir: str):
    """
    在 Brave 启动前，预写 Local State 文件以禁用 P3A 隐私分析弹窗。

    Brave 在启动时读取 user-data-dir 中的 Local State 文件，
    检查 brave_stats.reporting_enabled 是否为 true 来决定是否弹出提示。
    提前写入 false 即可跳过弹窗。
    """
    from pathlib import Path

    local_state_path = Path(user_data_dir) / "Local State"
    if local_state_path.exists():
        # 如果文件已存在（使用持久化 user_data_dir），追加/覆盖 P3A 设置
        try:
            existing = json.loads(local_state_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    else:
        existing = {}

    # 覆盖 Brave 隐私分析相关配置（兼容新旧键名）
    existing.setdefault("browser", {})
    existing.setdefault("brave", {})
    existing["brave"].setdefault("stats", {})["reporting_enabled"] = False
    # 新版本 Brave 使用 p3a 键
    existing.setdefault("p3a", {})["enabled"] = False

    # 确保目录存在并写入
    local_state_path.parent.mkdir(parents=True, exist_ok=True)
    local_state_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def create_driver(headless: bool = False, user_data_dir: str = None) -> webdriver.Chrome:
    """
    创建 Brave WebDriver 实例（单例模式：如已有活跃 driver 则先关闭再创建）

    Args:
        headless: 是否无头模式
        user_data_dir: 用户数据目录（复用登录状态）

    Returns:
        webdriver.Chrome 实例
    """
    global _active_driver

    # 如果已有活跃 driver，先关闭
    if _active_driver is not None:
        print("[brave_driver] 检测到已有活跃浏览器进程，先关闭旧进程...")
        try:
            _active_driver.quit()
        except Exception as e:
            print(f"[brave_driver] 关闭旧进程时出错（忽略）: {e}")
        finally:
            _active_driver = None
        print("[brave_driver] 旧进程已关闭")

    options = Options()
    options.binary_location = BRAVE_PATH

    # 基础配置
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")

    if headless:
        options.add_argument("--headless=new")

    # ── 用户数据目录 + Brave P3A 弹窗禁用 ──
    _temp_data_dir = None
    if not user_data_dir:
        _temp_data_dir = tempfile.mkdtemp(prefix="brave_profile_")
        user_data_dir = _temp_data_dir

    # 在 Brave 启动前，预写 Local State 文件以禁用 P3A 隐私分析弹窗
    _disable_brave_p3a_popup(user_data_dir)

    options.add_argument(f"--user-data-dir={user_data_dir}")

    # User-Agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")

    # 隐藏自动化特征
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    # 隐藏 webdriver 属性
    driver.execute_cdp_cmd(
        'Page.addScriptToEvaluateOnNewDocument',
        {'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'}
    )

    _active_driver = driver
    return driver


def get_active_driver() -> Optional[webdriver.Chrome]:
    """获取当前活跃的 driver 实例（可能为 None）"""
    return _active_driver


def quit_active_driver():
    """显式关闭活跃 driver"""
    _cleanup_active_driver()
