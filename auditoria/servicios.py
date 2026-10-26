"""
Punto único para escribir (y depurar) la auditoría.

Uso:
    from auditoria.servicios import registrar
    registrar(Modulo.TICKETS, "CREAR", objeto=ticket, referencia=ticket.codigo, detalle="...")

Si no se pasa `usuario`, se toma el de la petición actual (ver middleware).

La auditoría guarda SOLO eventos relevantes (ver ACCIONES_TICKET_AUDITADAS y signals.py).
Lo demás (comentarios, adjuntos...) vive en el historial de cada ticket.
"""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .middleware import contexto_actual
from .models import RegistroAuditoria

Modulo = RegistroAuditoria.Modulo

# Acciones de ticket que pasan a la auditoría global. COMENTAR, ADJUNTAR y descargas NO:
# esas quedan solo en el historial del propio ticket.
ACCIONES_TICKET_AUDITADAS = {
    "CREAR", "ASIGNAR", "CAMBIO_ESTADO", "REABRIR", "RESOLVER", "CERRAR", "CAMBIO_PRIORIDAD", "REPROGRAMAR", "RETOMAR",
}


def registrar(modulo, accion, *, usuario=None, objeto=None, referencia="", detalle="", ip=None,
              usuario_nombre=None, objeto_tipo="", objeto_id=""):
    usuario_ctx, ip_ctx = contexto_actual()
    usuario = usuario or usuario_ctx
    ip = ip or ip_ctx

    if objeto is not None:
        objeto_tipo = objeto_tipo or objeto.__class__.__name__
        objeto_id = objeto_id or str(objeto.pk or "")

    if usuario is not None:
        nombre = usuario.nombre_completo
        rol = usuario.get_rol_display()
    else:
        nombre = usuario_nombre or "Sistema"
        rol = ""

    return RegistroAuditoria.objects.create(
        usuario=usuario if usuario is not None and usuario.pk else None,
        usuario_nombre=nombre[:200],
        usuario_rol=rol,
        ip=ip or None,
        modulo=modulo,
        accion=accion,
        objeto_tipo=objeto_tipo,
        objeto_id=objeto_id,
        referencia=str(referencia)[:120],
        detalle=str(detalle)[:5000],
    )


def diferencias(antes, despues, campos):
    """
    Compara dos instancias del mismo modelo y devuelve un texto con lo que cambió:
        "rol: 'Solicitante' → 'Técnico'; activo: 'True' → 'False'"
    """
    partes = []
    for campo in campos:
        valor_antes = getattr(antes, campo)
        valor_despues = getattr(despues, campo)
        if valor_antes != valor_despues:
            partes.append(f"{campo}: '{valor_antes}' → '{valor_despues}'")
    return "; ".join(partes)


# --------------------------------------------------------------------------- #
# Integridad
# --------------------------------------------------------------------------- #
def verificar_cadena():
    """
    Recorre la cadena de hashes. Devuelve (total_registros, lista_de_problemas).

    Tras una depuración, el registro más antiguo que queda apunta a un anterior que ya
    no existe; por eso la verificación EMPIEZA en ese primer registro (se confía en su
    hash_anterior) y comprueba que todo lo que viene después encadene bien.
    """
    problemas, anterior, total = [], None, 0
    for r in RegistroAuditoria.objects.order_by("id").iterator():
        total += 1
        if anterior is not None and r.hash_anterior != anterior:
            problemas.append(f"Registro #{r.id}: la cadena está rota (el anterior fue alterado o eliminado).")
        if r.calcular_hash() != r.hash:
            problemas.append(f"Registro #{r.id}: su contenido no coincide con su sello (fue modificado).")
        anterior = r.hash
    return total, problemas


# --------------------------------------------------------------------------- #
# Depuración (solo jefe)
# --------------------------------------------------------------------------- #
def fecha_limite_depuracion():
    """Fecha más reciente hasta la cual se permite depurar (respeta la retención mínima)."""
    return timezone.now() - timedelta(days=settings.AUDITORIA_RETENCION_MINIMA_DIAS)


def registros_a_depurar(hasta):
    """
    Bloque INICIAL de la cadena con fecha anterior al día `hasta`: se corta justo antes del
    primer registro que ya no es antiguo. Así nunca se borra nada reciente ni quedan huecos
    en medio de la cadena (el día `hasta` no se toca).
    """
    primer_reciente = RegistroAuditoria.objects.filter(fecha__date__gte=hasta).order_by("id").first()
    qs = RegistroAuditoria.objects.all()
    if primer_reciente is not None:
        qs = qs.filter(id__lt=primer_reciente.id)
    return qs


@transaction.atomic
def depurar(hasta, usuario):
    """
    Borra los registros de auditoría anteriores a `hasta`. Solo para el jefe.
    El propio borrado queda registrado en la auditoría (quién, hasta cuándo y cuántos).
    """
    if not usuario.es_jefe:
        raise ValidationError("Solo el jefe de TI puede depurar la auditoría.")
    if hasta > fecha_limite_depuracion().date():
        raise ValidationError(
            f"Por seguridad solo se pueden depurar registros con más de "
            f"{settings.AUDITORIA_RETENCION_MINIMA_DIAS} días de antigüedad "
            f"(hasta el {fecha_limite_depuracion().date():%d/%m/%Y})."
        )
    candidatos = registros_a_depurar(hasta)
    cantidad = candidatos.count()
    if cantidad == 0:
        raise ValidationError("No hay registros anteriores a esa fecha.")
    borrados, _ = candidatos.delete()  # QuerySet.delete(): permitido aquí, el modelo solo bloquea el delete() individual
    registrar(Modulo.AUDITORIA, "DEPURAR", usuario=usuario, referencia=f"Antes de {hasta:%d/%m/%Y}",
              detalle=f"Se depuraron {borrados} registros de auditoría anteriores al {hasta:%d/%m/%Y}")
    return borrados
