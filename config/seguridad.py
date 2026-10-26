CSP_APP = "default-src 'none'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'; manifest-src 'self'"
CSP_ADMIN = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'; manifest-src 'self'"

class CabecerasSeguridadMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        respuesta = self.get_response(request)
        es_admin = request.path.startswith('/admin/')
        respuesta.setdefault('Content-Security-Policy', CSP_ADMIN if es_admin else CSP_APP)
        respuesta.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()')
        if not request.path.startswith('/static/'):
            respuesta.setdefault('Cache-Control', 'private, no-store, max-age=0')
            respuesta.setdefault('Pragma', 'no-cache')
        return respuesta

class RechazaNulosMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import HttpResponseBadRequest
        partes = [request.GET]
        if request.method == 'POST' and (not request.content_type.startswith('multipart/')):
            partes.append(request.POST)
        for parte in partes:
            for clave, valores in parte.lists():
                if '\x00' in clave or any(('\x00' in v for v in valores)):
                    return HttpResponseBadRequest('Solicitud no válida.')
        return self.get_response(request)
