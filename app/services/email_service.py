import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_TLS = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
EMAILS_FROM_EMAIL = os.getenv("EMAILS_FROM_EMAIL", "soporte@fashionstore.com")
EMAILS_FROM_NAME = os.getenv("EMAILS_FROM_NAME", "FashionStore SaaS")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://fashionstore-web-eight.vercel.app")


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to_email: str, subject: str, html_content: str, text_content: str | None = None) -> bool:
    """Envía un correo electrónico mediante SMTP si está configurado.
    Si no está configurado, registra el contenido en logs para entornos de desarrollo/demo."""
    if not is_smtp_configured():
        logger.info(
            "==> [SIMULATED EMAIL] Destinatario: %s | Asunto: %s\n%s",
            to_email,
            subject,
            text_content or html_content,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{EMAILS_FROM_NAME} <{EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(EMAILS_FROM_EMAIL, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                if SMTP_TLS:
                    server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(EMAILS_FROM_EMAIL, [to_email], msg.as_string())

        logger.info("==> Correo enviado exitosamente a: %s", to_email)
        return True
    except Exception as exc:
        logger.error("==> Error enviando correo a %s: %s", to_email, exc)
        return False


def send_password_reset_email(to_email: str, full_name: str, token: str) -> dict:
    """Genera y despacha el correo de restablecimiento de contraseña."""
    reset_url = f"{FRONTEND_URL}/auth/reset-password?token={token}"

    subject = "Recuperación de contraseña · FashionStore SaaS"

    text_body = (
        f"Hola {full_name},\n\n"
        f"Hemos recibido una solicitud para restablecer la contraseña de tu cuenta.\n\n"
        f"Haz clic en el siguiente enlace para crear una nueva contraseña:\n"
        f"{reset_url}\n\n"
        f"Este enlace expirará en 30 minutos.\n"
        f"Si no solicitaste este cambio, puedes ignorar este correo de forma segura.\n\n"
        f"Equipo FashionStore"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Recuperación de Contraseña</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8F9FA; margin: 0; padding: 40px 20px;">
  <div style="max-width: 540px; margin: 0 auto; background: #FFFFFF; border-radius: 12px; border: 1px solid #E5E7EB; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <div style="background-color: #111827; padding: 28px; text-align: center;">
      <h1 style="color: #FFFFFF; margin: 0; font-size: 22px; letter-spacing: 0.5px;">FashionStore SaaS</h1>
      <p style="color: #9CA3AF; margin: 6px 0 0 0; font-size: 13px;">Seguridad y Control de Acceso</p>
    </div>
    <div style="padding: 32px 28px;">
      <h2 style="color: #1F2937; font-size: 18px; margin-top: 0;">Restablecer contraseña</h2>
      <p style="color: #4B5563; font-size: 14px; line-height: 1.6;">
        Hola <strong>{full_name}</strong>,
      </p>
      <p style="color: #4B5563; font-size: 14px; line-height: 1.6;">
        Recibimos una solicitud para restablecer la contraseña de tu cuenta en FashionStore. Si fuiste tú, haz clic en el botón de abajo para definir una nueva contraseña:
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{reset_url}" style="background-color: #E05A47; color: #FFFFFF; padding: 12px 28px; font-size: 14px; font-weight: 600; text-decoration: none; border-radius: 8px; display: inline-block;">
          Restablecer mi contraseña
        </a>
      </div>
      <p style="color: #6B7280; font-size: 12px; line-height: 1.5;">
        O copia y pega el siguiente enlace en tu navegador:<br>
        <a href="{reset_url}" style="color: #E05A47; word-break: break-all;">{reset_url}</a>
      </p>
      <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 24px 0;">
      <p style="color: #9CA3AF; font-size: 11px; margin: 0;">
        Este enlace es válido por <strong>30 minutos</strong>. Si tú no realizaste esta solicitud, puedes ignorar este mensaje; tu contraseña actual continuará siendo segura.
      </p>
    </div>
  </div>
</body>
</html>"""

    sent = send_email(to_email, subject, html_body, text_body)
    return {
        "sent": sent,
        "reset_url": reset_url,
        "token": token,
    }

