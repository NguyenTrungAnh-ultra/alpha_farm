import pytest
from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError
from strategy_workflows.MCTSDimensions import Dimension

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
    # and_ expects BOOLEAN inputs. ema returns ANY (but it wraps ANY, so if it wraps volume, it returns volume).
    # But wait, and_(doji(), doji()) is valid.
    # What if we pass a CURRENCY field directly into and_?
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
    # rsi returns RATIO. It should be auto-wrapped with greater_than(zscore(rsi), 1.0)
    blueprint = "rsi(?, 14)"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "greater_than"
    assert len(ast.children) == 2
    assert ast.children[0].name == "zscore"
    assert ast.children[0].children[0].name == "rsi"
    assert ast.children[1].name == "Constant"
    assert ast.children[1].value == 1.0

def test_compiler_few_shot_examples():
    compiler = SemanticCompiler()
    
    # Example 0: div(macd_line(?), stddev(?))
    ast0 = compiler.compile_blueprint("div(macd_line(?), stddev(?))")
    assert ast0.name == "greater_than"
    assert ast0.children[0].name == "zscore"
    assert ast0.children[0].children[0].name == "div"
    
    # Example 1: div(sub(vwap(), ema(?)), stddev(?))
    ast1 = compiler.compile_blueprint("div(sub(vwap(), ema(?)), stddev(?))")
    assert ast1.name == "greater_than"
    assert ast1.children[0].children[0].name == "div"
    
    # Example 2: zscore(roc(?))
    ast2 = compiler.compile_blueprint("zscore(roc(?))")
    assert ast2.name == "greater_than"
    assert ast2.children[0].children[0].name == "zscore"
    assert ast2.children[0].children[0].children[0].name == "pct_change" # mapped from roc via HALLUCINATION_MAP
    
    # Example 3: div(mult(rsi(?), var(?)), stddev(?))
    ast3 = compiler.compile_blueprint("div(mult(rsi(?), var(?)), stddev(?))")
    assert ast3.name == "greater_than"
    assert ast3.children[0].children[0].name == "div"


