import treelang


def test_public_api_exports_core_types():
    assert treelang.AST is not None
    assert treelang.AnthropicTransport is not None
    assert treelang.TreeProgram is not None
    assert treelang.ToolProvider is not None
    assert treelang.TreePath is not None
    assert treelang.TreeChange is not None
    assert treelang.TransformationRecord is not None
    assert treelang.TransformResult is not None
    assert treelang.ConservativeTreePruner is not None
    assert treelang.prune_tree is not None
    assert treelang.graft_expression is not None
    assert treelang.compose_programs is not None
    assert treelang.TreePruner is not None
    assert treelang.TreeGrower is not None
    assert treelang.AsyncTreeGrower is not None
    assert treelang.GrowthOptions is not None
    assert treelang.ProgramCompositionGrower is not None
    assert treelang.wrap_expression is not None
    assert treelang.TransformationLimits is not None
    assert issubclass(treelang.TreeTransformationError, ValueError)
    assert treelang.ExecutionLimits is not None
    assert treelang.ExecutionPolicy is not None
    assert treelang.RetryPolicy is not None
    assert treelang.BranchOutcome is not None
    assert treelang.ToolReplayProvider is not None
    assert treelang.ModelReplayTransport is not None
    assert treelang.ModelCapabilities is not None
    assert treelang.ModelCapabilityNegotiator is not None
    assert treelang.CapabilityAwareTransport is not None
    assert treelang.ModelTransport is not None
    assert treelang.UsageAwareTransport is not None
    assert issubclass(treelang.ModelTransportError, treelang.ProviderResponseError)
    assert issubclass(treelang.ModelTimeoutError, TimeoutError)
    assert issubclass(treelang.ExecutionLimitError, treelang.ASTExecutionError)
    assert issubclass(treelang.ReplayMismatchError, treelang.ProviderResponseError)
    assert issubclass(
        treelang.StructuredOutputUnsupportedError,
        treelang.ProviderResponseError,
    )
    assert treelang.CURRENT_SCHEMA_VERSION == "1.0"
    assert treelang.__version__
    assert isinstance(treelang.ast_json_schema(), str)
    assert isinstance(treelang.ast_examples(), str)


def test_public_api_declares_every_export():
    assert all(hasattr(treelang, name) for name in treelang.__all__)
