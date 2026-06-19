import os
import sys
import json

PROJECT_ROOT = r"f:\Projects\alpha_farm"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError

compiler = SemanticCompiler()
ideas_dir = os.path.join(PROJECT_ROOT, "results", "ideas")

for filename in os.listdir(ideas_dir):
    if filename.endswith(".json"):
        filepath = os.path.join(ideas_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        blueprint = data.get("macro_blueprint")
        name = data.get("name")
        print(f"Compiling {name} ({filename}):")
        print(f"  Blueprint: {blueprint}")
        try:
            ast_tree = compiler.compile_blueprint(blueprint)
            print(f"  [SUCCESS] Compiled to AST: {ast_tree}")
        except Exception as e:
            print(f"  [ERROR] {e}")
