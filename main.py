"""
main
====
Main command-line interface (CLI) and interactive terminal console for the Alpha Farm system.

Coordinates the multi-stage pipeline:
1. `generate`: Queries the configured LLM to generate strategy ideas.
2. `mcts`: Compiles macro blueprints and searches for optimized parameters via MCTS.
3. `full`: Runs the entire sequence end-to-end.
"""

import os
import sys
import glob
import time
import argparse
from utilities.AppConfig import PROJECT_ROOT

# Fix Windows terminal UTF-8 encoding issue
sys.stdout.reconfigure(encoding='utf-8')

def cmd_generate(args):
    """
    Execute the strategy generation stage.
    
    Reads credentials and cookies, then triggers GenerateStrategies to query
    LLM models for initial strategy ideas.

    Parameters
    ----------
    args : argparse.Namespace or InteractiveArgs
        The parsed command-line or interactive menu arguments.
    """
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
    """
    Execute the MCTS formula discovery and scaling stage.
    
    Loads blueprint ideas, runs MCTS mutations to expand the trees, and runs backtests 
    to filter and scale strategy candidates.

    Parameters
    ----------
    args : argparse.Namespace or InteractiveArgs
        The parsed command-line or interactive menu arguments.
    """
    print("\n[Bước 2/3] Tầng 2 & 3: MCTS One-pass Pipeline (Entropy + Correlation)...")
    from utilities.AppConfig import REWARD_WEIGHTS
    from strategy_workflows.RunMCTS import run_mcts_pipeline
    
    patience = getattr(args, 'patience', 5000)
    REWARD_WEIGHTS['patience'] = patience
    
    iterations = getattr(args, 'iterations', 50000)
    retrain_hmm = getattr(args, 'retrain_hmm', False)
    seed = getattr(args, 'seed', None)
    run_mcts_pipeline(iterations=iterations, retrain_hmm=retrain_hmm, seed=seed)



def cmd_full(args):
    """
    Execute the full end-to-end pipeline.
    
    Runs generate and mcts stages sequentially.

    Parameters
    ----------
    args : argparse.Namespace or InteractiveArgs
        The parsed command-line or interactive menu arguments.
    """
    cmd_generate(args)
    cmd_mcts(args)

def display_interactive_menu(options: list[str], title: str = "Select option:") -> int:
    """
    Display an interactive terminal menu using ANSI escape sequences and keyboard input.

    Parameters
    ----------
    options : list[str]
        The options to select from.
    title : str, default "Select option:"
        The header title of the menu.

    Returns
    -------
    int
        The index of the selected option.
    """
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
    """
    Retrieve numerical input from the user via terminal prompt with support for defaults.

    Parameters
    ----------
    label : str
        The query label to present.
    default_value : int
        The default fallback value if input is empty.
    value_type : type, default int
        The numeric parser type.

    Returns
    -------
    int
        The parsed numeric value.
    """
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
    """
    Display an interactive menu for the user to choose their preferred LLM client.

    Returns
    -------
    str
        The model identifier key matching MODELS or Ollama/DeepSeek specs.
    """
    options = [
        "DeepSeek Web Thinking (Cloud - Yêu cầu token.txt)",
        "Ollama Qwen3.5 4B (Local - Cần chạy Ollama nền)",
        "Ollama Qwen3.5 9B (Local - Cần chạy Ollama nền)",
        "Gemini Web Flash (Cloud - Yêu cầu cookies.txt)",
        "Gemini Web Pro (Cloud - Yêu cầu cookies.txt)",
        "Gemini Web Flash Thinking (Cloud - Yêu cầu cookies.txt)"
    ]
    keys = [
        "deepseek-thinking",
        "ollama-local",
        "ollama-9b",
        "flash",
        "pro",
        "thinking"
    ]
    selected_idx = display_interactive_menu(options, "Chọn AI Model:")
    return keys[selected_idx]

class InteractiveArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def run_interactive_cli() -> None:
    """
    Start the interactive command-line interface.
    
    Guides the user through command selection, configuration input, model selection, 
    and launches the selected routine.
    """
    os.system("")
    print("="*80)
    print("  GIAO DIỆN TƯƠNG TÁC ALPHA FARM ".center(80))
    print("="*80)
    
    commands = [
        "generate (Tầng 1: Sinh Blueprint JSON bằng LLM)",
        "mcts (Tầng 2 & 3: MCTS One-pass Pipeline)",
        "full (Chạy toàn bộ quy trình: Generate -> MCTS)",
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
        args_dict["iterations"] = retrieve_numerical_input("Giới hạn vòng lặp MCTS tối đa (Max Iterations)", 50000, int)
        args_dict["patience"] = retrieve_numerical_input("Ngưỡng Early Stopping Patience", 5000, int)
        # Bỏ qua tuỳ chọn retrain_hmm ở CLI tương tác cho gọn, mặc định False.
        args_dict["retrain_hmm"] = False
        
    args = InteractiveArgs(**args_dict)
    
    print("\n" + "="*80)
    print("  KHỞI ĐỘNG HỆ THỐNG ALPHA FARM ".center(80))
    print("="*80)
    
    if selected_cmd == "generate":
        cmd_generate(args)
    elif selected_cmd == "mcts":
        cmd_mcts(args)
    elif selected_cmd == "full":
        cmd_full(args)

def main():
    """
    System entry point.
    
    Parses command line arguments, handles fallback to the interactive CLI 
    if no arguments are supplied on a TTY terminal, and routes control 
    to the requested command.
    """
    parser = argparse.ArgumentParser(description="Alpha Farm CLI")
    subparsers = parser.add_subparsers(dest="command", required=False)
    
    # Generate
    parser_gen = subparsers.add_parser("generate", help="Run LLM strategy generation")
    parser_gen.add_argument("--n_strategies", type=int, default=20, help="Number of strategies to generate")
    parser_gen.add_argument("--model", type=str, default="deepseek-thinking", help="LLM Model")
    parser_gen.add_argument("--no_cookies", action="store_true", help="Skip cookie check")
    
    # Convert (DEPRECATED)
    # Convert phase has been removed in 3-Tier Architecture.
    
    # MCTS
    parser_mcts = subparsers.add_parser("mcts", help="Run Tầng 2 & 3 (Compiler + MCTS)")
    parser_mcts.add_argument("--iterations", type=int, default=50000, help="Number of MCTS iterations")
    parser_mcts.add_argument("--patience", type=int, default=5000, help="Early stopping patience limit")
    parser_mcts.add_argument("--retrain-hmm", action="store_true", help="Force retrain HMM models instead of using cache")
    parser_mcts.add_argument("--seed", type=int, default=None, help="Seed for the MCTS random generator (default: not reproducible)")
    
    # Full
    parser_full = subparsers.add_parser("full", help="Run full pipeline (generate -> mcts)")
    parser_full.add_argument("--n_strategies", type=int, default=20)
    parser_full.add_argument("--model", type=str, default="deepseek-thinking")
    parser_full.add_argument("--iterations", type=int, default=50000, help="Number of MCTS iterations")
    parser_full.add_argument("--patience", type=int, default=5000, help="Early stopping patience limit")
    parser_full.add_argument("--retrain-hmm", action="store_true", help="Force retrain HMM models instead of using cache")
    parser_full.add_argument("--seed", type=int, default=None, help="Seed for the MCTS random generator (default: not reproducible)")
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
    print("  KHỞI ĐỘNG HỆ THỐNG ALPHA FARM ".center(80))
    print("="*80)
    
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "mcts":
        cmd_mcts(args)
    elif args.command == "full":
        cmd_full(args)

if __name__ == "__main__":
    main()
