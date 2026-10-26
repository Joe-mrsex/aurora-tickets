"""
Tarea periódica del sistema: se ejecuta cada minuto desde el Programador de tareas (tarea «Tickets-Notificaciones»).

  1. Reanuda el SLA de los tickets reprogramados cuyo día llegó, y deja anotado el recordatorio del técnico.
  2. Avisa al técnico de los tickets a punto de vencer o vencidos.
  3. Envía los correos pendientes (reintentando los que fallaron).
  4. Borra de la bandeja los avisos enviados hace mucho.

Los pasos 2 y 3 solo hacen algo si el correo está activado (TICKETS_CORREO); el paso 1 siempre se ejecuta.
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from notificaciones import envio, servicios
from tickets import services

logger = logging.getLogger("notificaciones")


class Command(BaseCommand):
    help = "Reanuda tickets reprogramados, genera avisos de SLA y envía los correos pendientes."

    def add_arguments(self, parser):
        parser.add_argument("--cada", type=int, default=0, metavar="SEGUNDOS",
                            help="Repetir sin parar cada N segundos (para desarrollo; Ctrl+C para detener). "
                                 "En el servidor se usa la tarea programada y no este modo.")

    def handle(self, *args, **opciones):
        espera = opciones["cada"]
        if not espera:
            return self.ciclo()
        self.stdout.write(f"Procesando notificaciones cada {espera} s. Ctrl+C para detener.")
        try:
            while True:
                self.ciclo()
                time.sleep(espera)
        except KeyboardInterrupt:
            self.stdout.write("Detenido.")

    def ciclo(self):
        ahora = timezone.now()
        reanudados = services.reanudar_programados(ahora)
        if not servicios.activo():
            self.stdout.write(f"reanudados={reanudados} correo=desactivado")
            return
        sla = services.avisar_sla(ahora)
        r = envio.procesar_cola(ahora=ahora)
        purgados = envio.purgar(ahora)
        linea = (f"reanudados={reanudados} avisos_sla={sla} enviados={r['enviados']} "
                 f"reintentos={r['reintentos']} fallidos={r['fallidos']} purgados={purgados}")
        self.stdout.write(linea)
        if r["enviados"] or r["fallidos"] or reanudados or sla:
            logger.info("procesar_notificaciones: %s", linea)
