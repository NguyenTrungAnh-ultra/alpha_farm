import os
import ast
from collections import Counter

def get_strategy_parameters(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    
    params = set()
    
    class ParamVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            if node.name == "CustomStrategy":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__algorithm__":
                        self.visit_algorithm(item)
        
        def visit_algorithm(self, func_node):
            for stmt in func_node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                            params.add(target.attr)
    
    visitor = ParamVisitor()
    visitor.visit(tree)
    return list(params)

def main():
    pushed_dir = r"f:\Projects\alpha_farm\agent\results\pushed"
    if not os.path.exists(pushed_dir):
        print(f"Directory not found: {pushed_dir}")
        return

    py_files = [f for f in os.listdir(pushed_dir) if f.endswith(".py") and f != "__init__.py"]
    
    results = {}
    for filename in py_files:
        file_path = os.path.join(pushed_dir, filename)
        params = get_strategy_parameters(file_path)
        if params is not None:
            results[filename] = params
            
    counts = [len(p) for p in results.values()]
    if not counts:
        print("No parameters found.")
        return
        
    c = Counter(counts)
    
    # Generate Markdown report
    md_lines = []
    md_lines.append("# Parameter Analysis for Successfully Submitted Alphas\n")
    md_lines.append(f"Total strategies: {len(results)}\n")
    md_lines.append("## Summary Statistics\n")
    md_lines.append(f"- **Minimum parameters:** {min(counts)}")
    md_lines.append(f"- **Maximum parameters:** {max(counts)}")
    md_lines.append(f"- **Average parameters:** {sum(counts) / len(counts):.2f}\n")
    
    md_lines.append("## Frequency Distribution\n")
    md_lines.append("| Number of Parameters | Count of Strategies |")
    md_lines.append("|---|---|")
    for num_params, count in sorted(c.items()):
        md_lines.append(f"| {num_params} | {count} |")
    md_lines.append("\n")
    
    md_lines.append("## Strategies by Parameter Count\n")
    for num in sorted(c.keys()):
        md_lines.append(f"### {num} Parameters ({c[num]} strategies)\n")
        for filename, params in sorted(results.items()):
            if len(params) == num:
                md_lines.append(f"- **{filename}**: {', '.join(params) if params else 'None'}")
        md_lines.append("")
        
    output_file = r"f:\Projects\alpha_farm\scratch\parameter_analysis.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
        
    print(f"Report written to {output_file}")

if __name__ == "__main__":
    main()
