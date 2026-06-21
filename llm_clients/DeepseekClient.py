from utilities.AppConfig import PROJECT_ROOT
import os
import sys

# Đảm bảo dsk module được import đúng từ utilities/deps/deepseek4free
deepseek_dir = os.path.join(PROJECT_ROOT, "utilities", "deps", "deepseek4free")
if deepseek_dir not in sys.path:
    sys.path.insert(0, deepseek_dir)

"""
DeepseekClient
==============
Adapter client wrapper for the deepseek4free library.

Ensures compatibility with the main strategy generation pipeline by providing 
a consistent `.send()` signature matching the Gemini client.
"""

from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, CloudflareError, APIError, NetworkError

class DeepseekChatClient:
    """
    Client adapter wrapper for deepseek4free API.
    
    Provides compatibility with the strategy generation pipeline by exposing 
    a `.send()` method signature identical to that of GeminiChat.
    """
    def __init__(self, auth_token: str, thinking_enabled: bool = True, search_enabled: bool = False, verbose: bool = True):
        self.auth_token = auth_token
        self.thinking_enabled = thinking_enabled
        self.search_enabled = search_enabled
        self.verbose = verbose
        self.api = DeepSeekAPI(self.auth_token)
        
    def send(self, prompt: str) -> str:
        """
        Send a prompt to the DeepSeek API and return the concatenated text response.
        
        Initializes a fresh chat session for each request to prevent context interference.
        Handles authentication errors, Cloudflare clearance challenges, and rate limits.

        Parameters
        ----------
        prompt : str
            The input prompt string.

        Returns
        -------
        str
            The text response from the model (excluding thinking reasoning chains).

        Raises
        ------
        RuntimeError
            If authentication, Cloudflare bypass, rate-limiting, or general API errors occur.
        """
        try:
            # Luôn tạo session chat mới cho mỗi chiến lược để không bị nhiễu ngữ cảnh
            chat_id = self.api.create_chat_session()
            
            chunks = self.api.chat_completion(
                chat_id,
                prompt,
                thinking_enabled=self.thinking_enabled,
                search_enabled=self.search_enabled
            )
            
            text_content = []
            
            if self.verbose:
                print("\n[DeepSeek] Bắt đầu sinh ý tưởng...")
            
            for chunk in chunks:
                if chunk['type'] == 'thinking':
                    if self.verbose and chunk['content']:
                        # In log thinking ra một tệp hoặc console nếu cần thiết, 
                        # ở đây chúng ta bỏ qua in chi tiết ra console để tránh rác màn hình
                        pass
                elif chunk['type'] == 'text':
                    text_content.append(chunk['content'])
            
            final_text = ''.join(text_content)
            
            if self.verbose:
                print(f"[DeepSeek] Hoàn thành. Độ dài phản hồi: {len(final_text)} ký tự")
                
            return final_text
            
        except AuthenticationError as e:
            raise RuntimeError(f"Lỗi xác thực DeepSeek. Kiểm tra lại userToken trong token.txt: {e}")
        except CloudflareError as e:
            # In ra hướng dẫn bypass
            raise RuntimeError(f"Bị Cloudflare chặn. Hãy chạy thủ công lệnh: 'python -m dsk.bypass' để lấy clearance cookie. Lỗi: {e}")
        except RateLimitError as e:
            raise RuntimeError(f"Vượt giới hạn gửi request. Vui lòng thử lại sau. Lỗi: {e}")
        except Exception as e:
            raise RuntimeError(f"Lỗi API DeepSeek không mong muốn: {e}")
            
    def stop_keepalive(self):
        """
        Dummy method to match the GeminiChat.stop_keepalive interface.
        """
        pass
