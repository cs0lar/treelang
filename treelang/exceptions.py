"""Public exception hierarchy for Treelang."""


class TreelangError(Exception):
    """Base class for errors raised by Treelang."""


class ToolNotFoundError(TreelangError, ValueError):
    """Raised when a provider does not expose a requested tool."""


class ToolExecutionError(TreelangError, RuntimeError):
    """Raised when a provider reports that a tool invocation failed."""


class ProviderResponseError(TreelangError, RuntimeError):
    """Raised when a provider returns an invalid response."""


class ModelTransportError(ProviderResponseError):
    """Normalized failure returned by a model transport SDK."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)


class ModelAuthenticationError(ModelTransportError):
    """Raised when a model provider rejects authentication or authorization."""


class ModelRateLimitError(ModelTransportError):
    """Raised when a model provider reports exhausted request capacity."""


class ModelTimeoutError(ModelTransportError, TimeoutError):
    """Raised when the provider SDK times out a model request."""


class ModelConnectionError(ModelTransportError, ConnectionError):
    """Raised when the provider SDK cannot reach its model service."""


class ReplayMismatchError(ProviderResponseError):
    """Raised when runtime activity diverges from a deterministic replay."""


class StructuredOutputUnsupportedError(ProviderResponseError):
    """Raised when a provider rejects strict structured-output configuration."""


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
