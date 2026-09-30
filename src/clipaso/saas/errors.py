"""Errores de cara al usuario, en español e inglés.

Cada error tiene un `code` estable (el frontend puede reaccionar a él) y un mensaje listo para
mostrar en el idioma de la petición (`Accept-Language`). Los mensajes con datos son plantillas
(`{limit}`…) que se rellenan con los `params` del error. Los detalles técnicos van al log, nunca
al usuario.
"""

from __future__ import annotations

from contextvars import ContextVar

LANGS = ("es", "en")
DEFAULT_LANG = "es"
# Idioma de la petición en curso (lo fija un middleware de la API a partir de Accept-Language).
request_lang: ContextVar[str] = ContextVar("request_lang", default=DEFAULT_LANG)

MESSAGES: dict[str, dict[str, str]] = {
    # petición
    "auth_required": {"es": "Inicia sesión para continuar.", "en": "Please sign in to continue."},
    "not_found": {"es": "No hemos encontrado lo que buscas.", "en": "We couldn't find what you're looking for."},
    "validation_error": {"es": "Revisa los datos enviados.", "en": "Please check the data you sent."},
    # cuotas y planes
    "quota_exceeded": {"es": "Has agotado los minutos de tu plan este mes.",
                       "en": "You've used up your plan's minutes for this month."},
    "quota_detail": {"es": "Este vídeo necesita {needed} min y te quedan {remaining} min de tu plan este mes.",
                     "en": "This video needs {needed} min and you have {remaining} min left this month."},
    "video_too_long": {"es": "El vídeo es más largo de lo que permite tu plan.",
                       "en": "The video is longer than your plan allows."},
    "video_too_long_detail": {"es": "El vídeo dura {minutes} min y tu plan permite hasta {limit} min por vídeo.",
                              "en": "The video is {minutes} min long and your plan allows up to {limit} min "
                                    "per video."},
    "too_many_jobs": {"es": "Ya tienes el máximo de vídeos procesándose a la vez. Espera a que termine alguno.",
                      "en": "You already have the maximum number of videos processing. Wait for one to finish."},
    "too_many_clips": {"es": "Tu plan no permite tantos clips por vídeo.",
                       "en": "Your plan doesn't allow that many clips per video."},
    "plan_clip_limit": {"es": "Tu plan permite hasta {limit} clips por vídeo.",
                        "en": "Your plan allows up to {limit} clips per video."},
    "project_clip_limit": {"es": "Este proyecto ya tiene el máximo de clips de tu plan.",
                           "en": "This project already has the maximum number of clips for your plan."},
    # edición y tareas
    "source_unavailable": {
        "es": "El vídeo original de este proyecto ya no está guardado, así que no se puede editar ni pedir más "
              "clips. Vuelve a subirlo si lo necesitas.",
        "en": "This project's original video is no longer stored, so it can't be edited or used for more "
              "clips. Upload it again if you need to.",
    },
    "no_transcript": {"es": "Este proyecto no tiene transcripción guardada.",
                      "en": "This project has no saved transcript."},
    "clip_duration": {"es": "Un clip debe durar entre {min} y {max} segundos.",
                      "en": "A clip must be between {min} and {max} seconds long."},
    "clip_busy": {"es": "Este clip se está generando. Espera a que termine.",
                  "en": "This clip is being generated. Please wait for it to finish."},
    "more_clips_busy": {"es": "Ya estamos buscando más clips de este vídeo.",
                        "en": "We're already looking for more clips in this video."},
    "too_many_tasks": {"es": "Tienes varios clips generándose. Espera a que termine alguno.",
                       "en": "You have several clips being generated. Wait for one to finish."},
    "no_more_clips": {"es": "No hemos encontrado más momentos que merezcan un clip.",
                      "en": "We couldn't find any more moments worth a clip."},
    "export_quality_unavailable": {"es": "Esa calidad no está disponible para este clip.",
                                   "en": "That quality isn't available for this clip."},
    "cover_busy": {"es": "Ya estamos preparando otra portada para este clip.",
                   "en": "We're already preparing another cover for this clip."},
    "bad_image": {"es": "No hemos podido leer la imagen. Prueba con un JPG o PNG.",
                  "en": "We couldn't read the image. Try a JPG or PNG."},
    "cover_frame": {"es": "No hemos podido sacar ese fotograma del vídeo. Prueba con otro momento.",
                    "en": "We couldn't get that frame from the video. Try another moment."},
    "thumbnail_frames": {"es": "No hemos podido leer los fotogramas del vídeo. Prueba con otro archivo.",
                         "en": "We couldn't read the video frames. Try another file."},
    "too_many_thumbnails": {"es": "Has creado muchas miniaturas hoy (máximo {max}). Vuelve a intentarlo mañana.",
                            "en": "You've created a lot of thumbnails today (up to {max}). Try again tomorrow."},
    "render_failed": {"es": "Algo falló al generar el clip. Inténtalo de nuevo.",
                      "en": "Something went wrong generating the clip. Please try again."},
    "archive_expired": {"es": "El enlace de descarga ha caducado. Vuelve a pulsar «Descargar todos».",
                        "en": "The download link has expired. Click “Download all” again."},
    "delete_while_processing": {"es": "No se puede borrar un vídeo mientras se procesa.",
                                "en": "A video can't be deleted while it's processing."},
    # marca
    "logo_too_big": {"es": "El logo debe ocupar 1 MB como máximo.", "en": "The logo must be 1 MB or smaller."},
    "logo_invalid": {"es": "El logo debe ser una imagen PNG o JPG de 1 MB como máximo.",
                     "en": "The logo must be a PNG or JPG image of 1 MB or less."},
    "logo_unreadable": {"es": "No hemos podido leer la imagen. Prueba con un PNG o JPG.",
                        "en": "We couldn't read the image. Try a PNG or JPG."},
    "logo_unprocessable": {"es": "No hemos podido procesar la imagen.", "en": "We couldn't process the image."},
    # estilos de subtítulos
    "style_limit": {"es": "Puedes guardar hasta {max} estilos propios. Borra alguno para crear otro.",
                    "en": "You can save up to {max} custom styles. Delete one to create another."},
    "style_name": {"es": "Ponle un nombre al estilo.", "en": "Give the style a name."},
    # cuenta
    "account_busy": {"es": "Tienes vídeos procesándose. Espera a que terminen para eliminar tu cuenta.",
                     "en": "You have videos processing. Wait for them to finish before deleting your account."},
    # subidas
    "plan_required": {"es": "Tu plan no incluye esta opción.", "en": "Your plan doesn't include this option."},
    "daily_renders": {"es": "Has llegado a las {limit} ediciones de clip diarias de tu plan. Vuelve mañana o mejora "
                            "tu plan.",
                      "en": "You've reached your plan's {limit} clip edits per day. Come back tomorrow or upgrade."},
    "daily_more_clips": {"es": "Has llegado a las {limit} peticiones de «Más clips» diarias de tu plan. Vuelve "
                               "mañana o mejora tu plan.",
                         "en": "You've reached your plan's {limit} «More clips» requests per day. Come back tomorrow "
                               "or upgrade."},
    "daily_exports": {"es": "Has llegado a las {limit} descargas en otra calidad diarias de tu plan. Vuelve mañana o "
                            "mejora tu plan.",
                      "en": "You've reached your plan's {limit} downloads in another quality per day. Come back "
                            "tomorrow or upgrade."},
    "daily_covers": {"es": "Has llegado a las {limit} portadas nuevas diarias de tu plan. Vuelve mañana o mejora tu "
                           "plan.",
                     "en": "You've reached your plan's {limit} new covers per day. Come back tomorrow or upgrade."},
    "email_disposable": {"es": "No admitimos correos temporales. Regístrate con tu correo habitual.",
                         "en": "Temporary email addresses aren't allowed. Sign up with your usual email."},
    "too_many_accounts": {"es": "Se han creado demasiadas cuentas desde esta conexión. Si crees que es un error, "
                                "escríbenos.",
                          "en": "Too many accounts have been created from this connection. If you think this is a "
                                "mistake, contact us."},
    "captcha_failed": {"es": "No hemos podido comprobar que eres una persona. Vuelve a intentarlo.",
                       "en": "We couldn't verify you're human. Please try again."},
    "rate_limited": {"es": "Demasiadas peticiones seguidas. Espera un momento y vuelve a intentarlo.",
                     "en": "Too many requests in a row. Wait a moment and try again."},
    "plan_quality": {"es": "La descarga en {quality} está disponible en el plan Ultra.",
                     "en": "The {quality} download is available on the Ultra plan."},
    "audio_needs_audio_mode": {"es": "Con un archivo de audio puedes crear un audiograma o pasarlo a texto.",
                               "en": "With an audio file you can create an audiogram or turn it into text."},
    "trim_too_short": {"es": "El tramo elegido debe durar al menos {min} segundos.",
                       "en": "The selected part must be at least {min} seconds long."},
    "upload_too_large": {"es": "El archivo supera el tamaño máximo de tu plan.",
                         "en": "The file exceeds your plan's maximum size."},
    "unsupported_format": {"es": "Formato no compatible. Sube un vídeo MP4, MOV, MKV o WEBM.",
                           "en": "Unsupported format. Upload an MP4, MOV, MKV or WEBM video."},
    "upload_incomplete": {"es": "La subida no se completó. Vuelve a intentarlo.",
                          "en": "The upload didn't complete. Please try again."},
    "upload_inactive": {"es": "Esta subida ya no está activa. Vuelve a elegir el vídeo.",
                        "en": "This upload is no longer active. Choose the video again."},
    "upload_missing_parts": {"es": "Faltan partes del vídeo por subir. Vuelve a intentarlo.",
                             "en": "Some parts of the video are missing. Please try again."},
    "upload_not_ready": {"es": "El vídeo todavía no está listo para procesarse.",
                         "en": "The video isn't ready to be processed yet."},
    "invalid_video": {"es": "No hemos podido leer el vídeo. Comprueba que el archivo no esté dañado.",
                      "en": "We couldn't read the video. Check that the file isn't damaged."},
    # procesamiento
    "no_speech": {"es": "No hemos detectado voz en el vídeo; Clipaso necesita diálogo para elegir los clips.",
                  "en": "We didn't detect speech in the video; Clipaso needs dialogue to pick clips."},
    "processing_failed": {"es": "Algo falló al procesar el vídeo. No se te han descontado minutos; inténtalo de nuevo.",
                          "en": "Something went wrong processing the video. No minutes were charged; please try "
                                "again."},
    "worker_lost": {"es": "El procesamiento se interrumpió. No se te han descontado minutos; inténtalo de nuevo.",
                    "en": "Processing was interrupted. No minutes were charged; please try again."},
    "internal_error": {"es": "Ha ocurrido un error inesperado. Ya estamos avisados.",
                       "en": "An unexpected error occurred. We've been notified."},
}


def normalize_lang(value: str | None) -> str:
    """Idioma a partir de un código o de una cabecera Accept-Language («en-GB,en;q=0.9» → «en»)."""
    for part in (value or "").split(","):
        tag = part.split(";")[0].strip().lower()[:2]
        if tag in LANGS:
            return tag
    return DEFAULT_LANG


def user_message(code: str | None, lang: str | None = None, **params) -> str | None:
    """Mensaje traducido de `code` (o del error genérico si no existe). Sin `lang`, el de la petición."""
    if code is None:
        return None
    lang = lang or request_lang.get()
    entry = MESSAGES.get(code, MESSAGES["internal_error"])
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**params) if params else text


def translate(text_or_code: str | None, lang: str | None = None) -> str | None:
    """Para textos guardados que pueden ser un código de mensaje o un texto antiguo ya redactado."""
    if text_or_code in MESSAGES:
        return user_message(text_or_code, lang)
    return text_or_code


class AppError(Exception):
    """Error para el usuario. `key` elige otro mensaje del catálogo (con `params`) sin cambiar el `code`."""

    def __init__(
        self, code: str, status: int = 400, *, key: str | None = None, params: dict | None = None,
        detail: str | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status = status
        self.key = key or code
        self.params = params or {}
        self.detail = detail

    def message_for(self, lang: str | None = None) -> str:
        return user_message(self.key, lang, **self.params) or self.code

    @property
    def message(self) -> str:
        return self.message_for(DEFAULT_LANG)


class NotFound(AppError):
    def __init__(self) -> None:
        super().__init__("not_found", 404)
