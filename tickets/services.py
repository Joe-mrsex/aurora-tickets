from datetime import datetime, time, timedelta
from functools import wraps
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from auditoria.servicios import ACCIONES_TICKET_AUDITADAS, Modulo, registrar
from bitacora.models import Actividad
from notificaciones import servicios as avisos
from .models import ESTADOS_ABIERTOS, Adjunto, Comentario, Estado, HistorialTicket, Ticket
TRANSICIONES_TI = {Estado.NUEVO: [Estado.ASIGNADO, Estado.EN_PROCESO, Estado.CANCELADO], Estado.ASIGNADO: [Estado.EN_PROCESO, Estado.PENDIENTE, Estado.RESUELTO, Estado.CANCELADO], Estado.EN_PROCESO: [Estado.PENDIENTE, Estado.RESUELTO, Estado.CANCELADO], Estado.PENDIENTE: [Estado.EN_PROCESO, Estado.RESUELTO, Estado.CANCELADO], Estado.RESUELTO: [Estado.CERRADO, Estado.EN_PROCESO], Estado.CERRADO: [Estado.EN_PROCESO], Estado.CANCELADO: []}

def _evento(ticket, usuario, accion, detalle, accion_auditoria=None, visible=True):
    HistorialTicket.objects.create(ticket=ticket, usuario=usuario, accion=accion, detalle=detalle, visible_solicitante=visible)
    accion_aud = accion_auditoria or accion
    if accion_aud in ACCIONES_TICKET_AUDITADAS:
        registrar(Modulo.TICKETS, accion_aud, usuario=usuario, objeto=ticket, referencia=ticket.codigo, detalle=detalle)

def _exigir_ti(usuario):
    if not usuario.es_tecnico:
        raise PermissionDenied('Solo el personal de TI puede realizar esta acción.')

def _exigir_transicion(ticket, nuevo_estado, usuario):
    if nuevo_estado not in TRANSICIONES_TI.get(ticket.estado, []):
        raise ValidationError(f'No se puede pasar de «{ticket.get_estado_display()}» a «{Estado(nuevo_estado).label}».')
    if ticket.estado == Estado.CERRADO and (not usuario.es_jefe):
        raise PermissionDenied('Solo el jefe de TI puede reabrir un ticket cerrado.')

def _texto_duracion(delta):
    minutos = int(delta.total_seconds() // 60)
    dias, resto = divmod(minutos, 1440)
    horas, mins = divmod(resto, 60)
    partes = ([f'{dias} d'] if dias else []) + ([f'{horas} h'] if horas else []) + ([f'{mins} min'] if mins and (not dias) else [])
    return ' '.join(partes) or 'menos de 1 min'

def _reanudar_por_accion(ticket, por):
    duracion = ticket.cerrar_pausa()
    if duracion is not None:
        _evento(ticket, por, 'RETOMAR', f'Se retomó el ticket: el SLA se reanudó (la pausa duró {_texto_duracion(duracion)}). Nuevo vencimiento: {timezone.localtime(ticket.fecha_limite):%Y-%m-%d %H:%M}')

def _marcar_primera_atencion(ticket):
    if not ticket.fecha_primera_atencion:
        ticket.fecha_primera_atencion = timezone.now()

def _con_ticket_fresco(funcion):

    @wraps(funcion)
    def envoltura(ticket, *args, **kwargs):
        if ticket.pk:
            type(ticket).objects.select_for_update().filter(pk=ticket.pk).first()
            ticket.refresh_from_db()
        return funcion(ticket, *args, **kwargs)
    return envoltura

@transaction.atomic
def crear_ticket(*, solicitante, titulo, descripcion, categoria, prioridad, equipo=None, archivos=()):
    ticket = Ticket.objects.create(solicitante=solicitante, titulo=titulo, descripcion=descripcion, categoria=categoria, prioridad=prioridad, equipo=equipo)
    _evento(ticket, solicitante, 'CREAR', f'Ticket creado: «{titulo}» | Categoría: {categoria} | Prioridad: {ticket.get_prioridad_display()} | Vence: {timezone.localtime(ticket.fecha_limite):%Y-%m-%d %H:%M}')
    for archivo in archivos:
        adjuntar(ticket, solicitante, archivo)
    return ticket

@transaction.atomic
@_con_ticket_fresco
def asignar(ticket, tecnico, por):
    _exigir_ti(por)
    if not tecnico.es_tecnico:
        raise ValidationError('Solo se puede asignar a personal de TI.')
    if not ticket.esta_abierto:
        raise ValidationError('No se puede asignar un ticket que ya está resuelto, cerrado o cancelado.')
    anterior = ticket.tecnico
    ticket.tecnico = tecnico
    ticket.fecha_asignacion = timezone.now()
    if ticket.estado == Estado.NUEVO:
        ticket.estado = Estado.ASIGNADO
    ticket.save()
    detalle = f'Asignado a {tecnico}' + (f' (antes: {anterior})' if anterior and anterior != tecnico else '')
    _evento(ticket, por, 'ASIGNAR', detalle)
    avisos.asignado(ticket, por)

@transaction.atomic
@_con_ticket_fresco
def tomar(ticket, por):
    _exigir_ti(por)
    if ticket.estado != Estado.NUEVO and (not (ticket.estado == Estado.ASIGNADO and ticket.tecnico_id in (None, por.id))):
        raise ValidationError('Este ticket ya está siendo atendido.')
    ticket.tecnico = por
    ticket.fecha_asignacion = ticket.fecha_asignacion or timezone.now()
    ticket.estado = Estado.EN_PROCESO
    _marcar_primera_atencion(ticket)
    _reanudar_por_accion(ticket, por)
    ticket.save()
    _evento(ticket, por, 'TOMAR', f'{por} tomó el ticket y comenzó a atenderlo', 'CAMBIO_ESTADO')
    avisos.asignado(ticket, por)

@transaction.atomic
@_con_ticket_fresco
def cambiar_estado(ticket, nuevo_estado, por, nota=''):
    _exigir_ti(por)
    nuevo_estado = Estado(nuevo_estado)
    if nuevo_estado == Estado.RESUELTO:
        raise ValidationError('Para resolver un ticket usa el formulario de solución.')
    if nuevo_estado == Estado.CERRADO:
        return cerrar(ticket, por)
    _exigir_transicion(ticket, nuevo_estado, por)
    anterior = ticket.get_estado_display()
    reapertura = ticket.estado in (Estado.RESUELTO, Estado.CERRADO)
    if nuevo_estado in (Estado.EN_PROCESO, Estado.CANCELADO):
        _reanudar_por_accion(ticket, por)
    ticket.estado = nuevo_estado
    if nuevo_estado == Estado.EN_PROCESO:
        _marcar_primera_atencion(ticket)
        if not ticket.tecnico_id:
            ticket.tecnico = por
    if reapertura:
        ticket.fecha_resolucion = None
        ticket.fecha_cierre = None
    ticket.save()
    detalle = f'Estado: {anterior} → {ticket.get_estado_display()}' + (f' | Nota: {nota}' if nota else '')
    _evento(ticket, por, 'REABRIR' if reapertura else 'CAMBIO_ESTADO', detalle)
    avisos.estado_cambiado(ticket, por, anterior, ticket.get_estado_display(), nota)

@transaction.atomic
@_con_ticket_fresco
def resolver(ticket, solucion, por, minutos=0):
    _exigir_ti(por)
    _exigir_transicion(ticket, Estado.RESUELTO, por)
    if not solucion.strip():
        raise ValidationError('Debes describir la solución aplicada.')
    _reanudar_por_accion(ticket, por)
    ticket.estado = Estado.RESUELTO
    ticket.solucion = solucion.strip()
    ticket.fecha_resolucion = timezone.now()
    _marcar_primera_atencion(ticket)
    if not ticket.tecnico_id:
        ticket.tecnico = por
    ticket.save()
    sla = 'dentro del SLA' if ticket.cumplio_sla else 'FUERA del SLA'
    _evento(ticket, por, 'RESOLVER', f'Ticket resuelto ({sla}). Solución: {ticket.solucion}')
    Actividad.objects.create(tecnico=por, fecha=timezone.localdate(), tipo=Actividad.Tipo.TICKET, titulo=f'{ticket.codigo}: {ticket.titulo}', descripcion=ticket.solucion, duracion_minutos=minutos or 0, equipo=ticket.equipo, ticket=ticket, automatica=True)
    avisos.resuelto(ticket, por)

@transaction.atomic
@_con_ticket_fresco
def cerrar(ticket, por, automatico=False):
    es_dueno = ticket.solicitante_id == por.id if por else False
    if not automatico and (not (es_dueno or por.es_tecnico)):
        raise PermissionDenied
    if ticket.estado != Estado.RESUELTO:
        raise ValidationError('Solo se pueden cerrar tickets en estado «Resuelto».')
    ticket.estado = Estado.CERRADO
    ticket.fecha_cierre = timezone.now()
    ticket.save()
    quien = 'Cierre automático por falta de respuesta' if automatico else f'Cerrado por {por}'
    _evento(ticket, por, 'CERRAR', quien)
    avisos.cerrado(ticket, por, automatico)

@transaction.atomic
@_con_ticket_fresco
def reabrir_por_solicitante(ticket, por, motivo):
    if ticket.solicitante_id != por.id:
        raise PermissionDenied
    if ticket.estado != Estado.RESUELTO:
        raise ValidationError('Solo se puede reabrir un ticket que está en estado «Resuelto».')
    if not motivo.strip():
        raise ValidationError('Indica por qué no estás conforme con la solución.')
    ticket.estado = Estado.EN_PROCESO
    ticket.fecha_resolucion = None
    ticket.save()
    _evento(ticket, por, 'REABRIR', f'Reabierto por el solicitante. Motivo: {motivo.strip()}')
    avisos.reabierto_por_solicitante(ticket, por, motivo.strip())

@transaction.atomic
@_con_ticket_fresco
def cambiar_prioridad(ticket, prioridad, por):
    _exigir_ti(por)
    if not ticket.esta_abierto:
        raise ValidationError('Solo se puede cambiar la prioridad de un ticket abierto.')
    if prioridad == ticket.prioridad:
        return
    anterior = ticket.get_prioridad_display()
    ticket.prioridad = prioridad
    ticket.fecha_limite = ticket.calcular_fecha_limite()
    ticket.save()
    _evento(ticket, por, 'CAMBIO_PRIORIDAD', f'Prioridad: {anterior} → {ticket.get_prioridad_display()} (nueva fecha límite: {timezone.localtime(ticket.fecha_limite):%Y-%m-%d %H:%M})')

@transaction.atomic
@_con_ticket_fresco
def reprogramar(ticket, fecha, motivo, por):
    _exigir_ti(por)
    if not ticket.esta_abierto:
        raise ValidationError('Solo se pueden reprogramar tickets abiertos (no resueltos, cerrados ni cancelados).')
    hoy = timezone.localdate()
    if fecha is None or fecha <= hoy:
        raise ValidationError('La nueva fecha debe ser posterior a hoy.')
    if fecha > hoy + timedelta(days=settings.DIAS_MAX_REPROGRAMACION):
        raise ValidationError(f'No se puede reprogramar a más de {settings.DIAS_MAX_REPROGRAMACION} días.')
    motivo = (motivo or '').strip()
    if len(motivo) < 5:
        raise ValidationError('Indica el motivo de la reprogramación.')
    ahora = timezone.now()
    anterior = ticket.reprogramado_para
    if ticket.pausado_desde is None:
        ticket.pausado_desde = ahora
    ticket.reprogramado_para = fecha
    ticket.reprogramaciones += 1
    if ticket.tecnico_id is None:
        ticket.tecnico = por
        ticket.fecha_asignacion = ticket.fecha_asignacion or ahora
        if ticket.estado == Estado.NUEVO:
            ticket.estado = Estado.ASIGNADO
    ticket.save()
    detalle = f'Reprogramado para el {fecha:%d/%m/%Y}' + (f' (antes: {anterior:%d/%m/%Y})' if anterior else '') + f'. El SLA queda en pausa. Motivo: {motivo}'
    _evento(ticket, por, 'REPROGRAMAR', detalle)
    avisos.reprogramado(ticket, por, fecha, motivo)

@transaction.atomic
@_con_ticket_fresco
def retomar(ticket, por):
    _exigir_ti(por)
    if not ticket.en_pausa:
        raise ValidationError('Este ticket no está reprogramado.')
    _reanudar_por_accion(ticket, por)
    ticket.save()

def reanudar_programados(ahora=None):
    ahora = ahora or timezone.now()
    hoy = timezone.localdate(ahora)
    cantidad = 0
    pendientes = Ticket.objects.filter(pausado_desde__isnull=False, reprogramado_para__lte=hoy, estado__in=ESTADOS_ABIERTOS).values_list('pk', flat=True)
    for pk in list(pendientes):
        with transaction.atomic():
            t = Ticket.objects.select_for_update().get(pk=pk)
            if t.pausado_desde is None or t.reprogramado_para is None or t.reprogramado_para > hoy:
                continue
            fecha = t.reprogramado_para
            inicio_dia = timezone.make_aware(datetime.combine(fecha, time.min))
            duracion = t.cerrar_pausa(hasta=max(inicio_dia, t.pausado_desde))
            t.save()
            _evento(t, None, 'RETOMAR', f'Llegó el día programado ({fecha:%d/%m/%Y}): el SLA se reanudó (la pausa duró {_texto_duracion(duracion)}). Nuevo vencimiento: {timezone.localtime(t.fecha_limite):%Y-%m-%d %H:%M}')
            avisos.recordatorio_del_dia(t, fecha)
            cantidad += 1
    return cantidad

def avisar_sla(ahora=None):
    ahora = ahora or timezone.now()
    base = Ticket.objects.filter(estado__in=ESTADOS_ABIERTOS, pausado_desde__isnull=True, tecnico__isnull=False, tecnico__is_active=True).select_related('tecnico', 'solicitante')
    creados = 0
    for t in base.filter(fecha_limite__gt=ahora, fecha_limite__lte=ahora + timedelta(hours=settings.SLA_AVISO_HORAS)):
        creados += 1 if avisos.sla_por_vencer(t) else 0
    for t in base.filter(fecha_limite__lte=ahora, fecha_limite__gt=ahora - timedelta(hours=24)):
        creados += 1 if avisos.sla_vencido(t) else 0
    return creados

@transaction.atomic
def comentar(ticket, autor, texto, interno=False):
    if interno and (not autor.es_tecnico):
        interno = False
    if not autor.es_tecnico and ticket.solicitante_id != autor.id:
        raise PermissionDenied
    if ticket.estado == Estado.CANCELADO or (ticket.estado == Estado.CERRADO and (not autor.es_tecnico)):
        raise ValidationError('Este ticket ya no admite comentarios.')
    if not texto or not texto.strip():
        raise ValidationError('El comentario no puede estar vacío.')
    comentario = Comentario.objects.create(ticket=ticket, autor=autor, texto=texto, interno=interno)
    if autor.es_tecnico and (not ticket.fecha_primera_atencion) and (not interno):
        ticket.fecha_primera_atencion = timezone.now()
        ticket.save(update_fields=['fecha_primera_atencion', 'actualizado'])
    tipo = 'nota interna' if interno else 'comentario'
    _evento(ticket, autor, 'COMENTAR', f'Nuevo {tipo}: {texto[:200]}', visible=not interno)
    avisos.comentario(ticket, comentario)
    return comentario

@transaction.atomic
def adjuntar(ticket, usuario, archivo, comentario=None):
    adjunto = Adjunto.objects.create(ticket=ticket, archivo=archivo, nombre_original=archivo.name, subido_por=usuario, comentario=comentario)
    interno = bool(comentario and comentario.interno)
    _evento(ticket, usuario, 'ADJUNTAR', f'Archivo adjuntado: {archivo.name}', visible=not interno)
    return adjunto

def cerrar_resueltos_vencidos(dias):
    limite = timezone.now() - timedelta(days=dias)
    cerrados = 0
    for ticket in Ticket.objects.filter(estado=Estado.RESUELTO, fecha_resolucion__lt=limite):
        cerrar(ticket, None, automatico=True)
        cerrados += 1
    return cerrados

def puede_ver(usuario, ticket):
    return usuario.es_tecnico or ticket.solicitante_id == usuario.id

def puede_ver_adjunto(usuario, adjunto):
    if not puede_ver(usuario, adjunto.ticket):
        return False
    return usuario.es_tecnico or not adjunto.es_interno
