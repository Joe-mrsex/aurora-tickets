"""
Manifiesto de la aplicación web instalable (Edge/Chrome → «Instalar como aplicación»): le dice al navegador el nombre y los iconos,
en lugar de que invente una letra y el título de la página. Es público (el navegador lo pide sin sesión).
"""
from django.conf import settings
from django.http import JsonResponse
from django.templatetags.static import static


def manifiesto(request):
    iconos = [
        {"src": static("img/aurora/icono-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": static("img/aurora/icono-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": static("img/aurora/icono-512-maskable.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ]
    datos = {
        "name": f"{settings.NOMBRE_SISTEMA} · {settings.SUBTITULO_SISTEMA}",
        "short_name": settings.NOMBRE_SISTEMA,
        "description": "Sistema de tickets y trazabilidad del área de TI.",
        "lang": "es",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#fff6d6",
        "theme_color": "#343a40",
        "icons": iconos,
    }
    return JsonResponse(datos, content_type="application/manifest+json")
