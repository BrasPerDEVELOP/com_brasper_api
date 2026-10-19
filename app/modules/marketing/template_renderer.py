"""Versioned, trusted email layouts. Only escaped campaign text is interpolated."""
import html
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TEMPLATE_KEY = "brasper_peru_pt_v1"
ASSET_PREFIX = "/marketing/assets/brasper-peru-pt-v1"
ASSET_DIR = Path(__file__).parent / "assets"
ASSET_NAMES = (
    "bandera_brasil.png", "bandera_peru.png", "banner_inferior_portugues.jpg",
    "banner_superior_portugues.jpg", "celular_pt.png", "footer_escudo.png",
    "footer_mundo.png", "footer_personas.png", "icon_atencion.png",
    "icon_rapido.png", "icon_seguridad.png", "logo_brasper.png",
)
DEFAULT_SUBJECT = "Brasil e Peru mais perto: faça sua cotação com a BrasPer"
DEFAULT_BODY = (
    "Olá!\n\nNa BrasPer, conectamos você a quem importa. Envie dinheiro do Brasil para o Peru "
    "com atendimento em português e espanhol.\n\nFaça sua cotação e confira a taxa de câmbio, "
    "as tarifas, os prazos e o valor final em soles antes de confirmar sua transferência."
)


def asset_cid(name):
    return name + "@brasper.marketing"


def render_email(subject, body, unsubscribe, template_key=None, asset_base=None):
    escaped = html.escape(body).replace("\n", "<br>\n")
    link = html.escape(unsubscribe, quote=True)
    if template_key is None:
        return (
            '<!doctype html><html lang="es"><meta charset="utf-8"><body>'
            '<div style="font-family:Arial;max-width:640px;margin:auto">'
            '<h2>Brasper Transferencias</h2>' + escaped
            + '<hr><p><a href="' + link + '">Dejar de recibir estos correos</a></p></div></body></html>'
        )
    if template_key != TEMPLATE_KEY:
        raise ValueError("Plantilla de correo desconocida")
    source = (Path(__file__).parent / "email_templates" / (TEMPLATE_KEY + ".html")).read_text(encoding="utf-8")
    for name in ASSET_NAMES:
        url = asset_base.rstrip("/") + ASSET_PREFIX + "/" + name if asset_base else "cid:" + asset_cid(name)
        source = source.replace("assets/" + name, html.escape(url, quote=True))
    values = {"unsubscribe_url": link, "subject": html.escape(subject), "message_html": escaped,
              "year": str(datetime.now(ZoneInfo("America/Lima")).year)}
    return re.sub(r"{{\s*(unsubscribe_url|subject|message_html|year)\s*}}", lambda match: values[match[1]], source)
