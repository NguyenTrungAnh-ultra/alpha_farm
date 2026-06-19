import requests
import json
import subprocess
import time
import os
import shutil

def _find_ollama_cmd():
    """Tìm đường dẫn tuyệt đối của ollama.exe trên Windows nếu không có trong PATH."""
    cmd = shutil.which("ollama")
    if cmd:
        return cmd
    
    # Các đường dẫn phổ biến trên Windows
    user_profile = os.environ.get("USERPROFILE", "")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    paths = []
    if local_app_data:
        paths.append(os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe"))
    if user_profile:
        paths.append(os.path.join(user_profile, "AppData", "Local", "Programs", "Ollama", "ollama.exe"))
    paths.append(r"C:\Program Files\Ollama\ollama.exe")
    
    for p in paths:
        if os.path.exists(p):
            return p
            
    return "ollama"  # Trả về mặc định nếu không tìm thấy

class OllamaChatClient:
    """
    Client adapter cho Ollama Local API. Tự động bật Ollama, tạo model từ Modelfile, và tự tắt khi xong.
    Mô phỏng cấu trúc .send() giống GeminiChat.
    """
    def __init__(self, model: str = "qwen3.5:4b", host: str = "http://localhost:11434", verbose: bool = True):
        self.model = model
        self.host = host
        self.verbose = verbose
        self.server_process = None
        self._setup()
        
    def _is_server_running(self):
        try:
            requests.get(self.host, timeout=2)
            return True
        except:
            return False
            
    def _setup(self):
        ollama_cmd = _find_ollama_cmd()
        
        # 1. Bật Ollama Server nếu chưa chạy
        if not self._is_server_running():
            if self.verbose: print(f"[Ollama] Server is not running. Starting '{ollama_cmd} serve' in background...")
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                self.server_process = subprocess.Popen([ollama_cmd, "serve"], startupinfo=startupinfo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[Ollama] Failed to start Ollama process: {e}")
            
            # Đợi server khởi động
            for _ in range(15):
                if self._is_server_running():
                    break
                time.sleep(1)
            else:
                raise Exception("Failed to start Ollama server.")
                
        # 2. Nạp Modelfile để tạo mô hình tùy chỉnh
        modelfile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Modelfile")
        custom_model = "alpha_farm_qwen"
        created_custom = False
        if os.path.exists(modelfile_path):
            if self.verbose: print(f"[Ollama] Creating/Updating custom model '{custom_model}' from Modelfile...")
            try:
                # Chạy build model tùy chỉnh
                subprocess.run([ollama_cmd, "create", custom_model, "-f", modelfile_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.model = custom_model
                created_custom = True
            except Exception as e:
                print(f"[Ollama] Warning: Could not create custom model. Falling back to base model '{self.model}'. Error: {e}")
        
        # 3. Nạp model vào VRAM
        if self.verbose: print(f"[Ollama] Pre-loading model '{self.model}' into VRAM...")
        try:
            requests.post(f"{self.host}/api/generate", json={"model": self.model, "prompt": "", "keep_alive": "24h", "options": {"num_ctx": 16384}}, timeout=30)
        except Exception:
            pass
            
    def send(self, prompt: str) -> str:
        """
        Gửi prompt tới Ollama và trả về kết quả dưới dạng chuỗi nối tiếp.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 16384,
                "num_predict": -1
            }
        }
        
        try:
            if self.verbose: print(f"[Ollama] Generating response using '{self.model}'...")
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            if self.verbose: print(f"[Ollama] Request failed: {e}")
            raise e

    def stop_keepalive(self):
        """Hủy nạp model khỏi VRAM và tắt server nếu nó được mở bởi script này."""
        if self.verbose: print(f"\n[Ollama] Unloading model '{self.model}' from VRAM...")
        try:
            requests.post(f"{self.host}/api/generate", json={"model": self.model, "prompt": "", "keep_alive": 0}, timeout=10)
        except Exception:
            pass
            
        if self.server_process is not None:
            if self.verbose: print(f"[Ollama] Shutting down local Ollama server process...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
