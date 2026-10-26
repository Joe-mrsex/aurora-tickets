"""
Restaura la base de datos desde un respaldo hecho con respaldo_bd. La aplicación debe estar detenida.

    manage.py restaurar_bd respaldos/db_20261011_0200.dump
"""
from django.core.management.base import BaseCommand, CommandError

from config import basedatos


class Command(BaseCommand):
    help = "Reemplaza la base de datos por el contenido de un respaldo."

    def add_arguments(self, parser):
        parser.add_argument("archivo")

    def handle(self, *args, **opciones):
        try:
            basedatos.restaurar(opciones["archivo"])
        except basedatos.ErrorDeBaseDeDatos as error:
            raise CommandError(f"Falló la restauración de la base de datos: {error}") from None
        self.stdout.write(self.style.SUCCESS(f"Base de datos restaurada desde {opciones['archivo']}"))
