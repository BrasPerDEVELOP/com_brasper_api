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


SPANISH_TEMPLATE_KEY = "brasper_brasil_es_v1"
SPANISH_ASSET_NAMES = tuple(name.replace("portugues", "espanol").replace("celular_pt", "celular_es") for name in ASSET_NAMES)
ALL_ASSET_NAMES = tuple(dict.fromkeys((*ASSET_NAMES, *SPANISH_ASSET_NAMES)))
TEMPLATES = {
    TEMPLATE_KEY: {"key": TEMPLATE_KEY, "name": "Brasil · Portugués · Envíos a Perú", "language": "pt-BR",
                   "default_subject": DEFAULT_SUBJECT, "default_body": DEFAULT_BODY},
    SPANISH_TEMPLATE_KEY: {"key": SPANISH_TEMPLATE_KEY, "name": "Perú · Español · Envíos a Brasil", "language": "es-PE",
        "default_subject": "Perú y Brasil más cerca: cotiza tu envío con BrasPer",
        "default_body": "¡Hola!\n\nEn BrasPer te conectamos con quienes más importan. Envía dinero de Perú a Brasil con atención en español y portugués.\n\nCotiza y revisa el tipo de cambio, las comisiones, los plazos y el monto final en reales antes de confirmar tu transferencia."},
}


def template_assets(template_key):
    if template_key not in TEMPLATES:
        raise ValueError("Plantilla de correo desconocida")
    return SPANISH_ASSET_NAMES if template_key == SPANISH_TEMPLATE_KEY else ASSET_NAMES


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
    if template_key not in TEMPLATES:
        raise ValueError("Plantilla de correo desconocida")
    source = (Path(__file__).parent / "email_templates" / (template_key + ".html")).read_text(encoding="utf-8")
    for name in template_assets(template_key):
        url = asset_base.rstrip("/") + ASSET_PREFIX + "/" + name if asset_base else "cid:" + asset_cid(name)
        source = source.replace("assets/" + name, html.escape(url, quote=True))
    values = {"unsubscribe_url": link, "subject": html.escape(subject), "message_html": escaped,
              "year": str(datetime.now(ZoneInfo("America/Lima")).year)}
    return re.sub(r"{{\s*(unsubscribe_url|subject|message_html|year)\s*}}", lambda match: values[match[1]], source)
