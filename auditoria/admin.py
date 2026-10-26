from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Solo lectura: la auditoría no se edita ni se borra desde ningún lado."""

    list_display = ("id", "fecha", "usuario_nombre", "modulo", "accion", "referencia", "ip")
    list_filter = ("modulo", "accion")
    search_fields = ("usuario_nombre", "referencia", "detalle")
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
