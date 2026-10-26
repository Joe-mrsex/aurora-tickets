import time
from pathlib import Path
from django.conf import settings
from . import temas
CICLO_AURORA = 42.8 * 3
try:
    VERSION = (Path(settings.BASE_DIR) / 'VERSION').read_text(encoding='utf-8').strip()
except OSError:
    VERSION = ''

def roles(request):
    usuario = getattr(request, 'user', None)
    autenticado = bool(usuario and usuario.is_authenticated)
    return {'es_ti': autenticado and usuario.es_tecnico, 'es_jefe': autenticado and usuario.es_jefe, 'sesion_completa': autenticado and _sesion_completa(request, usuario)}

def _sesion_completa(request, usuario):
    if usuario.debe_cambiar_clave:
        return False
    if settings.SEGUNDO_FACTOR:
        from . import segundo_factor
        return segundo_factor.verificado(request)
    return True

def tema(request):
    usuario = getattr(request, 'user', None)
    if usuario is not None and usuario.is_authenticated:
        clave = temas.tema_valido(usuario.tema)
    else:
        clave = temas.tema_valido(request.COOKIES.get('tema'))
    return {'tema_actual': clave, 'tema_nombre': temas.TEMAS[clave]['nombre'], 'temas_disponibles': temas.lista_para_selector(), 'cambio_tema': bool(request.session.pop('cambio_tema', False)) if hasattr(request, 'session') else False, 'version_sistema': VERSION, 'nombre_sistema': settings.NOMBRE_SISTEMA, 'subtitulo_sistema': settings.SUBTITULO_SISTEMA, 'aurora_fase': f'-{time.time() % CICLO_AURORA:.3f}s'}
