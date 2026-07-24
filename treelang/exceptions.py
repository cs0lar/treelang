"""Public exception hierarchy for Treelang."""


class TreelangError(Exception):
    """Base class for errors raised by Treelang."""


class ToolNotFoundError(TreelangError, ValueError):
    """Raised when a provider does not expose a requested tool."""


class ToolExecutionError(TreelangError, RuntimeError):
    """Raised when a provider reports that a tool invocation failed."""


class ProviderResponseError(TreelangError, RuntimeError):
    """Raised when a provider returns an invalid response."""


class ASTCompilationError(TreelangError, ValueError):
    """Raised when an AST cannot be compiled into a callable tool."""


class ASTValidationError(TreelangError, ValueError):
    """Raised when an AST violates a runtime tool contract."""


class ASTExecutionError(TreelangError, RuntimeError):
    """Raised when an AST fails during execution."""


class ExecutionLimitError(ASTExecutionError):
    """Raised when an AST invocation exceeds a configured resource limit."""

    def __init__(self, resource: str, limit: int | float) -> None:
        self.resource = resource
        self.limit = limit
        super().__init__(f"Execution {resource} limit exceeded ({limit})")
