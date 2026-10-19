import html
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException

from app.core.settings import get_settings


def check_config():
    s = get_settings()
    if not all((s.SMTP_HOST, s.SMTP_USERNAME, s.SMTP_PASSWORD, s.SMTP_FROM_EMAIL, s.PUBLIC_URL)):
        raise HTTPException(503, "Configura SMTP y PUBLIC_URL en el backend antes de enviar")
    if not s.SMTP_USE_TLS or not s.PUBLIC_URL.startswith("https://"):
        raise HTTPException(503, "El envío requiere SMTP con TLS y PUBLIC_URL HTTPS")


def unsubscribe_url(email):
    s = get_settings()
    token = jwt.encode({"email": email, "purpose": "marketing-unsubscribe"}, s.SECRET_KEY, algorithm="HS256")
    return s.PUBLIC_URL.rstrip("/") + "/marketing/unsubscribe?" + urlencode({"token": token})


def decode_unsubscribe(token):
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=["HS256"])
        if payload.get("purpose") != "marketing-unsubscribe" or not payload.get("email"):
            raise ValueError()
        return payload["email"]
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(400, "Enlace de baja inválido")


def send_email(email, subject, body, test=False):
    check_config()
    s = get_settings()
    url = unsubscribe_url(email)
    message = EmailMessage()
    message["From"] = s.SMTP_FROM_EMAIL
    message["To"] = email
    message["Subject"] = ("[PRUEBA] " if test else "") + subject
    message.set_content(body + "\n\nDejar de recibir correos: " + url)
    content = html.escape(body).replace("\n", "<br>")
    message.add_alternative(
        '<html><body><div style="font-family:Arial;max-width:640px;margin:auto">'
        '<h2>Brasper Transferencias</h2>' + content
        + '<hr><p><a href="' + html.escape(url, quote=True)
        + '">Dejar de recibir estos correos</a></p></div></body></html>', subtype="html")
    with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
        smtp.send_message(message)
