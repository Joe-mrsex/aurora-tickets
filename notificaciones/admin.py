from django.contrib import admin
from .models import Notificacion

@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'creada', 'evento', 'email', 'ticket', 'estado', 'intentos', 'enviada')
    list_filter = ('estado', 'evento')
    search_fields = ('email', 'asunto', 'ultimo_error')
    date_hierarchy = 'creada'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
