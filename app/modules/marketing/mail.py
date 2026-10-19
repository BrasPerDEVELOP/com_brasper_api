import smtplib
import ssl
import mimetypes
from email.message import EmailMessage
from email.utils import formatdate, formataddr, make_msgid
from email.policy import SMTP
from urllib.parse import urlencode

import jwt
from fastapi import HTTPException

from app.core.settings import get_settings
from app.modules.marketing.template_renderer import ASSET_DIR, TEMPLATE_KEY, template_assets, asset_cid, render_email


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


def build_message(email, subject, body, test=False, template_key=None):
    check_config()
    s = get_settings()
    url = unsubscribe_url(email)
    message = EmailMessage(policy=SMTP)
    message["From"] = formataddr(("BrasPer Transferencias", s.SMTP_FROM_EMAIL))
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Message-ID"] = make_msgid(domain=s.SMTP_FROM_EMAIL.rsplit("@", 1)[-1])
    message["List-Unsubscribe"] = "<" + url + ">"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message["To"] = email
    message["Subject"] = ("[PRUEBA] " if test else "") + subject
    footer = "Cancelar inscrição: " if template_key == TEMPLATE_KEY else "Dejar de recibir correos: "
    cta = "Faça sua cotação" if template_key == TEMPLATE_KEY else "Haz tu cotización"
    plain = body + ("\n\n" + cta + ": https://www.brasper.com" if template_key else "")
    message.set_content(plain + "\n\n" + footer + url)
    message.add_alternative(render_email(subject, body, url, template_key), subtype="html")
    if template_key:
        html_part = message.get_payload()[-1]
        for name in template_assets(template_key):
            maintype, subtype = mimetypes.guess_type(name)[0].split("/")
            html_part.add_related((ASSET_DIR / name).read_bytes(), maintype=maintype, subtype=subtype,
                                  cid="<" + asset_cid(name) + ">", disposition="inline", filename=name)
    return message


def send_email(email, subject, body, test=False, template_key=None):
    message = build_message(email, subject, body, test, template_key)
    s = get_settings()
    with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
        smtp.send_message(message)
