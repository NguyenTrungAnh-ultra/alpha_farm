import json
import os
import sys

# Đảm bảo đường dẫn import
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.convert_ideas import generate_python_code

def test_conversion():
    # Chọn ngẫu nhiên 1 tệp JSON có sẵn
    idea_path = os.path.join(PROJECT_ROOT, "agent", "results", "ideas", "Absolute_Directional_MFI_Reversal_10m.json")
    
    if not os.path.exists(idea_path):
        print("Không tìm thấy tệp JSON.")
        return
        
    with open(idea_path, 'r', encoding='utf-8') as f:
        idea = json.load(f)
        
    print(f"--- ĐANG CHUYỂN ĐỔI: {idea.get('name')} ---")
    code = generate_python_code(idea)
    
    print("\n--- KẾT QUẢ MÃ NGUỒN (KHÔNG CÓ GETATTR) ---")
    print(code)
    
    if "getattr" in code:
        print("\n[!] CẢNH BÁO: Vẫn còn getattr trong mã nguồn!")
    else:
        print("\n[OK] Mã nguồn sạch, không chứa getattr.")

if __name__ == "__main__":
    test_conversion()
