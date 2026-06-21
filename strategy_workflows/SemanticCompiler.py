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

HALLUCINATION_MAP = {
    "price": "?",
    "close": "?",
    "open": "?",
    "high": "?",
    "low": "?",
    "volume": "?",
    "boll": "ema",
    "bollinger_band_upper": "ema",
    "bollinger_band_lower": "ema",
    "sma": "ema",
    "wma": "ema",
    "dema": "ema",
    "tema": "ema",
    "kama": "ema",
    "natr": "stddev",
    "atr": "stddev",
    "trange": "stddev",
    "linearreg_slope": "diff",
    "cmf": "vwap",
    "roc": "pct_change",
    "mom": "diff"
}

class SemanticCompiler:
    def compile_blueprint(self, blueprint_str: str) -> ASTNode:
        """
        Parse a Macro-Blueprint string into an ASTNode tree and validate dimensional consistency.
        
        This performs a "Fail-Fast Drop" by analyzing the input expression using Python's
        built-in ast module. It translates the parsed expression into custom ASTNode representation,
        verifies that the dimensions match, automatically wraps ratio/currency outputs into boolean
        signals using a Z-score comparison, and ensures the root node ultimately resolves to a 
        boolean value.
        
        Parameters
        ----------
        blueprint_str : str
            The macro blueprint mathematical/logical formula expression to compile.
            
        Returns
        -------
        ASTNode
            The validated and compiled root ASTNode of the formula.
            
        Raises
        ------
        SemanticCompilerError
            If there are syntax errors, dimension mismatches, unsupported nodes, or if the
            root expression cannot be compiled to a boolean signal.
        """
        safe_str = blueprint_str.replace("?", "__HOLE__")
        try:
            tree = ast.parse(safe_str, mode='eval')
        except SyntaxError as e:
            raise SemanticCompilerError(f"Syntax error in blueprint: {e}")
        
        root_node = self._build_node(tree.body)
        
        # Fail-Fast Drop: Verify dimensions
        out_dim = self._check_dimensions(root_node)
        
        if out_dim in (Dimension.RATIO, Dimension.CURRENCY):
            # Auto-wrap RATIO and CURRENCY to produce a BOOLEAN signal via Z-score cut
            zscore_node = ASTNode(name="zscore", children=[root_node])
            # Pass '?' so MCTS can search over [0.5, 1.0, 1.5, 2.0, 2.5] instead of hardcoding 1.0
            constant_node = ASTNode(name="z_score", value="?")
            root_node = ASTNode(name="greater_than", children=[zscore_node, constant_node])
            out_dim = Dimension.BOOLEAN
            
        if out_dim != Dimension.BOOLEAN:
            raise SemanticCompilerError(f"Root node must return BOOLEAN, got {out_dim}")
            
        return root_node

    def _build_node(self, node) -> ASTNode:
        """
        Recursively construct a custom ASTNode tree from Python's abstract syntax tree.
        
        Maps Python ast objects (ast.Call, ast.Name, ast.Constant, ast.Compare, etc.) 
        to custom ASTNode instances. This method also handles mapping hallucinated functions
        to standard operators, stashing placeholder nodes, padding missing arguments, 
        and parsing comparison and boolean operations.
        
        Parameters
        ----------
        node : ast.AST
            The Python AST node to transform.
            
        Returns
        -------
        ASTNode
            The constructed custom ASTNode.
            
        Raises
        ------
        SemanticCompilerError
            If an unsupported node type is encountered, or operator/argument mismatches occur.
        """
        if isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name in HALLUCINATION_MAP:
                func_name = HALLUCINATION_MAP[func_name]
                if func_name == "?":
                    return ASTNode(name="?")

            if func_name in ["and_", "or_"]:
                children = [self._build_node(arg) for arg in node.args]
                if len(children) < 2:
                    raise SemanticCompilerError(f"{func_name} needs at least 2 children")
                res = ASTNode(name=func_name, children=[children[0], children[1]])
                for c in children[2:]:
                    res = ASTNode(name=func_name, children=[res, c])
                return res

            if func_name not in OPERATOR_REGISTRY:
                raise SemanticCompilerError(f"Unknown operator: {func_name}")
            children = [self._build_node(arg) for arg in node.args]
            
            # Auto-pad missing data arguments with '?'
            meta = OPERATOR_REGISTRY[func_name]
            expected_data_args = len(meta["input_dims"])
            non_constant_children = [c for c in children if c.name != "Constant"]
            if len(non_constant_children) < expected_data_args:
                missing = expected_data_args - len(non_constant_children)
                for _ in range(missing):
                    children.insert(0, ASTNode(name="?"))
                    
            return ASTNode(name=func_name, children=children)
        elif isinstance(node, ast.Name):
            name_id = node.id
            if name_id in HALLUCINATION_MAP:
                name_id = HALLUCINATION_MAP[name_id]

            if name_id == "?" or name_id == "__HOLE__":
                return ASTNode(name="?")
            elif name_id in DATA_FIELD_DIMENSIONS:
                return ASTNode(name=name_id)
            else:
                raise SemanticCompilerError(f"Unknown data field or identifier: {node.id}")
        elif isinstance(node, ast.Constant):
            return ASTNode(name="Constant", value=node.value)
        elif isinstance(node, ast.Compare):
            if len(node.ops) == 1:
                op = node.ops[0]
                left = self._build_node(node.left)
                right = self._build_node(node.comparators[0])
                if isinstance(op, ast.Gt) or isinstance(op, ast.GtE):
                    return ASTNode(name="greater_than", children=[left, right])
                elif isinstance(op, ast.Lt) or isinstance(op, ast.LtE):
                    return ASTNode(name="less_than", children=[left, right])
                elif isinstance(op, ast.Eq):
                    return ASTNode(name="equal", children=[left, right])
                elif isinstance(op, ast.NotEq):
                    return ASTNode(name="not_", children=[ASTNode(name="equal", children=[left, right])])
            raise SemanticCompilerError("Complex compare operators not supported. Keep it simple like a > b.")
        elif isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                func_name = "and_"
            elif isinstance(node.op, ast.Or):
                func_name = "or_"
            else:
                raise SemanticCompilerError(f"Unsupported BoolOp: {type(node.op)}")
                
            children = [self._build_node(v) for v in node.values]
            if len(children) < 2:
                raise SemanticCompilerError(f"BoolOp needs at least 2 children")
            
            res = ASTNode(name=func_name, children=[children[0], children[1]])
            for c in children[2:]:
                res = ASTNode(name=func_name, children=[res, c])
            return res
        elif isinstance(node, ast.Tuple):
            children = [self._build_node(elt) for elt in node.elts]
            if len(children) == 0:
                raise SemanticCompilerError("Empty tuple not supported")
            res = ASTNode(name="and_", children=[children[0], children[1]]) if len(children) >= 2 else children[0]
            for c in children[2:]:
                res = ASTNode(name="and_", children=[res, c])
            return res
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
        """
        Recursively check the dimensional consistency of an ASTNode tree.
        
        Ensures that data fields, operators, and their arguments are compatible
        based on the definitions in OPERATOR_REGISTRY and DATA_FIELD_DIMENSIONS.
        Verifies arity matches and guards against dimensional bleeding (mixing different
        units like volume and price in addition/subtraction or comparison operators).
        
        Parameters
        ----------
        node : ASTNode
            The ASTNode to perform dimensional check on.
            
        Returns
        -------
        Dimension
            The resolved output dimension of the node.
            
        Raises
        ------
        SemanticCompilerError
            If an arity mismatch, dimension mismatch, or dimensional bleeding is detected.
        """
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
            
        child_dims = []
        for child, expected_dim in zip(non_constant_children, expected_dims):
            child_dim = self._check_dimensions(child)
            child_dims.append(child_dim)
            # If expected is ANY, it accepts anything. If child is ANY (placeholder), it assumes it's valid.
            if expected_dim != Dimension.ANY and child_dim != Dimension.ANY:
                if child_dim != expected_dim:
                    raise SemanticCompilerError(f"Dimension mismatch in {node.name}: expected {expected_dim}, got {child_dim}")
                    
        # Check for Dimensional Bleeding on specific operators
        if node.name in ['add', 'sub', 'crossed', 'crossed_above', 'crossed_below', 'greater_than', 'less_than', 'equal']:
            resolved_dims = set(d for d in child_dims if d != Dimension.ANY)
            if len(resolved_dims) > 1:
                raise SemanticCompilerError(f"Dimensional Bleeding in {node.name}: inputs have mixed dimensions {resolved_dims}")

        return meta["output_dim"]
