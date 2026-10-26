import logging
from django.core.management.base import BaseCommand, CommandError
from auditoria.servicios import verificar_cadena
logger = logging.getLogger('auditoria')

class Command(BaseCommand):
    help = 'Verifica la integridad de la cadena de hashes de la auditoría. Termina con error si fue alterada.'

    def handle(self, *args, **opciones):
        total, problemas = verificar_cadena()
        if not problemas:
            self.stdout.write(self.style.SUCCESS(f'OK: {total} registros íntegros.'))
            return
        for p in problemas:
            self.stdout.write(self.style.ERROR(p))
        logger.error('La auditoría fue ALTERADA: %s problema(s) en %s registros. Primero: %s', len(problemas), total, problemas[0])
        raise CommandError(f'{len(problemas)} problema(s) en {total} registros de auditoría.')
