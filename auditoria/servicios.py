from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from .middleware import contexto_actual
from .models import RegistroAuditoria
Modulo = RegistroAuditoria.Modulo
ACCIONES_TICKET_AUDITADAS = {'CREAR', 'ASIGNAR', 'CAMBIO_ESTADO', 'REABRIR', 'RESOLVER', 'CERRAR', 'CAMBIO_PRIORIDAD', 'REPROGRAMAR', 'RETOMAR'}

def registrar(modulo, accion, *, usuario=None, objeto=None, referencia='', detalle='', ip=None, usuario_nombre=None, objeto_tipo='', objeto_id=''):
    usuario_ctx, ip_ctx = contexto_actual()
    usuario = usuario or usuario_ctx
    ip = ip or ip_ctx
    if objeto is not None:
        objeto_tipo = objeto_tipo or objeto.__class__.__name__
        objeto_id = objeto_id or str(objeto.pk or '')
    if usuario is not None:
        nombre = usuario.nombre_completo
        rol = usuario.get_rol_display()
    else:
        nombre = usuario_nombre or 'Sistema'
        rol = ''
    return RegistroAuditoria.objects.create(usuario=usuario if usuario is not None and usuario.pk else None, usuario_nombre=nombre[:200], usuario_rol=rol, ip=ip or None, modulo=modulo, accion=accion, objeto_tipo=objeto_tipo, objeto_id=objeto_id, referencia=str(referencia)[:120], detalle=str(detalle)[:5000])

def diferencias(antes, despues, campos):
    partes = []
    for campo in campos:
        valor_antes = getattr(antes, campo)
        valor_despues = getattr(despues, campo)
        if valor_antes != valor_despues:
            partes.append(f"{campo}: '{valor_antes}' → '{valor_despues}'")
    return '; '.join(partes)

def verificar_cadena():
    problemas, anterior, total = ([], None, 0)
    for r in RegistroAuditoria.objects.order_by('id').iterator():
        total += 1
        if anterior is not None and r.hash_anterior != anterior:
            problemas.append(f'Registro #{r.id}: la cadena está rota (el anterior fue alterado o eliminado).')
        if r.calcular_hash() != r.hash:
            problemas.append(f'Registro #{r.id}: su contenido no coincide con su sello (fue modificado).')
        anterior = r.hash
    return (total, problemas)

def fecha_limite_depuracion():
    return timezone.now() - timedelta(days=settings.AUDITORIA_RETENCION_MINIMA_DIAS)

def registros_a_depurar(hasta):
    primer_reciente = RegistroAuditoria.objects.filter(fecha__date__gte=hasta).order_by('id').first()
    qs = RegistroAuditoria.objects.all()
    if primer_reciente is not None:
        qs = qs.filter(id__lt=primer_reciente.id)
    return qs

@transaction.atomic
def depurar(hasta, usuario):
    if not usuario.es_jefe:
        raise ValidationError('Solo el jefe de TI puede depurar la auditoría.')
    if hasta > fecha_limite_depuracion().date():
        raise ValidationError(f'Por seguridad solo se pueden depurar registros con más de {settings.AUDITORIA_RETENCION_MINIMA_DIAS} días de antigüedad (hasta el {fecha_limite_depuracion().date():%d/%m/%Y}).')
    candidatos = registros_a_depurar(hasta)
    cantidad = candidatos.count()
    if cantidad == 0:
        raise ValidationError('No hay registros anteriores a esa fecha.')
    borrados, _ = candidatos.delete()
    registrar(Modulo.AUDITORIA, 'DEPURAR', usuario=usuario, referencia=f'Antes de {hasta:%d/%m/%Y}', detalle=f'Se depuraron {borrados} registros de auditoría anteriores al {hasta:%d/%m/%Y}')
    return borrados
