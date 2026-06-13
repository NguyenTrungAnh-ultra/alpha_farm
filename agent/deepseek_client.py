import os
import sys

# Đảm bảo dsk module được import đúng từ agent/util/deepseek4free
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
deepseek_dir = os.path.join(PROJECT_ROOT, "agent", "util", "deepseek4free")
if deepseek_dir not in sys.path:
    sys.path.insert(0, deepseek_dir)

from dsk.api import DeepSeekAPI, AuthenticationError, RateLimitError, CloudflareError, APIError, NetworkError

class DeepseekChatClient:
    """
    Client adapter cho deepseek4free để tương thích với luồng chạy của pipeline.py.
    Mô phỏng cấu trúc .send() giống GeminiChat.
    """
    def __init__(self, auth_token: str, thinking_enabled: bool = True, search_enabled: bool = False, verbose: bool = True):
        self.auth_token = auth_token
        self.thinking_enabled = thinking_enabled
        self.search_enabled = search_enabled
        self.verbose = verbose
        self.api = DeepSeekAPI(self.auth_token)
        
    def send(self, prompt: str) -> str:
        """
        Gửi prompt và trả về kết quả dưới dạng chuỗi nối tiếp.
        Tương thích với GeminiChat.send().
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
        """Hàm dummy để tương thích với GeminiChat.stop_keepalive() nếu có gọi."""
        pass
