"""Errores de cara al usuario.

Cada error tiene un `code` estable (el frontend puede reaccionar a él) y un
mensaje en español listo para mostrar. Los detalles técnicos van al log, nunca
al usuario.
"""

from __future__ import annotations

USER_MESSAGES: dict[str, str] = {
    # petición
    "auth_required": "Inicia sesión para continuar.",
    "not_found": "No hemos encontrado lo que buscas.",
    "validation_error": "Revisa los datos enviados.",
    # cuotas y planes
    "quota_exceeded": "Has agotado los minutos de tu plan este mes.",
    "video_too_long": "El vídeo es más largo de lo que permite tu plan.",
    "too_many_jobs": "Ya tienes el máximo de vídeos procesándose a la vez. Espera a que termine alguno.",
    "too_many_clips": "Tu plan no permite tantos clips por vídeo.",
    # subidas
    "upload_too_large": "El archivo supera el tamaño máximo de tu plan.",
    "unsupported_format": "Formato no compatible. Sube un vídeo MP4, MOV, MKV o WEBM.",
    "upload_incomplete": "La subida no se completó. Vuelve a intentarlo.",
    "upload_not_ready": "El vídeo todavía no está listo para procesarse.",
    "invalid_video": "No hemos podido leer el vídeo. Comprueba que el archivo no esté dañado.",
    # procesamiento
    "no_speech": "No hemos detectado voz en el vídeo; SmartCuts necesita diálogo para elegir los clips.",
    "processing_failed": "Algo falló al procesar el vídeo. No se te han descontado minutos; inténtalo de nuevo.",
    "worker_lost": "El procesamiento se interrumpió. No se te han descontado minutos; inténtalo de nuevo.",
    "internal_error": "Ha ocurrido un error inesperado. Ya estamos avisados.",
}


def user_message(code: str | None) -> str | None:
    if code is None:
        return None
    return USER_MESSAGES.get(code, USER_MESSAGES["internal_error"])


class AppError(Exception):
    def __init__(self, code: str, status: int = 400, *, message: str | None = None, detail: str | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.message = message or user_message(code) or code
        self.detail = detail


class NotFound(AppError):
    def __init__(self) -> None:
        super().__init__("not_found", 404)
