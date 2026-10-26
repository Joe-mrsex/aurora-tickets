from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from dashboard.views import inicio
from .pwa import manifiesto
from .salud import salud
admin.site.site_header = f'{settings.NOMBRE_SISTEMA} · {settings.SUBTITULO_SISTEMA} - Administración'
admin.site.site_title = settings.NOMBRE_SISTEMA
admin.site.index_title = 'Configuración del sistema'
urlpatterns = [path('salud/', salud, name='salud'), path('manifiesto.webmanifest', manifiesto, name='manifiesto'), path('admin/', admin.site.urls), path('', inicio, name='inicio'), path('cuentas/', include('accounts.urls')), path('tickets/', include('tickets.urls')), path('bitacora/', include('bitacora.urls')), path('auditoria/', include('auditoria.urls')), path('dashboard/', include('dashboard.urls'))]
