import sys
import os
import json
import logging
import time
from playwright.sync_api import sync_playwright

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.auto_submit import load_credentials_from_arch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PROBE_CODE = """
class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        is_first_bar = self.op.isna(self.op.shift(close, 1))
        index_series = self.op.bars_since(is_first_bar)
        
        # We hold position 1.0 from index 100 to 105
        mask = (index_series >= 100) & (index_series <= 105)
        self.set_positions(mask, position=1.0)
"""

def run_probe():
    captured_responses = []

    def handle_response(response):
        url = response.url
        try:
            # We want to capture JSON responses from XNOQuant backend
            if "xnoquant.io" in url and "json" in response.headers.get("content-type", ""):
                try:
                    data = response.json()
                    captured_responses.append({
                        "url": url,
                        "data": data
                    })
                    logger.info(f"Captured JSON response from: {url}")
                except Exception as e:
                    pass
        except Exception:
            pass

    with sync_playwright() as p:
        logger.info("Connecting to Chrome CDP on localhost:9222...")
        browser = None
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            logger.info("Connected to existing browser context.")
        except Exception as e:
            logger.warning(f"Failed to connect to CDP: {e}. Launching a new headless browser...")
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()

        page = context.new_page()
        page.on("response", handle_response)

        # Load credentials
        account, password = load_credentials_from_arch()
        if not account or not password:
            logger.error("Could not find account credentials in ARCH.md")
            return

        logger.info("Navigating to build page...")
        page.goto("https://alpha.xnoquant.io/build")
        page.wait_for_timeout(3000)

        if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
            logger.info("Login page detected. Performing automated login...")
            page.fill("input[type='text']", account)
            page.fill("input[type='password']", password)
            page.click("button:has-text('Login')")
            page.wait_for_timeout(3000)
            page.goto("https://alpha.xnoquant.io/build")
            page.wait_for_timeout(2000)

        # Wait for page to load
        page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=15000)

        logger.info("Adding new strategy tab...")
        page.evaluate("() => document.querySelector('button.shrink-0.w-14.border-r').click()")
        page.wait_for_timeout(1500)

        logger.info("Setting Monaco Editor content...")
        escaped_code = PROBE_CODE.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        page.evaluate(f"monaco.editor.getModels()[0].setValue(`{escaped_code}`)")
        page.wait_for_timeout(1000)

        logger.info("Configuring settings for VN30F1M-10MIN...")
        config_result = page.evaluate("""async (targetUniv) => {
            let settingsBtn = document.getElementById('onboarding-settings-btn');
            if (!settingsBtn) throw new Error('Settings button not found');
            settingsBtn.click();
            
            const wait = ms => new Promise(r => setTimeout(r, ms));
            await wait(500);
            
            let dialog = document.querySelector('[role="dialog"]');
            if (!dialog) throw new Error('Settings dialog not found');
            
            let buttons = Array.from(dialog.querySelectorAll('button'));
            
            // Click Market
            let marketBtn = buttons.find(b => b.textContent.includes('Crypto Spot') || b.textContent.includes('Vietnam Future') || b.textContent.includes('Vietnam Stock'));
            if (marketBtn && !marketBtn.textContent.includes('Vietnam Future')) {
                marketBtn.click();
                await wait(500);
                let divs = Array.from(document.querySelectorAll('div, button, span'));
                let targetMarket = divs.find(d => d.textContent.trim() === 'Vietnam Future');
                if (targetMarket) targetMarket.click();
                await wait(500);
            }
            
            // Refresh buttons reference
            buttons = Array.from(dialog.querySelectorAll('button'));
            
            // Click Universe
            let universeBtn = buttons.find(b => b.textContent.includes('VN30F1M') || b.textContent.includes('TOP10'));
            if (universeBtn && !universeBtn.textContent.includes(targetUniv)) {
                universeBtn.click();
                await wait(500);
                let divs = Array.from(document.querySelectorAll('div, button, span'));
                let targetOption = divs.find(d => d.textContent.trim() === targetUniv);
                if (targetOption) targetOption.click();
                await wait(500);
            }
            
            // Click Save
            buttons = Array.from(dialog.querySelectorAll('button'));
            let saveBtn = buttons.find(b => b.textContent.trim() === 'Save');
            if (saveBtn) {
                saveBtn.click();
                return 'Settings saved';
            }
            throw new Error('Save button not found');
        }""", "VN30F1M-10MIN")
        
        logger.info(f"Config Result: {config_result}")
        page.wait_for_timeout(1000)

        logger.info("Running simulation...")
        page.evaluate("() => document.getElementById('onboarding-simulate-btn').click()")

        # Poll status for 1 minute
        start_time = time.time()
        while time.time() - start_time < 60:
            status_text = page.evaluate("""() => {
                let titleEl = document.querySelector('h1.text-xl.font-semibold');
                if (!titleEl) return 'Loading';
                let toolbar = titleEl.parentElement.parentElement;
                let badges = Array.from(toolbar.querySelectorAll('span, div'));
                let statusBadge = badges.find(b => {
                    let text = b.textContent.trim().toLowerCase();
                    return ['draft', 'simulating', 'completed', 'published', 'failed', 'error'].includes(text);
                });
                return statusBadge ? statusBadge.textContent.trim() : 'Unknown';
            }""")
            
            logger.info(f"Simulation Status: {status_text}")
            if status_text.lower() in ["completed", "published", "failed", "error"]:
                break
            time.sleep(3)

        logger.info("Waiting extra time for API calls to settle...")
        page.wait_for_timeout(5000)

        # Save all captured responses to a JSON file
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "probe_captured_responses.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(captured_responses, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved captured responses to {output_path}")

        # Let's check localStorage to find the strategy ID
        strategy_ids = page.evaluate("""() => {
            try {
                const authData = JSON.parse(localStorage.getItem('auth-storage'));
                const uid = authData.state.user.uid;
                const editorStates = JSON.parse(localStorage.getItem('xno-editor-states-' + uid));
                let newestId = null;
                let newestTime = 0;
                for (let id in editorStates) {
                    let t = new Date(editorStates[id].editor.created_at).getTime();
                    if (t > newestTime) {
                        newestTime = t;
                        newestId = id;
                    }
                }
                return newestId ? editorStates[newestId].editor.strategy_ids : [];
            } catch(e) { return []; }
        }""")
        if strategy_ids:
            logger.info(f"Strategy ID: {strategy_ids[0]}")
        
        page.close()
        browser.close()

if __name__ == "__main__":
    run_probe()
