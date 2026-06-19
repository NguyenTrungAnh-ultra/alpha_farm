import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import ast
from .MCTSDimensions import OPERATOR_REGISTRY, DATA_FIELD_DIMENSIONS, Dimension

class ASTNode:
    def __init__(self, name: str, children: list = None, value=None):
        self.name = name
        self.children = children or []
        self.value = value

    def __repr__(self):
        if self.value is not None:
            return str(self.value)
        if self.name == "?":
            return "?"
        args = ", ".join([repr(c) for c in self.children])
        return f"{self.name}({args})"

class SemanticCompilerError(Exception):
    pass

class SemanticCompiler:
    def compile_blueprint(self, blueprint_str: str) -> ASTNode:
        """
        Parses a Macro-Blueprint string into an ASTNode tree and validates 
        Dimensional Consistency (Fail-Fast Drop).
        """
        # ast.parse does not like "?" so replace it with a valid identifier
        safe_str = blueprint_str.replace("?", "__HOLE__")
        try:
            tree = ast.parse(safe_str, mode='eval')
        except SyntaxError as e:
            raise SemanticCompilerError(f"Syntax error in blueprint: {e}")
        
        root_node = self._build_node(tree.body)
        
        # Fail-Fast Drop: Verify dimensions
        out_dim = self._check_dimensions(root_node)
        if out_dim != Dimension.BOOLEAN:
            raise SemanticCompilerError(f"Root node must return BOOLEAN, got {out_dim}")
            
        return root_node

    def _build_node(self, node) -> ASTNode:
        if isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name not in OPERATOR_REGISTRY:
                raise SemanticCompilerError(f"Unknown operator: {func_name}")
            children = [self._build_node(arg) for arg in node.args]
            return ASTNode(name=func_name, children=children)
        elif isinstance(node, ast.Name):
            if node.id == "__HOLE__":
                return ASTNode(name="?")
            elif node.id in DATA_FIELD_DIMENSIONS:
                return ASTNode(name=node.id)
            else:
                raise SemanticCompilerError(f"Unknown data field or identifier: {node.id}")
        elif isinstance(node, ast.Constant):
            return ASTNode(name="Constant", value=node.value)
        elif isinstance(node, ast.Compare):
            raise SemanticCompilerError("Compare operators (e.g. <, >) not allowed. Use functions like crossed_above.")
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                val_node = self._build_node(node.operand)
                if val_node.name == "Constant":
                    val_node.value = -val_node.value
                    return val_node
            raise SemanticCompilerError(f"Unsupported UnaryOp: {type(node.op)}")
        else:
            raise SemanticCompilerError(f"Unsupported AST node type: {type(node)}")

    def _check_dimensions(self, node: ASTNode) -> Dimension:
        if node.name == "?":
            return Dimension.ANY # Placeholders can be anything for now, MCTS will fill them
        elif node.name == "Constant":
            return Dimension.ANY # Constants scale/shift without forcing a unit (usually)
        elif node.name in DATA_FIELD_DIMENSIONS:
            return DATA_FIELD_DIMENSIONS[node.name]
            
        meta = OPERATOR_REGISTRY[node.name]
        expected_dims = meta["input_dims"]
        
        non_constant_children = [c for c in node.children if c.name != "Constant"]
        
        if len(non_constant_children) != len(expected_dims):
            raise SemanticCompilerError(f"Arity mismatch for {node.name}: expected {len(expected_dims)} data args, got {len(non_constant_children)}")
            
        for child, expected_dim in zip(non_constant_children, expected_dims):
            child_dim = self._check_dimensions(child)
            # If expected is ANY, it accepts anything. If child is ANY (placeholder), it assumes it's valid.
            if expected_dim != Dimension.ANY and child_dim != Dimension.ANY:
                if child_dim != expected_dim:
                    raise SemanticCompilerError(f"Dimension mismatch in {node.name}: expected {expected_dim}, got {child_dim}")
                    
        return meta["output_dim"]
