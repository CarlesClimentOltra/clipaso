"""Jerarquía de errores de negocio.

`retryable` indica a la capa superior (CLI, futura cola de workers) si tiene
sentido reintentar la operación.
"""


class SmartCutsError(Exception):
    retryable: bool = False

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class ConfigurationError(SmartCutsError):
    pass


class UnsupportedSourceError(SmartCutsError):
    pass


class SourceUnavailableError(SmartCutsError):
    retryable = True


class TranscriptionError(SmartCutsError):
    pass


class SelectionError(SmartCutsError):
    pass


class LLMError(SmartCutsError):
    retryable = True


class BudgetExceededError(SmartCutsError):
    pass


class RenderError(SmartCutsError):
    pass
