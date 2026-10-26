from django.contrib import admin
from .models import Categoria, Comentario, ConfiguracionSLA, Equipo, HistorialTicket, Ticket

@admin.register(ConfiguracionSLA)
class ConfiguracionSLAAdmin(admin.ModelAdmin):
    list_display = ('prioridad', 'horas')

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activa')
    list_filter = ('activa',)

@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tipo', 'marca', 'modelo', 'serial', 'asignado_a', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('codigo', 'serial', 'marca', 'modelo', 'asignado_a__username', 'asignado_a__first_name')

class ComentarioInline(admin.TabularInline):
    model = Comentario
    extra = 0
    can_delete = False
    readonly_fields = ('autor', 'texto', 'interno', 'creado')

    def has_add_permission(self, request, obj=None):
        return False

class HistorialInline(admin.TabularInline):
    model = HistorialTicket
    extra = 0
    can_delete = False
    readonly_fields = ('usuario', 'fecha', 'accion', 'detalle', 'visible_solicitante')

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'titulo', 'solicitante', 'tecnico', 'estado', 'prioridad', 'creado')
    list_filter = ('estado', 'prioridad', 'categoria')
    search_fields = ('titulo', 'descripcion', 'solicitante__username')
    inlines = [ComentarioInline, HistorialInline]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
