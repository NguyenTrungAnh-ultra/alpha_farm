import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import ast
from utilities.AppConfig import MCTS_MAX_DEPTH
from .MCTSDimensions import OPERATOR_REGISTRY, DATA_FIELD_DIMENSIONS, Dimension, analyze_dimensions

class ASTNode:
    def __init__(self, name: str, children: list = None, value=None, window: int = None):
        self.name = name
        self.children = children or []
        self.value = value
        # Rolling-window length of a TIME_SERIES node; None until the search fixes it.
        self.window = window

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
    "boll": "ts_mean",
    "bollinger_band_upper": "ts_mean",
    "bollinger_band_lower": "ts_mean",
    "sma": "ts_mean",
    "wma": "ts_mean",
    "dema": "ts_mean",
    "tema": "ts_mean",
    "kama": "ts_mean",
    "natr": "?",
    "atr": "?",
    "trange": "?",
    "linearreg_slope": "?",
    "cmf": "?",
    "roc": "?",
    "mom": "?",
    "max": "ts_max",
    "min": "ts_min",
    "highest": "ts_max",
    "lowest": "ts_min",
}

def count_slots(node: ASTNode) -> int:
    """Number of open `?` series slots in a compiled tree (template window/threshold slots are not counted)."""
    return (1 if node.name == "?" else 0) + sum(count_slots(c) for c in node.children)


class SemanticCompiler:
    def compile_open_blueprint(self, blueprint_str: str, max_depth: int = MCTS_MAX_DEPTH) -> ASTNode:
        """
        Compile a blueprint and require at least one `?` series slot, and that every slot can
        be filled within `max_depth` (the MCTS depth limit) so that the tree stays dimensionally valid.

        A blueprint without a slot leaves the search only windows and thresholds to tune, so it
        is rejected with a message meant to be fed back to the LLM.
        """
        root = self.compile_blueprint(blueprint_str)
        if count_slots(root) == 0:
            raise SemanticCompilerError(
                f"Blueprint `{blueprint_str}` has no `?` slot. Every blueprint must contain at least "
                "one `?` (prefer 2-3): replace the open parts (a data field or a whole sub-formula) "
                "with `?`, e.g. `sub(ts_mean(?), ts_mean(?))`."
            )
        analysis = analyze_dimensions(root, max_depth)
        if analysis.error:
            raise SemanticCompilerError(
                f"Blueprint `{blueprint_str}` cannot be completed within the depth limit of {max_depth}: "
                f"{analysis.error}. A `?` that must be dimensionless (RATIO), e.g. inside a `mult` or beside "
                "a `ts_zscore`, needs extra nesting under every rolling operator. Use a shallower skeleton."
            )
        return root

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
        root_dims = self._analyze(root_node).root_dims

        from .MCTSDimensions import TemplateType, DIMENSION_TO_TEMPLATE
        # The declared kind of the root operator picks the template, not the inferred dimension:
        # `div` is declared RATIO although it can also return the dimension of its numerator.
        root_meta = OPERATOR_REGISTRY.get(root_node.name)
        if root_dims == frozenset({Dimension.BOOLEAN}):
            out_dim = Dimension.BOOLEAN
        elif root_meta is not None and root_meta["output_dim"] == Dimension.RATIO:
            out_dim = Dimension.RATIO
        else:
            out_dim = Dimension.ANY
        template = DIMENSION_TO_TEMPLATE.get(out_dim, TemplateType.NORMALIZED)
        
        if template == TemplateType.NORMALIZED:
            root_node = ASTNode(name="normalized_template", children=[
                root_node,
                ASTNode(name="window", value="?"),
                ASTNode(name="z_score", value="?")
            ])
        elif template == TemplateType.RATIO:
            root_node = ASTNode(name="ratio_template", children=[
                root_node,
                ASTNode(name="threshold_upper", value="?"),
                ASTNode(name="threshold_lower", value="?")
            ])
        elif template == TemplateType.BOOLEAN:
            # Boolean giữ nguyên
            pass
            
        # We wrapped it in a template (or it's already boolean), so it resolves to BOOLEAN signal
        out_dim = Dimension.BOOLEAN
            
        if out_dim != Dimension.BOOLEAN:
            raise SemanticCompilerError(f"Root node must return BOOLEAN, got {out_dim}")

        # The wrapped tree must still be valid (a ratio_template needs a RATIO child).
        self._analyze(root_node)
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

    def _analyze(self, node: ASTNode, max_depth: int = None):
        """
        Run the dimension inference (see `analyze_dimensions`) and raise on the first invalid node.

        Dimensions propagate through every operator, so a mismatch is caught at any depth, and a
        blueprint whose `?` slots cannot take any dimension that keeps the tree valid is rejected.
        """
        analysis = analyze_dimensions(node, max_depth)
        if analysis.error:
            raise SemanticCompilerError(analysis.error)
        return analysis

    def _check_dimensions(self, node: ASTNode) -> Dimension:
        """
        Dimension of a tree: the single dimension it must have, or ANY while `?` slots leave
        several possible. Raises SemanticCompilerError on arity, dimension or bleeding errors.
        """
        dims = self._analyze(node).root_dims
        return next(iter(dims)) if len(dims) == 1 else Dimension.ANY
