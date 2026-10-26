import time
from pathlib import Path

from django.conf import settings

from . import temas

# La caminata de Aurora en la barra dura 42,8 s (aurora.css) y sus nubes completan su vuelta cada 3 caminatas. Cada página arranca la animación
# en el punto que marca el reloj del servidor, así al cambiar de página (o de tema) ella sigue por donde iba en lugar de empezar de nuevo.
CICLO_AURORA = 42.8 * 3

try:
    VERSION = (Path(settings.BASE_DIR) / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    VERSION = ""


def roles(request):
    """Hace disponibles en TODAS las plantillas variables de rol (es_ti, es_jefe)."""
    usuario = getattr(request, "user", None)
    autenticado = bool(usuario and usuario.is_authenticated)
    return {
        "es_ti": autenticado and usuario.es_tecnico,
        "es_jefe": autenticado and usuario.es_jefe,
        "sesion_completa": autenticado and _sesion_completa(request, usuario),
    }


def _sesion_completa(request, usuario):
    """Ya está «dentro»: sin clave temporal pendiente y, si se exige, con el segundo factor pasado. Antes de eso no se muestra la barra."""
    if usuario.debe_cambiar_clave:
        return False
    if settings.SEGUNDO_FACTOR:
        from . import segundo_factor
        return segundo_factor.verificado(request)
    return True


def tema(request):
    """Tema activo, lista para el selector y versión del sistema (se muestra en el pie para el soporte)."""
    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        clave = temas.tema_valido(usuario.tema)
    else:
        clave = temas.tema_valido(request.COOKIES.get("tema"))  # la pantalla de login recuerda el último tema
    return {
        "tema_actual": clave,
        "tema_nombre": temas.TEMAS[clave]["nombre"],
        "temas_disponibles": temas.lista_para_selector(),
        # Marca de un solo uso: activa la animación al cambiar de tema (la ponen la vista y se consume aquí)
        "cambio_tema": bool(request.session.pop("cambio_tema", False)) if hasattr(request, "session") else False,
        "version_sistema": VERSION,
        "nombre_sistema": settings.NOMBRE_SISTEMA,
        "subtitulo_sistema": settings.SUBTITULO_SISTEMA,
        "aurora_fase": f"-{time.time() % CICLO_AURORA:.3f}s",
    }
