from django.contrib.auth.signals import user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from accounts.models import Usuario
from bitacora.models import Actividad
from tickets.models import Categoria, ConfiguracionSLA, Equipo
from .middleware import obtener_ip
from .servicios import Modulo, diferencias, registrar

@receiver(user_login_failed)
def al_fallar_login(sender, credentials, request=None, **kwargs):
    intento = str(credentials.get('username', ''))[:150]
    registrar(Modulo.ACCESO, 'LOGIN_FALLIDO', usuario_nombre=intento or '(vacío)', referencia=intento, detalle='Intento de inicio de sesión fallido', ip=obtener_ip(request))
CONFIG = {Equipo: (Modulo.INVENTARIO, ['codigo', 'tipo', 'marca', 'modelo', 'serial', 'asignado_a_id', 'ubicacion', 'activo'], lambda o: o.codigo), Categoria: (Modulo.CONFIGURACION, ['nombre', 'activa'], lambda o: f'Categoría {o.nombre}'), ConfiguracionSLA: (Modulo.CONFIGURACION, ['horas'], lambda o: f'SLA {o.prioridad}'), Usuario: (Modulo.USUARIOS, ['rol', 'is_active', 'is_staff', 'is_superuser', 'first_name', 'last_name', 'email', 'departamento', 'cargo'], lambda o: o.username), Actividad: (Modulo.BITACORA, ['tipo', 'titulo', 'descripcion', 'duracion_minutos', 'fecha'], lambda o: f'Actividad #{o.pk}')}
SIN_AUDITAR_ALTAS = {Actividad}

def _conectar(modelo):

    @receiver(pre_save, sender=modelo, weak=False, dispatch_uid=f'aud_pre_{modelo.__name__}')
    def guardar_estado_previo(sender, instance, **kwargs):
        instance._estado_previo = sender.objects.filter(pk=instance.pk).first() if instance.pk else None

    @receiver(post_save, sender=modelo, weak=False, dispatch_uid=f'aud_post_{modelo.__name__}')
    def registrar_guardado(sender, instance, created, raw=False, **kwargs):
        if raw:
            return
        modulo, campos, referencia = CONFIG[sender]
        etiqueta = sender._meta.verbose_name
        if created:
            if sender in SIN_AUDITAR_ALTAS:
                return
            extra = ' (automática por ticket)' if getattr(instance, 'automatica', False) else ''
            registrar(modulo, 'CREAR', objeto=instance, referencia=referencia(instance), detalle=f'Se creó {etiqueta}: {instance}{extra}')
            return
        antes = getattr(instance, '_estado_previo', None)
        if antes is None:
            return
        cambios = diferencias(antes, instance, campos)
        if cambios:
            registrar(modulo, 'ACTUALIZAR', objeto=instance, referencia=referencia(instance), detalle=cambios)

    @receiver(post_delete, sender=modelo, weak=False, dispatch_uid=f'aud_del_{modelo.__name__}')
    def registrar_borrado(sender, instance, **kwargs):
        modulo, _campos, referencia = CONFIG[sender]
        registrar(modulo, 'ELIMINAR', objeto=instance, referencia=referencia(instance), detalle=f'Se eliminó {sender._meta.verbose_name}: {instance}')
for _modelo in CONFIG:
    _conectar(_modelo)
