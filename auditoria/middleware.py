"""
Middleware que recuerda "quién" y "desde dónde" hace la petición actual.

Así, aunque un cambio ocurra en lo profundo del código (por ejemplo una señal
de Django al guardar un equipo), la auditoría sabe qué usuario y qué IP lo
provocaron sin tener que pasar la petición por todas las funciones.
"""
import threading

from django.conf import settings

_local = threading.local()


def obtener_ip(request):
    if request is None:
        return None
    # X-Forwarded-For lo puede escribir cualquiera: solo se respeta si hay un proxy inverso declarado
    # (variable TICKETS_PROXY_CONFIABLE) y la petición realmente viene de él. Si no, un atacante podría
    # falsificar su IP en la auditoría con una simple cabecera.
    origen = request.META.get("REMOTE_ADDR")
    proxy = getattr(settings, "TICKETS_PROXY_CONFIABLE", "")
    reenviado = request.META.get("HTTP_X_FORWARDED_FOR")
    if proxy and reenviado and origen in [p.strip() for p in proxy.split(",")]:
        return reenviado.split(",")[-1].strip()[:45]  # el último valor lo añade NUESTRO proxy
    return origen


def contexto_actual():
    """Devuelve (usuario, ip) de la petición en curso; (None, None) fuera de una petición."""
    return getattr(_local, "usuario", None), getattr(_local, "ip", None)


class ContextoAuditoriaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        _local.usuario = usuario if usuario is not None and usuario.is_authenticated else None
        _local.ip = obtener_ip(request)
        try:
            return self.get_response(request)
        finally:
            _local.usuario = None
            _local.ip = None
