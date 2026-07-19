import pytest
from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError
from strategy_workflows.MCTSDimensions import Dimension, TemplateType

def test_compiler_valid_blueprint():
    compiler = SemanticCompiler()
    # crossed_above expects ANY, ANY and returns BOOLEAN
    # ema expects ANY and returns ANY. ? is ANY.
    blueprint = "crossed_above(ema(?, 20), ema(?, 50))"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "crossed_above"
    assert len(ast.children) == 2
    assert ast.children[0].name == "ema"
    assert ast.children[0].children[0].name == "?"

def test_compiler_candlestick_leaf():
    compiler = SemanticCompiler()
    # doji expects 0 args and returns BOOLEAN
    # and_ expects BOOLEAN, BOOLEAN and returns BOOLEAN
    blueprint = "and_(crossed_above(ema(?, 20), ema(?, 50)), doji())"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "and_"
    assert len(ast.children) == 2
    assert ast.children[1].name == "doji"
    assert len(ast.children[1].children) == 0

def test_compiler_arity_mismatch():
    compiler = SemanticCompiler()
    # and_ expects 2 arguments
    blueprint = "and_(doji())"
    with pytest.raises(SemanticCompilerError, match="needs at least 2 children"):
        compiler.compile_blueprint(blueprint)

def test_compiler_dimension_mismatch():
    compiler = SemanticCompiler()
    # and_ expects BOOLEAN inputs. pv_close is ANY/CURRENCY, so it causes mismatch.
    blueprint = "and_(doji(), pv_close)"
    with pytest.raises(SemanticCompilerError, match="Dimension mismatch"):
        compiler.compile_blueprint(blueprint)

def test_compiler_invalid_operator():
    compiler = SemanticCompiler()
    blueprint = "invalid_op(?, 20)"
    with pytest.raises(SemanticCompilerError, match="Unknown operator: invalid_op"):
        compiler.compile_blueprint(blueprint)

def test_compiler_auto_wrap_ratio_root():
    compiler = SemanticCompiler()
    # rsi returns BOUNDED_RATIO. It should be auto-wrapped with ratio_template
    blueprint = "rsi(?, 14)"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "ratio_template"
    assert len(ast.children) == 3
    assert ast.children[0].name == "rsi"
    assert ast.children[1].name == "threshold_upper"
    assert ast.children[2].name == "threshold_lower"

def test_compiler_auto_wrap_normalized_root():
    compiler = SemanticCompiler()
    # macd_line returns NORMALIZED. It should be auto-wrapped with greater_than(zscore(...), z_score)
    blueprint = "macd_line(?)"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "normalized_template"
    assert len(ast.children) == 3
    assert ast.children[0].name == "macd_line"
    assert ast.children[1].name == "window"
    assert ast.children[1].value == "?"
    assert ast.children[2].name == "z_score"
    assert ast.children[2].value == "?"

def test_compiler_few_shot_examples():
    compiler = SemanticCompiler()
    
    # Example 0: div(macd_line(?), stddev(?)) -> NORMALIZED
    ast0 = compiler.compile_blueprint("div(macd_line(?), stddev(?))")
    assert ast0.name == "normalized_template"
    assert ast0.children[0].name == "div"
    
    # Example 2: roc(?) -> pct_change -> NORMALIZED
    ast2 = compiler.compile_blueprint("roc(?)")
    assert ast2.name == "normalized_template"
    assert ast2.children[0].name == "pct_change" # mapped from roc via HALLUCINATION_MAP
