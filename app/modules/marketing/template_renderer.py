"""Versioned, trusted email layouts. Only escaped campaign text is interpolated."""
import html
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TEMPLATE_KEY = "brasper_peru_pt_v1"
ASSET_PREFIX = "/marketing/assets/brasper-peru-pt-v1"
ASSET_DIR = Path(__file__).parent / "assets"
LEGACY_ASSET_NAMES = (
    "bandera_brasil.png", "bandera_peru.png", "banner_inferior_portugues.jpg",
    "banner_superior_portugues.jpg", "celular_pt.png", "footer_escudo.png",
    "footer_mundo.png", "footer_personas.png", "icon_atencion.png",
    "icon_rapido.png", "icon_seguridad.png", "logo_brasper.png",
)
ASSET_VERSION = "servicios-2026-11-06"
SERVICE_ASSET_NAMES = (
    "bandera_brasil.png", "bandera_peru.png", "pt_header.jpg", "pt_footer.jpg",
    "footer_escudo.png", "footer_mundo.png", "footer_personas.png",
    "icon_atencion.png", "icon_rapido.png", "icon_seguridad.png", "logo_brasper.png",
)
ASSET_NAMES = tuple(ASSET_VERSION + "-" + name for name in SERVICE_ASSET_NAMES)
DEFAULT_SUBJECT = "Brasper: remessas, pagamentos e câmbio entre Peru e Brasil"
DEFAULT_BODY = (
    "Na Brasper, ajudamos você a enviar dinheiro, pagar compromissos e realizar câmbio, "
    "com atendimento personalizado em português e espanhol.\n\n"
    "Seja para sua família, seus projetos ou seu negócio, conheça as opções disponíveis "
    "e solicite uma cotação antes de realizar uma operação."
)


SPANISH_TEMPLATE_KEY = "brasper_brasil_es_v1"
SPANISH_ASSET_NAMES = tuple(name.replace("-pt_", "-es_") for name in ASSET_NAMES)
LEGACY_SPANISH_ASSET_NAMES = tuple(name.replace("portugues", "espanol").replace("celular_pt", "celular_es") for name in LEGACY_ASSET_NAMES)
CYBER_ASSET_NAMES = tuple("cyber-2026-11-" + name for name in dict.fromkeys((*LEGACY_ASSET_NAMES, *LEGACY_SPANISH_ASSET_NAMES)))
ALL_ASSET_NAMES = tuple(dict.fromkeys((*ASSET_NAMES, *SPANISH_ASSET_NAMES, *CYBER_ASSET_NAMES, *LEGACY_ASSET_NAMES, *LEGACY_SPANISH_ASSET_NAMES)))
TEMPLATES = {
    TEMPLATE_KEY: {"key": TEMPLATE_KEY, "name": "Brasil · Portugués · Servicios", "language": "pt-BR",
                   "default_subject": DEFAULT_SUBJECT, "default_body": DEFAULT_BODY},
    SPANISH_TEMPLATE_KEY: {"key": SPANISH_TEMPLATE_KEY, "name": "Perú · Español · Servicios", "language": "es-PE",
        "default_subject": "Brasper: remesas, pagos y cambio de divisas entre Perú y Brasil",
        "default_body": "En Brasper te acompañamos para enviar dinero, pagar obligaciones y cambiar divisas, con atención personalizada en español y portugués.\n\nYa sea para tu familia, tus proyectos o tu negocio, conoce las opciones disponibles y cotiza antes de realizar una operación."},
}


def template_assets(template_key):
    if template_key not in TEMPLATES:
        raise ValueError("Plantilla de correo desconocida")
    return SPANISH_ASSET_NAMES if template_key == SPANISH_TEMPLATE_KEY else ASSET_NAMES


def asset_cid(name):
    return name + "@brasper.marketing"


def render_plain_email(subject, body, unsubscribe, template_key=None):
    if template_key is None:
        return body + "\n\nDejar de recibir correos: " + unsubscribe
    if template_key not in TEMPLATES:
        raise ValueError("Plantilla de correo desconocida")
    source = (Path(__file__).parent / "email_templates" / (template_key + ".txt")).read_text(encoding="utf-8")
    values = {"subject": subject, "message_text": body, "unsubscribe_url": unsubscribe}
    return re.sub(r"{{\s*(subject|message_text|unsubscribe_url)\s*}}", lambda match: values[match[1]], source)


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
