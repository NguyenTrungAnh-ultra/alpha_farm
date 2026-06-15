import os
import sys
import json
import traceback
from pathlib import Path

# Add project root to path
PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.templates import TEMPLATE_REGISTRY
from agent.ollama_client import OllamaChatClient
from agent.gemini_client import extract_json

def build_conversion_prompt(legacy_json: dict) -> str:
    templates_info = []
    for name, info in TEMPLATE_REGISTRY.items():
        params_desc = []
        for p_name, p_info in info['params'].items():
            params_desc.append(f"{p_name} ({p_info['type']}, min={p_info['low']}, max={p_info['high']}, default={p_info['default']})")
        templates_info.append(f"- **{name}**: {info['description']}\n  Expected parameters: {', '.join(params_desc)}")
    
    templates_text = "\n".join(templates_info)
    
    return f"""You are a Quant Strategy Translator.
We have a legacy trading strategy defined in JSON format:
{json.dumps(legacy_json, indent=2)}

We need to map this legacy strategy to the CLOSEST matching template from our template library.

Available Templates:
{templates_text}

CRITICAL RULES:
1. You MUST choose exactly ONE template from the list. Choose the template that matches the core trading logic the closest:
   - If it uses moving average crossovers, trend indicators, or slopes -> EmaCrossoverTemplate
   - If it uses RSI, oscillators, overbought/oversold levels, or mean reversion -> RsiMeanReversionTemplate
   - If it uses Bollinger Bands, breakouts, volatility channels, or outer bands -> BollingerBreakoutTemplate
2. Map or suggest parameters that are strictly within the Min/Max bounds of the selected template. Do not invent new parameters.
3. Respond ONLY with a valid JSON block in the target format. Do not write any explanations or other text.

Target JSON Format:
```json
{{
    "name": "{legacy_json.get('name', 'StrategyName')}",
    "timeframe": "{legacy_json.get('timeframe', '10m')}",
    "template_name": "SelectedTemplateName",
    "rationale": "Why this template is the closest fit",
    "parameters": {{
        "param_name": value
    }}
}}
```"""

def validate_converted_json(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    required_keys = ["name", "timeframe", "template_name", "parameters"]
    if not all(k in data for k in required_keys):
        return False
        
    template_name = data["template_name"]
    if template_name not in TEMPLATE_REGISTRY:
        return False
        
    template_info = TEMPLATE_REGISTRY[template_name]
    params = data["parameters"]
    if not isinstance(params, dict):
        return False
        
    # Check if all required params are present
    for p_name in template_info["params"]:
        if p_name not in params:
            return False
            
    return True

def run_conversion():
    ideas_dir = os.path.join(PROJECT_ROOT, "agent", "results", "ideas")
    if not os.path.exists(ideas_dir):
        print(f"Error: ideas directory not found at {ideas_dir}")
        return
        
    json_files = [f for f in os.listdir(ideas_dir) if f.endswith('.json')]
    print(f"Found {len(json_files)} JSON files in ideas directory.")
    
    # Filter out files that are already template-based and valid
    legacy_files = []
    for filename in json_files:
        filepath = os.path.join(ideas_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if validate_converted_json(data):
                # Already converted
                continue
            legacy_files.append(filename)
        except Exception:
            # If error reading, treat as legacy/broken
            legacy_files.append(filename)
            
    total_legacy = len(legacy_files)
    print(f"Identified {total_legacy} legacy JSON files needing conversion.")
    
    if total_legacy == 0:
        print("No legacy files to convert. Exiting.")
        return
        
    print("Initializing Ollama local model...")
    try:
        chat = OllamaChatClient(model="qwen3.5:4b", verbose=False)
    except Exception as e:
        print(f"Failed to start Ollama: {e}")
        return
        
    success_count = 0
    fail_count = 0
    
    limit = int(os.environ.get("LIMIT", 0))
    if limit > 0:
        legacy_files = legacy_files[:limit]
        total_legacy = len(legacy_files)
        print(f"Limiting conversion to the first {limit} files.")
        
    for idx, filename in enumerate(legacy_files, 1):
        filepath = os.path.join(ideas_dir, filename)
        print(f"[{idx}/{total_legacy}] Processing {filename}...")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                legacy_json = json.load(f)
                
            prompt = build_conversion_prompt(legacy_json)
            response_text = chat.send(prompt)
            converted_data = extract_json(response_text)
            
            if converted_data and validate_converted_json(converted_data):
                # Overwrite original file
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(converted_data, f, indent=4, ensure_ascii=False)
                print(f"  ✅ Converted successfully to '{converted_data['template_name']}'")
                success_count += 1
            else:
                print(f"  ❌ Failed to convert or invalid JSON returned.")
                fail_count += 1
                
        except Exception as e:
            print(f"  💥 Exception processing {filename}: {e}")
            fail_count += 1
            
    chat.stop_keepalive()
    
    print("\n" + "="*50)
    print("Batch Conversion Complete!")
    print(f"Successfully converted: {success_count}")
    print(f"Failed to convert: {fail_count}")
    print("="*50)

if __name__ == "__main__":
    run_conversion()
