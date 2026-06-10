import sys
import os
import logging
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STRATEGY_ID = "v6qikQeZN1"

def find_all_tabs():
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

        details_url = f"https://alpha.xnoquant.io/list?strategyId={STRATEGY_ID}&stage=simulate"
        logger.info(f"Navigating to Details: {details_url}")
        page.goto(details_url)
        page.wait_for_timeout(5000)

        # Let's find all text on the page to identify tabs
        text_elements = page.evaluate("""() => {
            let divs = Array.from(document.querySelectorAll('div, button, span, a'));
            return divs.map(d => d.textContent.trim()).filter(t => t.length > 0 && t.length < 50);
        }""")
        
        # Deduplicate
        unique_texts = sorted(list(set(text_elements)))

        # Find possible tabs
        tabs = page.evaluate("""() => {
            let els = Array.from(document.querySelectorAll('*'));
            return els.filter(el => {
                let style = window.getComputedStyle(el);
                let hasTabClass = Array.from(el.classList).some(c => c.toLowerCase().includes('tab'));
                return style.cursor === 'pointer' && (hasTabClass || el.textContent.length < 30);
            }).map(el => el.textContent.trim()).filter(t => t.length > 0 && t.length < 40);
        }""")
        unique_tabs = sorted(list(set(tabs)))

        out_path = "scratch/all_tabs_output.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("=== All short text snippets ===\n")
            for t in unique_texts:
                f.write(f"- {t}\n")
            f.write("\n=== Clickable elements / tabs ===\n")
            for t in unique_tabs:
                f.write(f"- {t}\n")
                
        print(f"Results written to {out_path}")

        page.close()
        browser.close()

if __name__ == "__main__":
    find_all_tabs()
