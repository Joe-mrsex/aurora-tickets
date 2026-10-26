import logging
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from notificaciones import envio, servicios
from tickets import services
logger = logging.getLogger('notificaciones')

class Command(BaseCommand):
    help = 'Reanuda tickets reprogramados, genera avisos de SLA y envía los correos pendientes.'

    def add_arguments(self, parser):
        parser.add_argument('--cada', type=int, default=0, metavar='SEGUNDOS', help='Repetir sin parar cada N segundos (para desarrollo; Ctrl+C para detener). En el servidor se usa la tarea programada y no este modo.')

    def handle(self, *args, **opciones):
        espera = opciones['cada']
        if not espera:
            return self.ciclo()
        self.stdout.write(f'Procesando notificaciones cada {espera} s. Ctrl+C para detener.')
        try:
            while True:
                self.ciclo()
                time.sleep(espera)
        except KeyboardInterrupt:
            self.stdout.write('Detenido.')

    def ciclo(self):
        ahora = timezone.now()
        reanudados = services.reanudar_programados(ahora)
        if not servicios.activo():
            self.stdout.write(f'reanudados={reanudados} correo=desactivado')
            return
        sla = services.avisar_sla(ahora)
        r = envio.procesar_cola(ahora=ahora)
        purgados = envio.purgar(ahora)
        linea = f"reanudados={reanudados} avisos_sla={sla} enviados={r['enviados']} reintentos={r['reintentos']} fallidos={r['fallidos']} purgados={purgados}"
        self.stdout.write(linea)
        if r['enviados'] or r['fallidos'] or reanudados or sla:
            logger.info('procesar_notificaciones: %s', linea)
