"""
correct_failed_ideas.py
=======================
Quét các idea JSON chưa có file .py hợp lệ và thử sửa lỗi theo 3 giai đoạn:

  Giai đoạn A — Pre-Fix (Tầng 1 & 2a): sandbox_prefixer.apply_prefixes()
      Áp dụng các fix xác định (Regex + fuzzy), không tốn API call.
      Nếu có thay đổi: sync ngược vào JSON trên disk.

  Giai đoạn B — Validate Pre-Fixed Code:
      Nếu Sharpe >= 1.3 → SUCCESS.
      Nếu code chạy nhưng Sharpe < 1.3 → Tầng 4: SKIP (không retry LLM).
      Nếu exception → chuyển sang Giai đoạn C.

  Giai đoạn C — LLM Self-Correction (Tầng 2b & 3): max 3 attempts
      Mỗi attempt: build_correction_prompt → Ollama → validate.
      Nếu Sharpe >= 1.3 → SUCCESS, cập nhật JSON.
      Nếu Sharpe < 1.3 (no error) → Tầng 4: SKIP.
      Nếu vẫn exception sau 3 attempts → move to failed_conversions/.
"""

import os
import sys
import json
import glob
import traceback
import shutil

# Add project root to path
PROJECT_ROOT = "f:/Projects/alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.convert_ideas import generate_python_code
from agent.sandbox_prefixer import apply_prefixes, check_tautology
from xno_sdk.emulator import XNOPlatformEmulator
from agent.prompts import build_correction_prompt
from agent.gemini_client import extract_json
from agent.ollama_client import OllamaChatClient


# ── Helpers ────────────────────────────────────────────────────────────────

def _load_idea(filepath: str) -> dict | None:
    """Load và parse JSON idea file. Trả về None nếu lỗi."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ❌ Error loading JSON: {e}")
        return None


def _save_idea(filepath: str, idea: dict) -> None:
    """Ghi idea dict ngược lại vào JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(idea, f, indent=4, ensure_ascii=False)


def _save_code(filepath: str, code: str) -> None:
    """Ghi Python code ra file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)


def _remove_file(filepath: str) -> None:
    """Xóa file nếu tồn tại."""
    if os.path.exists(filepath):
        os.remove(filepath)


def _validate(emulator: XNOPlatformEmulator, py_filepath: str, tf: str) -> tuple[float, float]:
    """
    Chạy emulator và trả về (sharpe, cagr).
    Raise exception nếu code bị lỗi runtime/sandbox.
    """
    metrics = emulator.get_metrics(py_filepath, tf)
    return metrics.get("sharpe_ratio", 0.0), metrics.get("cagr", 0.0)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Correct failed strategy ideas (3-phase: pre-fix → validate → LLM)."
    )
    parser.add_argument(
        "--failed-only", action="store_true",
        help="Chỉ xử lý ideas đã có .py trong failed_conversions/ (bỏ qua fresh ideas)."
    )
    parser.add_argument(
        "--fresh-only", action="store_true",
        help="Chỉ xử lý ideas chưa từng generate (bỏ qua failed_conversions/)."
    )
    args = parser.parse_args()

    ideas_dir  = os.path.join(PROJECT_ROOT, "agent", "results", "ideas")
    output_dir = os.path.join(PROJECT_ROOT, "agent", "results")
    failed_dir = os.path.join(output_dir, "failed_conversions")

    os.makedirs(failed_dir, exist_ok=True)

    if not os.path.exists(ideas_dir):
        print(f"Ideas directory does not exist: {ideas_dir}")
        return

    json_files = sorted(f for f in os.listdir(ideas_dir) if f.endswith(".json"))
    print(f"Found {len(json_files)} total idea JSON files.")

    # Phân loại ideas thành 2 nhóm
    failed_backlog: list[str] = []   # Đã có trong failed_conversions/ → ưu tiên trước
    fresh_backlog: list[str]  = []   # Chưa từng generate

    for filename in json_files:
        py_filename = filename.replace(".json", ".py")
        py_filepath       = os.path.join(output_dir, py_filename)
        pushed_llm_path   = os.path.join(output_dir, "pushed", "llm_strategies", py_filename)
        pushed_mcts_path  = os.path.join(output_dir, "pushed", "mcts_strategies", py_filename)
        in_failed_path    = os.path.join(failed_dir, py_filename)

        # Bỏ qua ideas đã thành công
        if os.path.exists(py_filepath) or os.path.exists(pushed_llm_path) or os.path.exists(pushed_mcts_path):
            continue

        if os.path.exists(in_failed_path):
            failed_backlog.append(filename)
        else:
            fresh_backlog.append(filename)

    # Áp dụng filter từ CLI args
    if args.failed_only:
        ideas_to_process = failed_backlog
        print(f"Mode: --failed-only → {len(ideas_to_process)} ideas từ failed_conversions/")
    elif args.fresh_only:
        ideas_to_process = fresh_backlog
        print(f"Mode: --fresh-only → {len(ideas_to_process)} ideas chưa từng generate")
    else:
        # Ưu tiên failed_backlog trước (đã biết dạng lỗi, thường pre-fix được)
        ideas_to_process = failed_backlog + fresh_backlog
        print(
            f"Mode: ALL → {len(failed_backlog)} failed + {len(fresh_backlog)} fresh "
            f"= {len(ideas_to_process)} ideas"
        )

    if not ideas_to_process:
        print("Tất cả ideas đã được convert. Không có gì để xử lý.")
        return

    # Khởi tạo LLM client và Emulator
    print("\n[Ollama] Initializing local client for self-correction...")
    try:
        chat = OllamaChatClient(model="qwen3.5:4b", verbose=False)
        print("[Ollama] Local client ready.")
    except Exception as e:
        print(f"❌ Failed to initialize Ollama: {e}")
        print("Hãy đảm bảo Ollama đang chạy trên máy.")
        return

    emulator = XNOPlatformEmulator(verbose=False)

    # Counters
    success_count  = 0
    prefix_count   = 0   # Thành công nhờ pre-fix mà không cần LLM
    llm_count      = 0   # Thành công nhờ LLM correction
    tier4_count    = 0   # Sharpe thấp (Tầng 4) — bỏ qua
    fail_count     = 0   # Thất bại hoàn toàn → failed_conversions/

    MAX_LLM_ATTEMPTS = 3

    for idx, filename in enumerate(ideas_to_process, 1):
        json_filepath = os.path.join(ideas_dir, filename)
        py_filename   = filename.replace(".json", ".py")
        py_filepath   = os.path.join(output_dir, py_filename)
        failed_path   = os.path.join(failed_dir, py_filename)

        print(f"\n[{idx}/{len(ideas_to_process)}] Processing: {filename}")

        # ── Load idea ──────────────────────────────────────────────────────
        idea = _load_idea(json_filepath)
        if idea is None:
            fail_count += 1
            continue

        tf = idea.get("timeframe", "15m")

        # ══════════════════════════════════════════════════════════════════
        # Giai đoạn A: Generate code + Deterministic Pre-Fix (Tầng 1 & 2a)
        # ══════════════════════════════════════════════════════════════════
        try:
            code = generate_python_code(idea)
        except Exception as e:
            print(f"  ❌ generate_python_code failed: {e}")
            fail_count += 1
            continue

        print(f"  [A] Applying deterministic pre-fixes...")
        fixed_code, updated_idea, was_modified, fix_log = apply_prefixes(code, idea)

        for log_line in fix_log:
            print(log_line)

        # Kiểm tra tautology (chỉ cảnh báo, không fix)
        for warn in check_tautology(fixed_code):
            print(warn)

        if was_modified:
            # Sync JSON ngược lại disk để lần sau generate ra code đúng ngay
            _save_idea(json_filepath, updated_idea)
            print(f"  [A] ✅ Pre-fix applied & JSON synced.")
            idea = updated_idea
            code = fixed_code
        else:
            print(f"  [A] Không có deterministic fix nào cần thiết.")

        # ══════════════════════════════════════════════════════════════════
        # Giai đoạn B: Validate code đã pre-fix
        # ══════════════════════════════════════════════════════════════════
        print(f"  [B] Validating in Sandbox...")
        _save_code(py_filepath, code)

        pre_fix_error: str | None = None
        pre_fix_success = False
        try:
            sharpe, cagr = _validate(emulator, py_filepath, tf)
            if sharpe >= 1.3:
                print(f"  [B] ✅ PASS! Sharpe: {sharpe:.4f} | CAGR: {cagr*100:.2f}%")
                pre_fix_success = True
                success_count += 1
                if was_modified:
                    prefix_count += 1
            else:
                # Tầng 4: code chạy được nhưng chiến lược kém
                print(
                    f"  [B] ⏭ Tầng 4 — Sharpe ({sharpe:.4f}) < 1.3. "
                    f"Logic tài chính kém, cần MCTS/LLM tái sinh. Bỏ qua."
                )
                _remove_file(py_filepath)
                tier4_count += 1
                continue  # next idea

        except Exception as e:
            pre_fix_error = traceback.format_exc()
            print(f"  [B] ❌ Sandbox Error: {type(e).__name__}: {e}")
            _remove_file(py_filepath)

        if pre_fix_success:
            print(f"  ✨ Saved to results/{py_filename}")
            continue  # next idea

        # Nếu không có lỗi sandbox thì đã xử lý xong (success hoặc tier4)
        if pre_fix_error is None:
            continue

        # ══════════════════════════════════════════════════════════════════
        # Giai đoạn C: LLM Self-Correction (Tầng 2b & 3), max 3 attempts
        # ══════════════════════════════════════════════════════════════════
        print(f"  [C] Bắt đầu LLM self-correction (max {MAX_LLM_ATTEMPTS} attempts)...")
        error_msg  = pre_fix_error
        llm_success = False

        for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
            print(f"  [C] Attempt {attempt}/{MAX_LLM_ATTEMPTS} — querying Ollama...")

            correction_prompt = build_correction_prompt(
                json.dumps(idea, indent=4, ensure_ascii=False),
                error_msg,
            )
            try:
                raw_text = chat.send(correction_prompt)
                corrected_idea = extract_json(raw_text)
            except Exception as e:
                print(f"  [C] ❌ Ollama error: {e}")
                break

            if not corrected_idea:
                print("  [C] ❌ Không parse được JSON từ Ollama response.")
                break

            # Validate corrected idea
            try:
                corrected_code = generate_python_code(corrected_idea)
            except Exception as e:
                print(f"  [C] ❌ generate_python_code failed: {e}")
                error_msg = traceback.format_exc()
                idea = corrected_idea
                continue

            _save_code(py_filepath, corrected_code)
            try:
                sharpe, cagr = _validate(emulator, py_filepath, tf)
                if sharpe >= 1.3:
                    print(
                        f"  [C] ✅ PASS (attempt {attempt})! "
                        f"Sharpe: {sharpe:.4f} | CAGR: {cagr*100:.2f}%"
                    )
                    # Cập nhật JSON với idea đã được LLM sửa
                    _save_idea(json_filepath, corrected_idea)
                    llm_success = True
                    success_count += 1
                    llm_count += 1
                    break
                else:
                    # Tầng 4 sau LLM correction
                    print(
                        f"  [C] ⏭ Tầng 4 (attempt {attempt}) — "
                        f"Sharpe ({sharpe:.4f}) < 1.3. Không retry thêm."
                    )
                    _remove_file(py_filepath)
                    tier4_count += 1
                    llm_success = True  # Đánh dấu là đã xử lý (không cần move to failed)
                    break

            except Exception as e:
                error_msg = traceback.format_exc()
                print(f"  [C] ❌ Sandbox Error (attempt {attempt}): {type(e).__name__}: {e}")
                _remove_file(py_filepath)
                idea = corrected_idea  # Dùng idea LLM đã sửa cho attempt tiếp theo

        if not llm_success:
            # Hết attempts → lưu vào failed_conversions để debug sau
            print(
                f"  [C] ❌ Hết {MAX_LLM_ATTEMPTS} attempts. "
                f"Chuyển vào failed_conversions/..."
            )
            try:
                final_code = generate_python_code(idea)
                _save_code(failed_path, final_code)
            except Exception:
                pass
            fail_count += 1
        elif llm_success:
            print(f"  ✨ Saved to results/{py_filename}")

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("CORRECTION RUN COMPLETE")
    print("=" * 60)
    print(f"  ✅ Success total     : {success_count}")
    print(f"     ↳ By pre-fix only : {prefix_count}")
    print(f"     ↳ By LLM fix      : {llm_count}")
    print(f"  ⏭ Tầng 4 (skipped) : {tier4_count}")
    print(f"  ❌ Failed (no fix)  : {fail_count}")
    print("=" * 60)

    if hasattr(chat, "stop_keepalive"):
        chat.stop_keepalive()


if __name__ == "__main__":
    main()
