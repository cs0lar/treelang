import treelang


def test_public_api_exports_core_types():
    assert treelang.AST is not None
    assert treelang.TreeProgram is not None
    assert treelang.ToolProvider is not None
    assert treelang.CURRENT_SCHEMA_VERSION == "1.0"
    assert treelang.__version__
    assert isinstance(treelang.ast_json_schema(), str)
    assert isinstance(treelang.ast_examples(), str)


def test_public_api_declares_every_export():
    assert all(hasattr(treelang, name) for name in treelang.__all__)
