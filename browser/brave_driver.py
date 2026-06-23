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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Brave 浏览器和 ChromeDriver 路径配置
BRAVE_PATH = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROMEDRIVER_PATH = os.path.expanduser("~/chromedriver-mac-arm64/chromedriver")


def create_driver(headless: bool = False, user_data_dir: str = None) -> webdriver.Chrome:
    """
    创建 Brave WebDriver 实例
    
    Args:
        headless: 是否无头模式
        user_data_dir: 用户数据目录（复用登录状态）
    
    Returns:
        webdriver.Chrome 实例
    """
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
    
    return driver
