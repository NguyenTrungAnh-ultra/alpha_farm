import os
import sys
import glob
import time
import argparse
from utilities.AppConfig import PROJECT_ROOT, QUALITY_THRESHOLDS

# Fix Windows terminal UTF-8 encoding issue
sys.stdout.reconfigure(encoding='utf-8')

def cmd_generate(args):
    print("\n[Bước 1/4] Đang sinh ý tưởng (Ideas Generation)...")
    from strategy_workflows.GenerateStrategies import run_pipeline, load_cookies
    
    # 1. Trợ lý Cookie
    cookie_path = os.path.join(PROJECT_ROOT, "cookies.txt")
    cookies = None
    try:
        cookies = load_cookies(cookie_path)
    except Exception:
        print("Lỗi: Không thể load cookies.txt.")
        if not args.no_cookies:
            sys.exit(1)
            
    run_pipeline(
        cookies=cookies,
        n_strategies=args.n_strategies,
        model=args.model
    )

def cmd_mcts(args):
    print("\n[Bước 2/3] Tầng 2 & 3: Biên dịch Blueprint & MCTS Brute-force...")
    from strategy_workflows.RunMCTS import run_mcts_pipeline
    iterations = getattr(args, 'iterations', 500)
    run_mcts_pipeline(iterations=iterations)



def cmd_submit(args):
    print("\n[Bước 3/3] Nộp chiến lược (Auto Submit)...")
    from strategy_workflows.SubmitStrategies import run_auto_submit
    
    results_dir = os.path.join(PROJECT_ROOT, "results")
    py_files = glob.glob(os.path.join(results_dir, "*.py"))
    py_files = [f for f in py_files if not os.path.basename(f).startswith("__")]
    
    if not py_files:
        print("Không có chiến lược nào để nộp.")
        return
        
    for filepath in py_files:
        filename = os.path.basename(filepath)
        tf_part = filename.split('_')[-1].replace('.py', '')
        tf = tf_part if tf_part in ['1m', '3m', '5m', '10m', '15m', '30m', '60m'] else '10m'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
            
        success, err_msg = run_auto_submit(strategy_code=code, timeframe=tf, filepath=filepath)
        if success:
            print(f"✅ SUCCESS: {filename}")
        else:
            print(f"❌ FAILED: {filename} - {err_msg}")
        time.sleep(15)

def cmd_full(args):
    cmd_generate(args)
    cmd_mcts(args)
    # Tạm bỏ qua Optimize vì MCTS đã quét Scale, có thể tích hợp sau nếu cần
    cmd_submit(args)

def display_interactive_menu(options: list[str], title: str = "Select option:") -> int:
    import msvcrt
    
    # Enable ANSI escape codes on Windows 10+
    os.system("")
    
    selected_index = 0
    print(f"\n  \033[1;36m{title}\033[0m")
    
    def render_menu():
        for i, option in enumerate(options):
            if i == selected_index:
                sys.stdout.write(f"  \033[1;32m➔  {option}\033[0m\n")
            else:
                sys.stdout.write(f"     {option}\n")
        sys.stdout.flush()
                
    render_menu()
    
    try:
        while True:
            char = msvcrt.getch()
            if char in (b'\xe0', b'\x00'): # Arrow key prefix
                sub_char = msvcrt.getch()
                if sub_char == b'H': # Up arrow
                    selected_index = (selected_index - 1) % len(options)
                elif sub_char == b'P': # Down arrow
                    selected_index = (selected_index + 1) % len(options)
            elif char in (b'\r', b'\n'): # Enter key
                break
            elif char == b'\x03': # Ctrl+C
                print("\nThoát chương trình.")
                sys.exit(0)
            else:
                continue
                
            # Clear previous printed menu lines
            sys.stdout.write(f"\033[{len(options)}A")
            render_menu()
    except KeyboardInterrupt:
        print("\nThoát chương trình.")
        sys.exit(0)
        
    return selected_index

def retrieve_numerical_input(label: str, default_value: int, value_type: type = int) -> int:
    os.system("")
    sys.stdout.write(f"\n  \033[1;33m? \033[0m{label} [\033[36mMặc định: {default_value}\033[0m]: ")
    sys.stdout.flush()
    try:
        user_input = input().strip()
        if not user_input:
            return default_value
        return value_type(user_input)
    except ValueError:
        print(f"  \033[31mLỗi: Giá trị không hợp lệ. Sử dụng mặc định: {default_value}\033[0m")
        return default_value

def select_ai_model() -> str:
    models = ["deepseek-thinking", "ollama-local", "ollama-9b", "gemini-2.5-flash"]
    selected_idx = display_interactive_menu(models, "Chọn AI Model:")
    return models[selected_idx]

class InteractiveArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_interactive_cli() -> None:
    os.system("")
    print("="*80)
    print("  GIAO DIỆN TƯƠNG TÁC XNOQUANT AUTO-FARM ".center(80))
    print("="*80)
    
    commands = [
        "generate (Tầng 1: Sinh Blueprint JSON bằng LLM)",
        "mcts (Tầng 2 & 3: Semantic Compiler & MCTS Đào mỏ)",
        "submit (Tự động nộp chiến lược lên XNO)",
        "full (Chạy toàn bộ quy trình: Generate -> MCTS -> Submit)",
        "Exit (Thoát)"
    ]
    
    selected_cmd_idx = display_interactive_menu(commands, "Chọn lệnh muốn thực thi:")
    selected_cmd = commands[selected_cmd_idx].split()[0]
    
    if selected_cmd == "Exit":
        print("\nTạm biệt!")
        sys.exit(0)
        
    print(f"\n  \033[1;32m» Lệnh đã chọn: {selected_cmd}\033[0m")
    
    args_dict = {"command": selected_cmd, "no_cookies": False}
    
    if selected_cmd in ("generate", "full"):
        args_dict["n_strategies"] = retrieve_numerical_input("Số lượng chiến lược sinh ra", 20, int)
        args_dict["model"] = select_ai_model()
        
    if selected_cmd in ("mcts", "full"):
        args_dict["iterations"] = retrieve_numerical_input("Số lượng vòng lặp MCTS (iterations)", 500, int)
        
    args = InteractiveArgs(**args_dict)
    
    print("\n" + "="*80)
    print("  KHỞI ĐỘNG HỆ THỐNG XNOQUANT AUTO-FARM ".center(80))
    print("="*80)
    
    if selected_cmd == "generate":
        cmd_generate(args)
    elif selected_cmd == "mcts":
        cmd_mcts(args)
    elif selected_cmd == "submit":
        cmd_submit(args)
    elif selected_cmd == "full":
        cmd_full(args)

def main():
    parser = argparse.ArgumentParser(description="XNOQuant Auto-Farm CLI")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    # Generate
    parser_gen = subparsers.add_parser("generate", help="Run LLM strategy generation")
    parser_gen.add_argument("--n_strategies", type=int, default=20, help="Number of strategies to generate")
    parser_gen.add_argument("--model", type=str, default="deepseek-thinking", help="LLM Model")
    parser_gen.add_argument("--no_cookies", action="store_true", help="Skip cookie check")
    
    # Convert (DEPRECATED)
    # parser_conv = subparsers.add_parser("convert", help="Deprecated in 3-Tier Architecture")
    
    # MCTS
    parser_mcts = subparsers.add_parser("mcts", help="Run Tầng 2 & 3 (Compiler + MCTS)")
    parser_mcts.add_argument("--iterations", type=int, default=500, help="Number of MCTS iterations")
    
    # Submit
    parser_sub = subparsers.add_parser("submit", help="Auto submit valid strategies")
    
    # Full
    parser_full = subparsers.add_parser("full", help="Run full pipeline (generate -> mcts -> submit)")
    parser_full.add_argument("--n_strategies", type=int, default=20)
    parser_full.add_argument("--model", type=str, default="deepseek-thinking")
    parser_full.add_argument("--iterations", type=int, default=500, help="Number of MCTS iterations")
    parser_full.add_argument("--no_cookies", action="store_true")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        if sys.stdin.isatty():
            run_interactive_cli()
        else:
            parser.print_help()
        sys.exit(0)
        
    if args.command is None:
        parser.print_help()
        sys.exit(0)
        
    print("="*80)
    print("  KHỞI ĐỘNG HỆ THỐNG XNOQUANT AUTO-FARM ".center(80))
    print("="*80)
    
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "mcts":
        cmd_mcts(args)
    elif args.command == "submit":
        cmd_submit(args)
    elif args.command == "full":
        cmd_full(args)

if __name__ == "__main__":
    main()
