"""
La imagen de Aurora que va en los correos. Se incrusta DENTRO del mensaje (adjunto en línea con Content-ID), no se enlaza a internet:
así se ve sin que la persona tenga que pulsar «mostrar imágenes» (Outlook y otros las bloquean por defecto).
"""
from functools import lru_cache

from django.conf import settings

CONTENT_ID = "aurora"


@lru_cache(maxsize=1)
def imagen_correo():
    """Bytes del PNG, o None si el archivo no está (el correo sale igual, sin imagen)."""
    ruta = settings.BASE_DIR / "static" / "img" / "aurora" / "correo_aurora.png"
    try:
        return ruta.read_bytes()
    except OSError:
        return None


def lleva_imagen(html):
    return bool(html) and f"cid:{CONTENT_ID}" in html
