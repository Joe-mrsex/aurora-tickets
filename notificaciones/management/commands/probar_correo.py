"""
Prueba la configuración de correo enviando UN mensaje de prueba ahora mismo (sin pasar por la cola) y mostrando el
resultado o el motivo exacto del fallo.

    manage.py probar_correo nombre@empresa.com
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.template.loader import render_to_string

from notificaciones import envio
from notificaciones.graph import ErrorPermanente, ErrorTemporal
from notificaciones.models import Notificacion


class Command(BaseCommand):
    help = "Envía un correo de prueba para comprobar la configuración (TICKETS_CORREO)."

    def add_arguments(self, parser):
        parser.add_argument("destino", help="Dirección a la que se envía la prueba")

    def handle(self, *args, **opciones):
        destino = opciones["destino"].strip()
        try:
            validate_email(destino)
        except ValidationError:
            raise CommandError(f"«{destino}» no es una dirección de correo válida.") from None
        modo = settings.CORREO_MODO
        self.stdout.write(f"Modo de correo: {modo} | Remitente: {settings.CORREO_REMITENTE} | Enlaces: {settings.URL_BASE}")
        if modo == "desactivado":
            raise CommandError("El correo está desactivado. Define TICKETS_CORREO=graph (Microsoft 365) o smtp en configuracion_local.bat.")
        ctx = {"nombre": "equipo", "titulo": "Correo de prueba del sistema de tickets", "sistema": settings.CORREO_NOMBRE,
               "lineas": ["Si recibes este mensaje, el envío de avisos está bien configurado."], "cita": "",
               "boton": "Abrir el sistema", "enlace": settings.URL_BASE + "/", "codigo": ""}
        n = Notificacion(email=destino, evento=Notificacion.Evento.PRUEBA, asunto="Prueba de correo · " + settings.CORREO_NOMBRE,
                         texto=render_to_string("correo/aviso.txt", ctx), html=render_to_string("correo/aviso.html", ctx))
        try:
            envio.enviar(n)
        except (ErrorPermanente, ErrorTemporal) as e:
            raise CommandError(f"NO se pudo enviar: {e}") from None
        self.stdout.write(self.style.SUCCESS(f"Enviado a {destino}. Revisa la bandeja de entrada (y el correo no deseado)."))
