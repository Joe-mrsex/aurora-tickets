from functools import lru_cache
from django.conf import settings
CONTENT_ID = 'aurora'

@lru_cache(maxsize=1)
def imagen_correo():
    ruta = settings.BASE_DIR / 'static' / 'img' / 'aurora' / 'correo_aurora.png'
    try:
        return ruta.read_bytes()
    except OSError:
        return None

def lleva_imagen(html):
    return bool(html) and f'cid:{CONTENT_ID}' in html
