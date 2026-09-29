"""Jerarquía de errores de negocio.

`retryable` indica a la capa superior (CLI, futura cola de workers) si tiene
sentido reintentar la operación.
"""


class ClipasoError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class ConfigurationError(ClipasoError):
    pass


class UnsupportedSourceError(ClipasoError):
    pass


class SourceUnavailableError(ClipasoError):
    retryable = True


class TranscriptionError(ClipasoError):
    pass


class SelectionError(ClipasoError):
    pass


class LLMError(ClipasoError):
    retryable = True


class BudgetExceededError(ClipasoError):
    pass


class RenderError(ClipasoError):
    pass
