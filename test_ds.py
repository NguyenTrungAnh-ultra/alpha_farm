import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
deepseek_dir = os.path.join(PROJECT_ROOT, "agent", "util", "deepseek4free")
if deepseek_dir not in sys.path:
    sys.path.insert(0, deepseek_dir)

from dsk.api import DeepSeekAPI

def test():
    with open("token.txt", "r") as f:
        token = f.read().strip()
    
    print("Testing DeepSeekAPI instantiation...", flush=True)
    api = DeepSeekAPI(token)
    
    print("Testing create_chat_session...", flush=True)
    try:
        chat_id = api.create_chat_session()
        print(f"Chat ID: {chat_id}", flush=True)
        
        print("Testing chat_completion...", flush=True)
        chunks = api.chat_completion(chat_id, "Explain 1+1", thinking_enabled=True)
        for chunk in chunks:
            print(f"RAW CHUNK: {chunk}", flush=True)
        print("\nCompletion finished.", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    test()
