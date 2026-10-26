"""
Creación de avisos por correo (la «bandeja de salida») y los mensajes de cada evento.

Reglas que se cumplen siempre:
  * Si el correo está desactivado (TICKETS_CORREO=desactivado) no se hace nada.
  * Nadie recibe un aviso de lo que hizo él mismo.
  * Solo reciben avisos las cuentas activas que tengan correo y no hayan desactivado `recibe_correos`.
  * Al solicitante NUNCA le llegan notas internas ni sus archivos.
  * Cada aviso es corto y lleva el enlace al ticket; el contenido de usuarios se escapa en el HTML.
"""
import logging
import re
import threading
from contextlib import contextmanager
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .models import Notificacion

logger = logging.getLogger("notificaciones")
Evento = Notificacion.Evento


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
_estado = threading.local()


@contextmanager
def silencio():
    """
    Mientras se está dentro de este bloque no se crea ningún aviso. Sirve para cargas masivas (datos de demostración,
    importaciones), que si no generarían cientos de correos por acciones que en realidad son parte de la carga.
    """
    anterior = getattr(_estado, "silencio", False)
    _estado.silencio = True
    try:
        yield
    finally:
        _estado.silencio = anterior


def activo():
    return settings.CORREO_MODO != "desactivado" and not getattr(_estado, "silencio", False)


def _una_linea(texto, largo=150):
    """Quita saltos de línea y caracteres de control (evita inyección de cabeceras en el asunto)."""
    texto = re.sub(r"[\x00-\x1f\x7f  ]+", " ", str(texto or ""))
    return re.sub(r"\s{2,}", " ", texto).strip()[:largo]


def _recortar(texto, largo=600):
    texto = str(texto or "").strip()
    return texto if len(texto) <= largo else texto[:largo].rstrip() + "…"


def _puede_recibir(usuario):
    return bool(usuario is not None and usuario.is_active and getattr(usuario, "recibe_correos", True)
                and (usuario.email or "").strip())


def _enlace(ticket):
    if ticket is None:
        return settings.URL_BASE + "/"
    return settings.URL_BASE + reverse("tickets:detalle", args=[ticket.pk])


def _local(fecha):
    return timezone.localtime(fecha).strftime("%d/%m/%Y %H:%M") if fecha else "—"


# --------------------------------------------------------------------------- #
# Alta de un aviso
# --------------------------------------------------------------------------- #
def avisar(destinatario, evento, ticket=None, *, asunto, titulo, lineas=(), cita="", boton="Abrir el ticket",
           clave=None, enviar_despues_de=None, excluir=None):
    """Anota un aviso para `destinatario`. Devuelve la Notificacion creada o None si no corresponde enviarla."""
    if not activo():
        return None
    if excluir is not None and destinatario is not None and destinatario.pk == excluir.pk:
        return None  # nadie recibe un aviso de lo que hizo él mismo
    if not _puede_recibir(destinatario):
        return None
    if clave and Notificacion.objects.filter(clave=clave).exists():
        return None

    codigo = ticket.codigo if ticket is not None else ""
    contexto = {
        "nombre": destinatario.first_name or destinatario.username, "titulo": _una_linea(titulo, 200),
        "lineas": [_una_linea(x, 300) for x in lineas if x], "cita": _recortar(cita), "boton": boton,
        "enlace": _enlace(ticket), "codigo": codigo, "sistema": settings.CORREO_NOMBRE,
        "ticket": ticket,
    }
    asunto_final = _una_linea(f"{codigo} · {asunto}" if codigo else asunto, 150)
    try:
        with transaction.atomic():
            return Notificacion.objects.create(
                destinatario=destinatario, email=destinatario.email.strip(), ticket=ticket, evento=evento,
                asunto=asunto_final, texto=render_to_string("correo/aviso.txt", contexto),
                html=render_to_string("correo/aviso.html", contexto), clave=clave,
                enviar_despues_de=enviar_despues_de or timezone.now())
    except IntegrityError:  # otra petición creó el mismo aviso a la vez
        return None


# --------------------------------------------------------------------------- #
# Eventos de tickets (los llama tickets/services.py)
# --------------------------------------------------------------------------- #
def _resumen(ticket):
    return [f"Asunto: {ticket.titulo}", f"Solicitante: {ticket.solicitante.nombre_completo}"
            + (f" ({ticket.solicitante.departamento})" if ticket.solicitante.departamento else ""),
            f"Prioridad: {ticket.get_prioridad_display()}"]


def asignado(ticket, por):
    """Se asignó o se tomó un ticket: avisa al técnico (si no fue él) y al solicitante de quién lo atiende."""
    tecnico = ticket.tecnico
    if tecnico is None:
        return
    avisar(tecnico, Evento.ASIGNADO, ticket, asunto="Se te asignó un ticket", titulo="Se te asignó un ticket",
           lineas=_resumen(ticket) + [f"Vence: {_local(ticket.fecha_limite)}"], excluir=por)
    avisar(ticket.solicitante, Evento.ATENDIENDO, ticket, asunto="Ya lo están atendiendo",
           titulo="Tu ticket ya tiene responsable", lineas=[f"Asunto: {ticket.titulo}", f"Lo atiende: {tecnico.nombre_completo}"],
           boton="Ver mi ticket", excluir=por)


def comentario(ticket, comentario_obj):
    """Un comentario público va a la otra parte; una nota interna solo al técnico responsable (nunca al solicitante)."""
    autor = comentario_obj.autor
    if comentario_obj.interno:
        avisar(ticket.tecnico, Evento.NOTA_INTERNA, ticket, asunto=f"Nota interna de {autor.nombre_completo}",
               titulo=f"{autor.nombre_completo} dejó una nota interna", lineas=[f"Asunto: {ticket.titulo}"],
               cita=comentario_obj.texto, excluir=autor)
        return
    if autor.es_tecnico:
        avisar(ticket.solicitante, Evento.COMENTARIO, ticket, asunto=f"Nuevo comentario de {autor.nombre_completo}",
               titulo=f"{autor.nombre_completo} respondió a tu ticket", lineas=[f"Asunto: {ticket.titulo}"],
               cita=comentario_obj.texto, boton="Ver y responder", excluir=autor)
    else:
        avisar(ticket.tecnico, Evento.COMENTARIO, ticket, asunto=f"Nuevo comentario de {autor.nombre_completo}",
               titulo=f"{autor.nombre_completo} comentó en su ticket", lineas=[f"Asunto: {ticket.titulo}"],
               cita=comentario_obj.texto, boton="Ver y responder", excluir=autor)


def estado_cambiado(ticket, por, anterior, nuevo, nota=""):
    """Cambio de estado hecho por TI: avisa al solicitante (resolver y reabrir tienen sus propios avisos)."""
    avisar(ticket.solicitante, Evento.ESTADO, ticket, asunto=f"Ahora está «{nuevo}»", titulo="Cambió el estado de tu ticket",
           lineas=[f"Asunto: {ticket.titulo}", f"Estado: {anterior} → {nuevo}"], cita=nota, boton="Ver mi ticket", excluir=por)


def resuelto(ticket, por):
    dias = settings.DIAS_AUTOCIERRE
    avisar(ticket.solicitante, Evento.RESUELTO, ticket, asunto="Tu ticket fue resuelto", titulo="Tu ticket fue resuelto",
           lineas=[f"Asunto: {ticket.titulo}",
                   "Si estás conforme, ciérralo. Si el problema sigue, reábrelo indicando el motivo.",
                   f"Si no respondes en {dias} días, se cerrará automáticamente."],
           cita=ticket.solucion, boton="Revisar y cerrar", excluir=por)


def cerrado(ticket, por, automatico=False):
    quien = "se cerró automáticamente por falta de respuesta" if automatico else f"lo cerró {por.nombre_completo}"
    avisar(ticket.tecnico, Evento.CERRADO, ticket, asunto="Ticket cerrado", titulo="Un ticket que resolviste se cerró",
           lineas=[f"Asunto: {ticket.titulo}", f"Cierre: {quien}"], excluir=por if not automatico else None)


def reabierto_por_solicitante(ticket, por, motivo):
    avisar(ticket.tecnico, Evento.REABIERTO, ticket, asunto="El solicitante reabrió el ticket",
           titulo=f"{por.nombre_completo} no está conforme con la solución",
           lineas=[f"Asunto: {ticket.titulo}"], cita=motivo, excluir=por)


def reprogramado(ticket, por, fecha, motivo):
    f = fecha.strftime("%d/%m/%Y")
    avisar(ticket.solicitante, Evento.REPROGRAMADO, ticket, asunto=f"Reprogramado para el {f}",
           titulo="Tu ticket se atenderá otro día",
           lineas=[f"Asunto: {ticket.titulo}", f"Nueva fecha: {f}", f"Lo atiende: {ticket.tecnico.nombre_completo}" if ticket.tecnico else ""],
           cita=motivo, boton="Ver mi ticket", excluir=por)
    avisar(ticket.tecnico, Evento.REPROGRAMADO, ticket, asunto=f"Reprogramado para el {f}",
           titulo=f"{por.nombre_completo} reprogramó tu ticket", lineas=[f"Asunto: {ticket.titulo}", f"Nueva fecha: {f}"],
           cita=motivo, excluir=por)


def recordatorio_del_dia(ticket, fecha):
    """Recordatorio al técnico el día para el que se reprogramó el ticket (se envía a la HORA_RECORDATORIO)."""
    inicio = timezone.make_aware(datetime.combine(fecha, time.min))
    cuando = max(timezone.now(), inicio + timedelta(hours=settings.HORA_RECORDATORIO))
    avisar(ticket.tecnico, Evento.RECORDATORIO, ticket, asunto="Hoy toca atender este ticket",
           titulo="Hoy toca atender este ticket", lineas=_resumen(ticket) + [f"Vence: {_local(ticket.fecha_limite)}"],
           clave=f"recordatorio:{ticket.pk}:{fecha.isoformat()}", enviar_despues_de=cuando)


def sla_por_vencer(ticket):
    horas = settings.SLA_AVISO_HORAS
    return avisar(ticket.tecnico, Evento.SLA_POR_VENCER, ticket, asunto=f"Le quedan menos de {horas} h de plazo",
           titulo=f"A este ticket le quedan menos de {horas} horas de plazo", lineas=_resumen(ticket) + [f"Vence: {_local(ticket.fecha_limite)}"],
           boton="Atender ahora", clave=f"sla-por-vencer:{ticket.pk}:{ticket.fecha_limite.isoformat()}")


def sla_vencido(ticket):
    return avisar(ticket.tecnico, Evento.SLA_VENCIDO, ticket, asunto="Se venció el plazo (SLA)", titulo="Se venció el plazo de este ticket",
           lineas=_resumen(ticket) + [f"Venció: {_local(ticket.fecha_limite)}"], boton="Atender ahora",
           clave=f"sla-vencido:{ticket.pk}:{ticket.fecha_limite.isoformat()}")
