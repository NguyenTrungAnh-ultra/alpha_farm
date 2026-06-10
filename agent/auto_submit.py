import re
import time
import logging
import os
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def load_credentials_from_arch() -> tuple:
    """
    Read email and password credentials from ARCH.md in the project root.
    """
    try:
        # ARCH.md is in the project root (parent directory of agent)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        arch_path = os.path.join(project_root, "ARCH.md")
        account = None
        password = None
        if os.path.exists(arch_path):
            with open(arch_path, 'r', encoding='utf-8') as f:
                content = f.read()
                acc_match = re.search(r"account:\s*(\S+)", content)
                pwd_match = re.search(r"password:\s*(\S+)", content)
                if acc_match:
                    account = acc_match.group(1).strip()
                if pwd_match:
                    password = pwd_match.group(1).strip()
        return account, password
    except Exception as e:
        logger.error(f"[AutoSubmit] Failed to load credentials from ARCH.md: {e}")
        return None, None


def inject_params_to_code(code: str, params: dict) -> str:
    """
    Replace default parameter values inside __algorithm__ with optimized values.
    """
    if not params:
        return code
    new_code = code
    for name, val in params.items():
        pattern = rf"\b{name}\s*=\s*[\w\.\-\[\]'\"]+"
        replacement = f"{name} = {repr(val)}"
        new_code = re.sub(pattern, replacement, new_code)
    return new_code

def format_code_for_xno(code: str, params: dict = None) -> str:
    """
    Format the strategy code to comply with XNOQuant rules:
    1. Strip all lines starting with import or from.
    2. Rename the strategy class to CustomStrategy.
    3. Strip the __init__ method entirely.
    4. Replace getattr(self, 'param', default) with the actual parameter value.
    5. Clean up any unallowed numpy (np) and pandas (pd) references.
    """
    # 1. Strip imports
    lines = code.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        clean_lines.append(line)
        
    clean_code = "\n".join(clean_lines)
    
    # 2. Rename class definition to CustomStrategy
    pattern_class = r"class\s+(\w+)\s*\(\s*SimpleAlgorithm\s*\)\s*:"
    clean_code = re.sub(pattern_class, "class CustomStrategy(SimpleAlgorithm):", clean_code)
    
    # 3. Strip __init__ method entirely (from def __init__ up to def __algorithm__)
    init_pattern = r"def\s+__init__\s*\([\s\S]+?def\s+__algorithm__\s*\(\s*self\s*\)\s*:"
    if re.search(init_pattern, clean_code):
        clean_code = re.sub(init_pattern, "def __algorithm__(self):", clean_code)
        
    # 4. Replace getattr parameter expressions or inject self.param = value
    if params:
        remaining_params = params.copy()
        for name, val in params.items():
            pattern = rf"getattr\(\s*self\s*,\s*['\"]{name}['\"]\s*,\s*[^)]+\)"
            if re.search(pattern, clean_code):
                clean_code = re.sub(pattern, repr(val), clean_code)
                remaining_params.pop(name)
                
        # If any parameters were not replaced, inject them at the top of __algorithm__
        if remaining_params:
            assignments = []
            for name, val in remaining_params.items():
                assignments.append(f"        self.{name} = {repr(val)}")
            assignments_str = "\n".join(assignments)
            clean_code = clean_code.replace("def __algorithm__(self):", f"def __algorithm__(self):\n{assignments_str}\n")
        
    # 5. Clean up np/pd references to only use Series methods
    clean_code = re.sub(
        r"pd\.Series\(\s*np\.where\(\s*(\w+),\s*(\w+),\s*np\.nan\s*\),\s*index\s*=\s*\w+\.index\s*\)\.ffill\(\)",
        r"\2.where(\1).ffill()",
        clean_code
    )
    clean_code = re.sub(
        r"pd\.Series\(\s*np\.where\(\s*(\w+),\s*(\w+),\s*np\.nan\s*\),\s*index\s*=\s*\w+\.index\s*\)",
        r"\2.where(\1)",
        clean_code
    )
    
    return clean_code

def run_auto_submit(strategy_code: str, timeframe: str = "15m", params: dict = None, timeout_seconds: int = 300) -> bool:
    """
    Automate strategy creation, simulation, and submission on XNOQuant via Playwright CDP.
    
    Parameters
    ----------
    strategy_code : str
        The strategy python code.
    timeframe : str
        Timeframe (e.g. "1m", "5m", "10m", "15m", "30m", "60m").
    timeout_seconds : int
        Max wait time for simulation.
        
    Returns
    ----------
    bool
        True if successfully submitted, False otherwise.
    """
    strategy_code = format_code_for_xno(strategy_code, params)

    
    timeframe_map = {
        "1m": "VN30F1M-01MIN",
        "3m": "VN30F1M-03MIN",
        "5m": "VN30F1M-05MIN",
        "10m": "VN30F1M-10MIN",
        "15m": "VN30F1M-15MIN",
        "30m": "VN30F1M-30MIN",
        "60m": "VN30F1M-60MIN"
    }
    
    target_universe = timeframe_map.get(timeframe.lower())
    if not target_universe:
        logger.error(f"[AutoSubmit] Invalid timeframe: {timeframe}")
        return False
        
    try:
        with sync_playwright() as p:
            browser = None
            try:
                logger.info("[AutoSubmit] Connecting to Chrome CDP on localhost:9222...")
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = context.new_page()
                logger.info("[AutoSubmit] Navigating to build page...")
                page.goto("https://alpha.xnoquant.io/build")
                page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=5000)
            except Exception as cdp_err:
                logger.warning(f"[AutoSubmit] CDP connection failed or not logged in: {cdp_err}. Launching local browser instead...")
                if browser:
                    try:
                        browser.close()
                    except:
                        pass
                
                # Launch a new Chromium browser
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Load credentials from ARCH.md
                account, password = load_credentials_from_arch()
                if not account or not password:
                    logger.error("[AutoSubmit] Could not find account credentials in ARCH.md")
                    return False
                
                logger.info("[AutoSubmit] Navigating to build page...")
                page.goto("https://alpha.xnoquant.io/build")
                page.wait_for_timeout(3000)
                
                if "dang-nhap" in page.url or page.locator("input[type='password']").count() > 0:
                    logger.info("[AutoSubmit] Login page detected. Performing automated login...")
                    page.fill("input[type='text']", account)
                    page.fill("input[type='password']", password)
                    page.click("button:has-text('Login')")
                    page.wait_for_timeout(3000)
                    
                    logger.info("[AutoSubmit] Navigating back to build page after login...")
                    page.goto("https://alpha.xnoquant.io/build")
                    page.wait_for_timeout(2000)
                
                # Wait for page to load
                page.wait_for_selector("button.shrink-0.w-14.border-r", timeout=15000)
            
            logger.info("[AutoSubmit] Adding new strategy tab...")
            page.evaluate("() => document.querySelector('button.shrink-0.w-14.border-r').click()")
            page.wait_for_timeout(1500)
            
            logger.info("[AutoSubmit] Setting Monaco Editor content...")
            escaped_code = strategy_code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
            page.evaluate(f"monaco.editor.getModels()[0].setValue(`{escaped_code}`)")
            page.wait_for_timeout(500)
            
            logger.info(f"[AutoSubmit] Configuring settings for {target_universe}...")
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
            }""", target_universe)
            
            logger.info(f"[AutoSubmit] {config_result}")
            page.wait_for_timeout(1000)
            
            logger.info("[AutoSubmit] Running simulation...")
            page.evaluate("() => document.getElementById('onboarding-simulate-btn').click()")
            
            # Poll status
            logger.info("[AutoSubmit] Polling simulation status...")
            start_time = time.time()
            sim_success = False
            
            while time.time() - start_time < timeout_seconds:
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
                
                logger.info(f"[AutoSubmit] Status: {status_text}")
                if status_text.lower() == "published":
                    sim_success = True
                    break
                elif status_text.lower() == "completed":
                    logger.error("[AutoSubmit] Simulation completed but did not publish (failed metrics).")
                    page.close()
                    return False
                elif status_text.lower() in ["failed", "error"]:
                    logger.error("[AutoSubmit] Simulation failed (compilation/runtime error).")
                    page.close()
                    return False
                
                time.sleep(5)
                
            if not sim_success:
                logger.error("[AutoSubmit] Simulation timed out or failed to publish.")
                page.close()
                return False
                
            # Get strategy ID from localStorage (find the newest editor state)
            logger.info("[AutoSubmit] Fetching Strategy ID from localStorage...")
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
                    if (newestId) {
                        return editorStates[newestId].editor.strategy_ids;
                    }
                    return [];
                } catch(e) {
                    return [];
                }
            }""")
            
            if not strategy_ids:
                logger.error("[AutoSubmit] Failed to get strategy ID from localStorage.")
                page.close()
                return False
                
            strategy_id = strategy_ids[0]
            logger.info(f"[AutoSubmit] Strategy ID found: {strategy_id}")

            
            # Navigate to Details View
            details_url = f"https://alpha.xnoquant.io/list?strategyId={strategy_id}&stage=train"
            logger.info(f"[AutoSubmit] Navigating to Details URL: {details_url}")
            page.goto(details_url)
            page.wait_for_timeout(2000)
            
            # Click three-dots menu in details panel
            logger.info("[AutoSubmit] Clicking details action menu...")
            page.wait_for_selector('button[aria-haspopup="menu"].size-8')
            page.click('button[aria-haspopup="menu"].size-8')
            page.wait_for_timeout(1000)
            
            # Click Submit Alpha
            logger.info("[AutoSubmit] Clicking Submit Alpha...")
            submit_item_selector = 'div[role="menuitem"]:has-text("Submit Alpha")'
            try:
                page.wait_for_selector(submit_item_selector, timeout=5000)
                page.click(submit_item_selector)
            except Exception as e:
                logger.error("[AutoSubmit] Submit Alpha option not found in menu or timed out.")
                page.close()
                return False
                
            page.wait_for_timeout(1500)
            
            # Click competition selection and confirm
            logger.info("[AutoSubmit] Confirming VQC 2026 event submission...")
            try:
                comp_selector = 'button:has-text("Data Science Talent Competition")'
                page.wait_for_selector(comp_selector, timeout=5000)
                page.click(comp_selector)
                page.wait_for_timeout(500)
                
                confirm_selector = 'button:has-text("Confirm submission")'
                page.wait_for_selector(confirm_selector, timeout=5000)
                page.click(confirm_selector)
                page.wait_for_timeout(1000)
                submission_result = 'Submitted'
            except Exception as e:
                logger.error(f"[AutoSubmit] Failed during confirmation: {e}")
                page.close()
                return False
            
            logger.info(f"[AutoSubmit] Result: {submission_result}")
            page.close()
            return submission_result == 'Submitted'
            
    except Exception as e:
        logger.error(f"[AutoSubmit] Error: {e}")
        return False
