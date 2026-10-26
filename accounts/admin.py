from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from auditoria.servicios import Modulo, registrar
from . import segundo_factor
from .claves import generar_clave_temporal
from .models import Usuario

@admin.action(description='Restablecer contraseña (genera una temporal para entregar)')
def restablecer_clave(modeladmin, request, queryset):
    for usuario in queryset:
        temporal = generar_clave_temporal()
        usuario.set_password(temporal)
        usuario.debe_cambiar_clave = True
        usuario.totp_epoca += 1
        usuario.save(update_fields=['password', 'debe_cambiar_clave', 'totp_epoca'])
        registrar(Modulo.USUARIOS, 'RESTABLECER_CLAVE', usuario=request.user, referencia=usuario.username, detalle=f'{request.user.username} restableció la contraseña de {usuario.username}')
        messages.warning(request, f'{usuario.username}: contraseña temporal  {temporal}   (entrégasela a la persona; la cambiará al entrar. No se vuelve a mostrar)')

@admin.action(description='Reiniciar el segundo factor (perdió el celular)')
def reiniciar_segundo_factor(modeladmin, request, queryset):
    for usuario in queryset:
        segundo_factor.reiniciar(usuario)
        registrar(Modulo.USUARIOS, 'REINICIAR_SEGUNDO_FACTOR', usuario=request.user, referencia=usuario.username, detalle=f'{request.user.username} reinició el segundo factor de {usuario.username}')
    messages.success(request, 'Segundo factor reiniciado: tendrán que volver a activarlo en su próximo ingreso.')

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'nombre_completo', 'rol', 'departamento', 'is_active', 'debe_cambiar_clave', 'totp_activo', 'last_login')
    list_filter = ('rol', 'is_active', 'debe_cambiar_clave', 'departamento')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'departamento')
    actions = [restablecer_clave, reiniciar_segundo_factor]
    readonly_fields = ('totp_activo',)
    fieldsets = UserAdmin.fieldsets + (('Datos del sistema de tickets', {'fields': ('rol', 'departamento', 'cargo', 'telefono', 'tema', 'recibe_correos', 'debe_cambiar_clave', 'totp_activo')}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Datos del sistema de tickets', {'fields': ('rol', 'departamento', 'cargo', 'first_name', 'last_name', 'email')}),)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.debe_cambiar_clave = True
        super().save_model(request, obj, form, change)
