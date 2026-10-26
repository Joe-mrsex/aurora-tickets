import threading
from django.conf import settings
_local = threading.local()

def obtener_ip(request):
    if request is None:
        return None
    origen = request.META.get('REMOTE_ADDR')
    proxy = getattr(settings, 'TICKETS_PROXY_CONFIABLE', '')
    reenviado = request.META.get('HTTP_X_FORWARDED_FOR')
    if proxy and reenviado and (origen in [p.strip() for p in proxy.split(',')]):
        return reenviado.split(',')[-1].strip()[:45]
    return origen

def contexto_actual():
    return (getattr(_local, 'usuario', None), getattr(_local, 'ip', None))

class ContextoAuditoriaMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)
        _local.usuario = usuario if usuario is not None and usuario.is_authenticated else None
        _local.ip = obtener_ip(request)
        try:
            return self.get_response(request)
        finally:
            _local.usuario = None
            _local.ip = None
