import pytest
from strategy_workflows.SemanticCompiler import SemanticCompiler, SemanticCompilerError
from strategy_workflows.MCTSDimensions import Dimension, TemplateType

def test_compiler_valid_blueprint():
    compiler = SemanticCompiler()
    # crossed_above expects ANY, ANY and returns BOOLEAN
    # ts_mean expects ANY and returns ANY. ? is ANY.
    blueprint = "crossed_above(ts_mean(?, 20), ts_mean(?, 50))"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "crossed_above"
    assert len(ast.children) == 2
    assert ast.children[0].name == "ts_mean"
    assert ast.children[0].children[0].name == "?"

def test_compiler_logic_leaf():
    compiler = SemanticCompiler()
    # crossed expects ANY, ANY and returns BOOLEAN
    # and_ expects BOOLEAN, BOOLEAN and returns BOOLEAN
    blueprint = "and_(crossed_above(ts_mean(?, 20), ts_mean(?, 50)), crossed(?, ?))"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "and_"
    assert len(ast.children) == 2
    assert ast.children[1].name == "crossed"
    assert len(ast.children[1].children) == 2

def test_compiler_arity_mismatch():
    compiler = SemanticCompiler()
    # and_ expects 2 arguments
    blueprint = "and_(crossed(?, ?))"
    with pytest.raises(SemanticCompilerError, match="needs at least 2 children"):
        compiler.compile_blueprint(blueprint)

def test_compiler_dimension_mismatch():
    compiler = SemanticCompiler()
    # and_ expects BOOLEAN inputs. pv_close is ANY/CURRENCY, so it causes mismatch.
    blueprint = "and_(crossed(?, ?), pv_close)"
    with pytest.raises(SemanticCompilerError, match="Dimension mismatch"):
        compiler.compile_blueprint(blueprint)

def test_compiler_invalid_operator():
    compiler = SemanticCompiler()
    blueprint = "invalid_op(?, 20)"
    with pytest.raises(SemanticCompilerError, match="Unknown operator: invalid_op"):
        compiler.compile_blueprint(blueprint)

def test_compiler_auto_wrap_ratio_root():
    compiler = SemanticCompiler()
    # ts_rank returns RATIO. It should be auto-wrapped with ratio_template
    blueprint = "ts_rank(?, 14)"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "ratio_template"
    assert len(ast.children) == 3
    assert ast.children[0].name == "ts_rank"
    assert ast.children[1].name == "threshold_upper"
    assert ast.children[2].name == "threshold_lower"

def test_compiler_auto_wrap_normalized_root():
    compiler = SemanticCompiler()
    # ts_mean returns ANY. It should be auto-wrapped with normalized_template
    blueprint = "ts_mean(?)"
    ast = compiler.compile_blueprint(blueprint)
    
    assert ast.name == "normalized_template"
    assert len(ast.children) == 3
    assert ast.children[0].name == "ts_mean"
    assert ast.children[1].name == "window"
    assert ast.children[1].value == "?"
    assert ast.children[2].name == "z_score"
    assert ast.children[2].value == "?"

def test_compiler_few_shot_examples():
    compiler = SemanticCompiler()
    
    # Example 0: div(ts_mean(?), ts_max(?)) -> RATIO
    ast0 = compiler.compile_blueprint("div(ts_mean(?), ts_max(?))")
    assert ast0.name == "ratio_template"
    assert ast0.children[0].name == "div"
    
    # Example 2: sma(?) -> ts_mean -> NORMALIZED
    ast2 = compiler.compile_blueprint("sma(?)")
    assert ast2.name == "normalized_template"
    assert ast2.children[0].name == "ts_mean" # mapped from sma via HALLUCINATION_MAP
