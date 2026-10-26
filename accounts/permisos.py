"""
Decoradores de permisos para las vistas: @solo_ti (técnicos y jefe) y @solo_jefe. Devuelven 403 si el rol no alcanza
y redirigen al login si no hay sesión.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def _exigir(condicion):
    """Crea un decorador que solo deja pasar a los usuarios con sesión que cumplan `condicion(usuario)`."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not condicion(request.user):
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


solo_ti = _exigir(lambda usuario: usuario.es_tecnico)
solo_jefe = _exigir(lambda usuario: usuario.es_jefe)
