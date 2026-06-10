import sys
import os
import json
import logging
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agent.auto_submit import load_credentials_from_arch, format_code_for_xno

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SMA_CODE = """
class CustomStrategy(SimpleAlgorithm):
    def __algorithm__(self):
        close = self.data.pv_close
        sma = self.feat.sma(close, timeperiod=10)
        long_zone = close > sma
        short_zone = ~long_zone
        self.set_positions(long_zone, position=1.0)
        self.set_positions(short_zone, position=-1.0)
"""

def submit_and_check():
    captured_responses = []

    def handle_response(response):
        url = response.url
        try:
            if "xnoquant.io" in url and "json" in response.headers.get("content-type", ""):
                try:
                    data = response.json()
                    captured_responses.append({
                        "url": url,
                        "data": data
                    })
                except:
                    pass
        except:
            pass

    with sync_playwright() as p:
        logger.info("Connecting to Chrome...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("response", handle_response)

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
            page.goto("https://alpha.xnoquant.io/build")
            page.wait_for_timeout(2000)

        # Wait for page to load
        page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=15000)

        logger.info("Adding new strategy tab...")
        page.evaluate("() => document.querySelector('button.shrink-0.w-14.border-r').click()")
        page.wait_for_timeout(1500)

        logger.info("Waiting for Monaco Editor to initialize...")
        page.wait_for_function("() => typeof monaco !== 'undefined' && monaco.editor && monaco.editor.getModels().length > 0", timeout=15000)

        logger.info("Setting Monaco Editor content...")
        escaped_code = format_code_for_xno(SMA_CODE)
        escaped_code = escaped_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        page.evaluate(f"monaco.editor.getModels()[0].setValue(`{escaped_code}`)")
        page.wait_for_timeout(1000)

        logger.info("Configuring settings for VN30F1M-10MIN...")
        page.evaluate("""async (targetUniv) => {
            let settingsBtn = document.getElementById('onboarding-settings-btn');
            settingsBtn.click();
            const wait = ms => new Promise(r => setTimeout(r, ms));
            await wait(500);
            let dialog = document.querySelector('[role="dialog"]');
            let buttons = Array.from(dialog.querySelectorAll('button'));
            
            // Market
            let marketBtn = buttons.find(b => b.textContent.includes('Crypto Spot') || b.textContent.includes('Vietnam Future') || b.textContent.includes('Vietnam Stock'));
            if (marketBtn && !marketBtn.textContent.includes('Vietnam Future')) {
                marketBtn.click();
                await wait(500);
                let divs = Array.from(document.querySelectorAll('div, button, span'));
                let targetMarket = divs.find(d => d.textContent.trim() === 'Vietnam Future');
                if (targetMarket) targetMarket.click();
                await wait(500);
            }
            
            // Universe
            buttons = Array.from(dialog.querySelectorAll('button'));
            let universeBtn = buttons.find(b => b.textContent.includes('VN30F1M') || b.textContent.includes('TOP10'));
            if (universeBtn && !universeBtn.textContent.includes(targetUniv)) {
                universeBtn.click();
                await wait(500);
                let divs = Array.from(document.querySelectorAll('div, button, span'));
                let targetOption = divs.find(d => d.textContent.trim() === targetUniv);
                if (targetOption) targetOption.click();
                await wait(500);
            }
            
            // Save
            buttons = Array.from(dialog.querySelectorAll('button'));
            let saveBtn = buttons.find(b => b.textContent.trim() === 'Save');
            if (saveBtn) saveBtn.click();
        }""", "VN30F1M-10MIN")
        page.wait_for_timeout(2000)

        logger.info("Running simulation...")
        page.evaluate("() => document.getElementById('onboarding-simulate-btn').click()")

        # Poll status
        start_time = time.time()
        while time.time() - start_time < 90:
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
            logger.info(f"Status: {status_text}")
            if status_text.lower() in ["completed", "published", "failed", "error"]:
                break
            time.sleep(3)

        # Get strategy ID
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
        
        if not strategy_ids:
            logger.error("Failed to get strategy ID.")
            return

        strategy_id = strategy_ids[0]
        logger.info(f"Strategy ID: {strategy_id}")

        # Navigate to Details
        details_url = f"https://alpha.xnoquant.io/list?strategyId={strategy_id}&stage=train"
        page.goto(details_url)
        page.wait_for_timeout(5000)

        # Print performance data from captured responses
        for resp in captured_responses:
            if "stages/train/performance" in resp["url"]:
                perf = resp["data"]["data"]
                print("\n=== XNOQuant Web backtest results for SMA10 SAR (10m) ===")
                print(json.dumps(perf, indent=2))

        page.close()
        browser.close()

if __name__ == "__main__":
    submit_and_check()
