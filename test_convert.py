import json
import os
import sys

# Đảm bảo đường dẫn import
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.templates import TEMPLATE_REGISTRY

def test_conversion():
    # Test all templates in registry
    print(f"--- ĐANG KIỂM TRA {len(TEMPLATE_REGISTRY)} TEMPLATES TRONG REGISTRY ---")
    
    for name, info in TEMPLATE_REGISTRY.items():
        print(f"\nTemplate: {name}")
        
        # Build default params
        params = {p_name: p_info['default'] for p_name, p_info in info['params'].items()}
        print(f"  Params: {params}")
        
        # Generate code
        try:
            code = info['generate_code'](params)
            print("  ✅ Code generated successfully!")
            
            # Basic sanity check
            assert "class CustomStrategy(SimpleAlgorithm):" in code
            assert "def __algorithm__(self):" in code
            print("  ✅ Syntax check: OK")
        except Exception as e:
            print(f"  ❌ Generation failed: {e}")

if __name__ == "__main__":
    test_conversion()
