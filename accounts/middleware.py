from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
PERMITIDAS = ('/cuentas/cambiar-clave/', '/cuentas/salir/', '/static/', '/salud/', '/manifiesto.webmanifest')

class CambioDeClaveObligatorioMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)
        if usuario is not None and usuario.is_authenticated and getattr(usuario, 'debe_cambiar_clave', False) and (not request.path.startswith(PERMITIDAS)):
            destino = request.get_full_path() if request.method == 'GET' else ''
            enlace = reverse('accounts:cambiar_clave')
            return redirect(f"{enlace}?{urlencode({'next': destino})}" if destino else enlace)
        return self.get_response(request)
PERMITIDAS_SEGUNDO_FACTOR = ('/cuentas/verificar-2fa/', '/cuentas/activar-2fa/', '/cuentas/salir/', '/static/', '/salud/', '/manifiesto.webmanifest')

class SegundoFactorMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from . import segundo_factor
        usuario = getattr(request, 'user', None)
        if settings.SEGUNDO_FACTOR and usuario is not None and usuario.is_authenticated and (not usuario.debe_cambiar_clave) and (not request.path.startswith(PERMITIDAS_SEGUNDO_FACTOR)):
            if segundo_factor.verificado(request):
                pass
            elif usuario.totp_activo and segundo_factor.equipo_recordado(request, usuario):
                segundo_factor.marcar_verificado(request)
            else:
                nombre = 'accounts:verificar_2fa' if usuario.totp_activo else 'accounts:activar_2fa'
                destino = request.get_full_path() if request.method == 'GET' else ''
                enlace = reverse(nombre)
                return redirect(f"{enlace}?{urlencode({'next': destino})}" if destino else enlace)
        return self.get_response(request)
