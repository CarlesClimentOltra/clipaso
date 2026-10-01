"""Genera las plantillas de los emails de Supabase Auth con el estilo de Clipaso.

    .venv\\Scripts\\python deploy\\supabase_emails.py

Escribe un .html por plantilla en `deploy/supabase_emails/` para pegarlo en Supabase →
Authentication → Emails → Templates. Los textos salen en el idioma de la cuenta (`locale` en los
metadatos del usuario, que la web guarda al registrarse); sin idioma, en español.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("supabase_emails")

LIME = "#b6e34a"
LIME_INK = "#1f2d0c"
INK = "#4d7c0f"

# plantilla de Supabase → (asunto, título, texto, botón, aviso) en es / en
TEMPLATES = {
    "confirm_signup": {
        "es": ("Confirma tu cuenta de Clipaso", "Confirma tu email",
               "Ya casi está. Confirma tu email para activar tu cuenta y empezar a crear clips con tus "
               "20 minutos gratis de este mes.",
               "Confirmar mi email", "Si no has creado una cuenta en Clipaso, ignora este email."),
        "en": ("Confirm your Clipaso account", "Confirm your email",
               "Almost there. Confirm your email to activate your account and start creating clips with "
               "your 20 free minutes this month.",
               "Confirm my email", "If you didn't create a Clipaso account, you can ignore this email."),
    },
    "reset_password": {
        "es": ("Cambia tu contraseña de Clipaso", "Cambia tu contraseña",
               "Hemos recibido una solicitud para cambiar la contraseña de tu cuenta. Pulsa el botón para "
               "elegir una nueva.",
               "Elegir contraseña nueva", "Si no lo has pedido tú, ignora este email: tu contraseña no cambiará."),
        "en": ("Reset your Clipaso password", "Reset your password",
               "We received a request to change your account password. Press the button to choose a new one.",
               "Choose a new password", "If you didn't ask for this, ignore this email: your password won't change."),
    },
    "magic_link": {
        "es": ("Tu enlace para entrar en Clipaso", "Entra en Clipaso",
               "Pulsa el botón para entrar en tu cuenta. El enlace caduca en una hora y solo sirve una vez.",
               "Entrar en Clipaso", "Si no has pedido entrar, ignora este email."),
        "en": ("Your Clipaso sign-in link", "Sign in to Clipaso",
               "Press the button to sign in to your account. The link expires in one hour and works only once.",
               "Sign in to Clipaso", "If you didn't ask to sign in, you can ignore this email."),
    },
    "change_email": {
        "es": ("Confirma tu nuevo email en Clipaso", "Confirma tu nuevo email",
               "Has pedido cambiar el email de tu cuenta de {{ .Email }} a {{ .NewEmail }}. Confírmalo para "
               "terminar el cambio.",
               "Confirmar el cambio", "Si no lo has pedido tú, ignora este email y tu email no cambiará."),
        "en": ("Confirm your new Clipaso email", "Confirm your new email",
               "You asked to change your account email from {{ .Email }} to {{ .NewEmail }}. Confirm it to "
               "finish the change.",
               "Confirm the change", "If you didn't ask for this, ignore this email and your email won't change."),
    },
}

FOOTER = {"es": "Clipaso · Datos alojados en la Unión Europea", "en": "Clipaso · Data hosted in the European Union"}
FALLBACK = {"es": "¿El botón no funciona? Copia este enlace en el navegador:",
            "en": "Button not working? Copy this link into your browser:"}


def body(lang: str, texts: tuple[str, str, str, str, str]) -> str:
    _, title, text, button, notice = texts
    return f"""
<tr><td style="padding:40px 40px 8px">
  <h1 style="margin:0 0 12px;font-size:24px;line-height:1.25;font-weight:700;color:#111;letter-spacing:-0.02em">{title}</h1>
  <p style="margin:0;font-size:15px;line-height:1.6;color:#404040">{text}</p>
</td></tr>
<tr><td style="padding:28px 40px 8px">
  <a href="{{{{ .ConfirmationURL }}}}" style="display:inline-block;background:{LIME};color:{LIME_INK};font-size:15px;font-weight:700;text-decoration:none;padding:14px 28px;border-radius:999px">{button}</a>
</td></tr>
<tr><td style="padding:24px 40px 0">
  <p style="margin:0 0 6px;font-size:12px;line-height:1.5;color:#737373">{FALLBACK[lang]}</p>
  <p style="margin:0;font-size:12px;line-height:1.5;word-break:break-all"><a href="{{{{ .ConfirmationURL }}}}" style="color:{INK}">{{{{ .ConfirmationURL }}}}</a></p>
</td></tr>
<tr><td style="padding:28px 40px 40px">
  <p style="margin:0;padding-top:20px;border-top:1px solid #ececec;font-size:13px;line-height:1.5;color:#737373">{notice}</p>
</td></tr>"""


def page(name: str) -> str:
    t = TEMPLATES[name]
    # Inglés solo si la cuenta lo tiene guardado (el `if` exterior evita comparar un valor vacío).
    content = ('{{ if and .Data .Data.locale }}{{ if eq .Data.locale "en" }}' + body("en", t["en"])
               + "{{ else }}" + body("es", t["es"]) + "{{ end }}{{ else }}" + body("es", t["es"]) + "{{ end }}")
    footer = ('{{ if and .Data .Data.locale }}{{ if eq .Data.locale "en" }}' + FOOTER["en"]
              + "{{ else }}" + FOOTER["es"] + "{{ end }}{{ else }}" + FOOTER["es"] + "{{ end }}")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"></head>
<body style="margin:0;padding:0;background:#f4f6ee">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6ee;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<tr><td align="center" style="padding:40px 16px">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px">
    <tr><td style="padding:0 8px 20px">
      <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="width:32px;height:32px;background:#121a05;border-radius:9px;text-align:center;vertical-align:middle;color:{LIME};font-size:15px;font-weight:800;line-height:32px">C</td>
        <td style="padding-left:10px;font-size:19px;font-weight:700;color:#111;letter-spacing:-0.02em">Clip<span style="color:{INK}">aso</span></td>
      </tr></table>
    </td></tr>
    <tr><td style="background:#ffffff;border-radius:20px;border:1px solid #e6e9dc;overflow:hidden">
      <div style="height:6px;background:{LIME};font-size:0;line-height:0">&nbsp;</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{content}
      </table>
    </td></tr>
    <tr><td align="center" style="padding:20px 8px 0;font-size:12px;color:#8a8f7c">{footer}</td></tr>
  </table>
</td></tr>
</table>
</body></html>
"""


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, t in TEMPLATES.items():
        (OUT / f"{name}.html").write_text(page(name), encoding="utf-8")
        print(f"{name}.html  ·  asunto: {t['es'][0]}")


if __name__ == "__main__":
    main()
