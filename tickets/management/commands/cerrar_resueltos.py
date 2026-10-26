from django.conf import settings
from django.core.management.base import BaseCommand
from tickets.services import cerrar_resueltos_vencidos

class Command(BaseCommand):
    help = 'Cierra los tickets Resueltos que el usuario no ha confirmado en DIAS_AUTOCIERRE días. Programar a diario.'

    def handle(self, *args, **opciones):
        n = cerrar_resueltos_vencidos(settings.DIAS_AUTOCIERRE)
        self.stdout.write(self.style.SUCCESS(f'{n} ticket(s) cerrados automáticamente.'))
