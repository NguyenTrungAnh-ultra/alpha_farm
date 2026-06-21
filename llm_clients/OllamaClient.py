"""
OllamaClient
============
Client wrapper for local Ollama APIs and running models.

Launches the local Ollama server process automatically, creates customized 
model configurations from a Modelfile, pre-loads models to VRAM, handles 
request responses with context boundaries, and unloads/terminates on shutdown.
"""

import requests
import json
import subprocess
import time
import os
import shutil

def _find_ollama_cmd():
    """
    Search for the absolute path of the Ollama executable on Windows/PATH.
    
    Returns
    -------
    str
        The absolute path to the executable, or "ollama" if not found.
    """
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
    Client adapter for the local Ollama REST API.
    
    Automates starting the local Ollama server, builds/updates a custom model
    using a Modelfile template, pre-loads the model in VRAM, routes query prompts, 
    and handles process cleanup on shutdown.
    """
    def __init__(self, model: str = "qwen3.5:4b", host: str = "http://localhost:11434", verbose: bool = True):
        self.model = model
        self.host = host
        self.verbose = verbose
        self.server_process = None
        self._setup()
        
    def _is_server_running(self):
        """
        Check if the local Ollama server is currently listening.
        
        Returns
        -------
        bool
            True if the server responded to the heartbeat probe, False otherwise.
        """
        try:
            requests.get(self.host, timeout=2)
            return True
        except:
            return False
            
    def _setup(self):
        """
        Set up the Ollama server environment, build custom models, and pre-load into VRAM.
        
        1. Checks if the server is running, starting it as a background process if necessary.
        2. Configures a custom Modelfile using the specified base model.
        3. Pre-loads the model to VRAM via an empty generate call with keepalive set to 24h.
        """
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
        created_custom = False
        if os.path.exists(modelfile_path):
            base_model = self.model
            clean_base_model = base_model.replace(":", "_").replace(".", "_").replace("-", "_")
            custom_model = f"alpha_farm_{clean_base_model}"
            
            if self.verbose:
                print(f"[Ollama] Preparing custom model '{custom_model}' from base '{base_model}'...")
                
            try:
                # Đọc nội dung Modelfile gốc
                with open(modelfile_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                
                # Thay thế hoặc chèn dòng FROM để trỏ tới base_model tương ứng
                lines = []
                replaced_from = False
                for line in original_content.splitlines():
                    if line.strip().upper().startswith("FROM "):
                        lines.append(f"FROM {base_model}")
                        replaced_from = True
                    else:
                        lines.append(line)
                if not replaced_from:
                    lines.insert(0, f"FROM {base_model}")
                
                custom_modelfile_content = "\n".join(lines)
                
                # Ghi ra file tạm để build
                temp_modelfile_path = modelfile_path + f".{clean_base_model}.auto"
                with open(temp_modelfile_path, "w", encoding="utf-8") as f:
                    f.write(custom_modelfile_content)
                
                if self.verbose:
                    print(f"[Ollama] Creating/Updating custom model '{custom_model}' using temporary Modelfile...")
                
                try:
                    subprocess.run(
                        [ollama_cmd, "create", custom_model, "-f", temp_modelfile_path],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    self.model = custom_model
                    created_custom = True
                finally:
                    if os.path.exists(temp_modelfile_path):
                        os.remove(temp_modelfile_path)
            except Exception as e:
                print(f"[Ollama] Warning: Could not create custom model. Falling back to base model '{self.model}'. Error: {e}")
        
        # 3. Nạp model vào VRAM
        if self.verbose: print(f"[Ollama] Pre-loading model '{self.model}' into VRAM...")
        try:
            requests.post(f"{self.host}/api/generate", json={"model": self.model, "prompt": "", "keep_alive": "24h", "options": {"num_ctx": 16384}}, timeout=30)
        except Exception:
            pass
            
    def send(self, prompt: str, schema: dict = None) -> str:
        """
        Send a prompt to the local Ollama model and return the generated text response.

        Parameters
        ----------
        prompt : str
            The input prompt string.
        schema : dict, optional
            A JSON Schema dictionary (typically from Pydantic) to enforce structured JSON output.

        Returns
        -------
        str
            The text response from the model.

        Raises
        ------
        Exception
            If the HTTP request to the Ollama server fails.
        """
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 16384
            }
        }
        if schema:
            payload["format"] = schema
        
        try:
            if self.verbose: print(f"[Ollama] Generating response using '{self.model}'...")
            response = requests.post(url, json=payload, timeout=300)
            response.raise_for_status()
            data = response.json()
            
            resp_text = data.get("response", "")
            thinking = data.get("thinking", "")
            
            if not resp_text and thinking:
                resp_text = thinking
                
            return resp_text
        except Exception as e:
            if self.verbose: print(f"[Ollama] Request failed: {e}")
            raise e

    def stop_keepalive(self):
        """
        Unload the model from VRAM and terminate the background server process.
        
        Sends a keep_alive = 0 request to unload the model from VRAM and terminates
        the server subprocess if it was spawned during initialization.
        """
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
