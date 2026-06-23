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
import atexit
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
    # 禁用 Brave P3A 隐私分析弹窗
    options.add_argument("--disable-brave-stats-updater")

    if headless:
        options.add_argument("--headless=new")

    # 用户数据目录（复用 profile/cookies）
    if user_data_dir:
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
