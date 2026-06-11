import time
from playwright.sync_api import sync_playwright

def get_submitted_strategies():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("Logging in...")
        page.goto("https://alpha.xnoquant.io/build")
        page.wait_for_timeout(3000)
        
        if page.locator("input[type='password']").count() > 0:
            page.fill("input[type='text']", "toinguyen15102004@gmail.com")
            page.fill("input[type='password']", "anhtrung15102004")
            page.click("button:has-text('Login')")
            page.wait_for_timeout(3000)
            
        print("Going to Strategy List...")
        page.goto("https://alpha.xnoquant.io/list?stage=train")
        try:
            page.wait_for_selector("table", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        
        print("Extracting strategies...")
        text = page.locator("body").inner_text()
        with open('strategies_list.txt', 'w', encoding='utf-8') as f:
            f.write(text)
        
        browser.close()

if __name__ == "__main__":
    get_submitted_strategies()
