import sys
import os
import json
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def take_list_screenshot():
    with sync_playwright() as p:
        logger.info("Connecting to Chrome...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        account, password = load_credentials_from_arch()
        if not account or not password:
            logger.error("No credentials in ARCH.md")
            return

        logger.info("Logging in...")
        page.goto("https://alpha.xnoquant.io/build")
        page.wait_for_timeout(3000)
        if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
            page.fill("input[type='text']", account)
            page.fill("input[type='password']", password)
            page.click("button:has-text('Login')")
            page.wait_for_timeout(3000)

        logger.info("Navigating to List page...")
        page.goto("https://alpha.xnoquant.io/list")
        page.wait_for_timeout(6000)

        # Take screenshot
        screenshot_path = "scratch/list_page_screenshot.png"
        page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot saved to {screenshot_path}")

        # Dump HTML
        html_path = "scratch/list_page.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        logger.info(f"HTML DOM dumped to {html_path}")

        page.close()
        browser.close()

if __name__ == "__main__":
    take_list_screenshot()
