"""
Entrega de un aviso por el medio configurado (TICKETS_CORREO): SMTP o Microsoft Graph, y procesado de la cola.
"""
import logging
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives
from django.utils import timezone

from . import graph
from .imagenes import CONTENT_ID, imagen_correo, lleva_imagen
from .graph import ErrorPermanente, ErrorTemporal
from .models import Notificacion

logger = logging.getLogger("notificaciones")

# Espera antes de cada reintento (minutos): 1.º, 2.º, 3.º y 4.º fallo
ESPERAS = (1, 5, 15, 60)
CABECERAS = {"Auto-Submitted": "auto-generated", "X-Auto-Response-Suppress": "All"}  # evita respuestas automáticas


def enviar(n):
    """Entrega una notificación. Lanza ErrorTemporal o ErrorPermanente si no se pudo."""
    modo = settings.CORREO_MODO
    if modo == "desactivado":
        raise ErrorPermanente("El envío de correo está desactivado (TICKETS_CORREO=desactivado).")
    if modo == "graph":
        graph.enviar(n.email, n.asunto, n.texto, n.html)
        return
    _smtp(n)


class _CorreoHtml(EmailMultiAlternatives):
    """Correo con texto y HTML; si lleva imagen, el HTML pasa a ser multipart/related con la imagen incrustada (Content-ID), la estructura que muestran bien Outlook y Gmail."""
    imagen = None

    def message(self, **kwargs):
        msg = super().message(**kwargs)
        if self.imagen:
            for parte in msg.iter_parts():
                if parte.get_content_type() == "text/html":
                    parte.add_related(self.imagen, "image", "png", cid=f"<{CONTENT_ID}>", disposition="inline", filename="aurora.png")
                    break
        return msg


def _smtp(n):
    correo = _CorreoHtml(subject=n.asunto, body=n.texto, from_email=settings.DEFAULT_FROM_EMAIL, to=[n.email], headers=CABECERAS)
    if n.html:
        correo.attach_alternative(n.html, "text/html")
        correo.imagen = imagen_correo() if lleva_imagen(n.html) else None
    try:
        correo.send(fail_silently=False)
    except BadHeaderError as e:
        raise ErrorPermanente(f"Cabecera de correo no válida: {e}") from None
    except smtplib.SMTPRecipientsRefused as e:
        raise ErrorPermanente(f"El servidor rechazó al destinatario: {list(e.recipients.values())[:1]}") from None
    except smtplib.SMTPDataError as e:
        if 500 <= e.smtp_code < 600:
            raise ErrorPermanente(f"El servidor rechazó el mensaje (SMTP {e.smtp_code}).") from None
        raise ErrorTemporal(f"El servidor no aceptó el mensaje (SMTP {e.smtp_code}).") from None
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        raise ErrorTemporal(f"Fallo del servidor de correo: {type(e).__name__}: {str(e)[:150]}") from None


# --------------------------------------------------------------------------- #
# Cola
# --------------------------------------------------------------------------- #
def procesar_cola(limite=100, ahora=None):
    """
    Envía los avisos pendientes cuya hora ya llegó. Cada uno se «reclama» antes de enviarlo, así dos ejecuciones
    simultáneas nunca envían el mismo correo. Devuelve un resumen {enviados, reintentos, fallidos}.
    """
    ahora = ahora or timezone.now()
    resumen = {"enviados": 0, "reintentos": 0, "fallidos": 0}
    # Un aviso que quedó «enviando» (el proceso se cortó) vuelve a la cola pasados 10 minutos
    Notificacion.objects.filter(estado=Notificacion.Estado.ENVIANDO, enviar_despues_de__lt=ahora - timedelta(minutes=10)
                                ).update(estado=Notificacion.Estado.PENDIENTE)
    ids = list(Notificacion.objects.filter(estado=Notificacion.Estado.PENDIENTE, enviar_despues_de__lte=ahora)
               .order_by("id").values_list("pk", flat=True)[:limite])
    for pk in ids:
        if not Notificacion.objects.filter(pk=pk, estado=Notificacion.Estado.PENDIENTE).update(
                estado=Notificacion.Estado.ENVIANDO, enviar_despues_de=ahora):
            continue  # otra ejecución ya lo tomó
        n = Notificacion.objects.get(pk=pk)
        n.intentos += 1
        try:
            enviar(n)
        except ErrorPermanente as e:
            n.estado, n.ultimo_error = Notificacion.Estado.FALLIDO, str(e)[:300]
            resumen["fallidos"] += 1
            logger.warning("Aviso #%s fallido (definitivo): %s", n.pk, n.ultimo_error)
        except Exception as e:  # noqa: BLE001  (temporal o inesperado: se reintenta)
            n.ultimo_error = (str(e) if isinstance(e, ErrorTemporal) else f"{type(e).__name__}: {e}")[:300]
            if n.intentos >= settings.NOTIF_MAX_INTENTOS:
                n.estado = Notificacion.Estado.FALLIDO
                resumen["fallidos"] += 1
                logger.error("Aviso #%s fallido tras %s intentos: %s", n.pk, n.intentos, n.ultimo_error)
            else:
                n.estado = Notificacion.Estado.PENDIENTE
                n.enviar_despues_de = ahora + timedelta(minutes=ESPERAS[min(n.intentos - 1, len(ESPERAS) - 1)])
                resumen["reintentos"] += 1
                logger.warning("Aviso #%s: intento %s fallido, se reintenta: %s", n.pk, n.intentos, n.ultimo_error)
        else:
            n.estado, n.enviada, n.ultimo_error = Notificacion.Estado.ENVIADO, timezone.now(), ""
            resumen["enviados"] += 1
        n.save()
    return resumen


def purgar(ahora=None):
    """Borra de la bandeja los avisos enviados hace más de NOTIF_RETENCION_DIAS días."""
    ahora = ahora or timezone.now()
    corte = ahora - timedelta(days=settings.NOTIF_RETENCION_DIAS)
    return Notificacion.objects.filter(estado=Notificacion.Estado.ENVIADO, enviada__lt=corte).delete()[0]
