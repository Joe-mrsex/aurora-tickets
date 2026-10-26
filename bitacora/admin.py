from django.contrib import admin
from .models import Actividad

@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'tecnico', 'tipo', 'titulo', 'duracion_minutos', 'automatica')
    list_filter = ('tipo', 'tecnico', 'automatica')
    search_fields = ('titulo', 'descripcion')
    date_hierarchy = 'fecha'
