from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from notificaciones.models import Notificacion

class Command(BaseCommand):
    help = 'Cuenta los correos fallidos y los pendientes atrasados.'

    def handle(self, *args, **opciones):
        fallidos = Notificacion.objects.filter(estado=Notificacion.Estado.FALLIDO).count()
        atrasados = Notificacion.objects.filter(estado=Notificacion.Estado.PENDIENTE, creada__lt=timezone.now() - timedelta(minutes=30)).count()
        self.stdout.write(f'{fallidos} {atrasados}')
