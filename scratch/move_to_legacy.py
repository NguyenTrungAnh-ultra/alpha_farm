import os
import sys
import json
import subprocess

PROJECT_ROOT = r"f:\Projects\alpha_farm"
ideas_dir = os.path.join(PROJECT_ROOT, "results", "ideas")
legacy_file = os.path.join(PROJECT_ROOT, "results", "ideas_legacy.json")

new_files = {
    "VN30F15M_MorningStarMACDTrend_15m.json",
    "VN30F1M_ADX_TrendBreakout_15m.json",
    "VN30F1M_BollingerSqueeze_Trend_10m.json",
    "VN30F30M_EMAADX_Trend_30m.json"
}

def main():
    # 1. Restore all deleted tracked files in results/ideas/
    print("Restoring deleted ideas from git...")
    try:
        subprocess.run(["git", "checkout", "HEAD", "--", "results/ideas/"], cwd=PROJECT_ROOT, check=True)
        print("Restoration successful.")
    except Exception as e:
        print(f"Failed to restore: {e}")
        sys.exit(1)

    # 2. Read all files except the new ones
    legacy_ideas = []
    restored_files = []
    
    for filename in os.listdir(ideas_dir):
        if filename.endswith(".json") and filename not in new_files:
            filepath = os.path.join(ideas_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    idea_data = json.load(f)
                    # Add filename reference to trace it later if needed
                    idea_data["original_filename"] = filename
                    legacy_ideas.append(idea_data)
                    restored_files.append(filepath)
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    print(f"Read {len(legacy_ideas)} legacy ideas.")

    # 3. Write all legacy ideas into ideas_legacy.json
    print(f"Writing to {legacy_file}...")
    try:
        with open(legacy_file, "w", encoding="utf-8") as f:
            json.dump(legacy_ideas, f, indent=4, ensure_ascii=False)
        print("Legacy file written successfully.")
    except Exception as e:
        print(f"Failed to write legacy file: {e}")
        sys.exit(1)

    # 4. Clean up the restored files
    print("Cleaning up restored files...")
    deleted_count = 0
    for filepath in restored_files:
        try:
            os.remove(filepath)
            deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {filepath}: {e}")

    print(f"Deleted {deleted_count} restored files.")
    print("Done!")

if __name__ == "__main__":
    main()
