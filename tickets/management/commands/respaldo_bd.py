"""
Respalda la base de datos (SQLite o PostgreSQL, según TICKETS_DB_MOTOR) en la carpeta indicada.

    manage.py respaldo_bd respaldos 20261011_0200
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from config import basedatos


class Command(BaseCommand):
    help = "Respalda la base de datos en <carpeta>/db_<sello><extensión>."

    def add_arguments(self, parser):
        parser.add_argument("carpeta")
        parser.add_argument("sello", help="Fecha y hora del respaldo, p. ej. 20261011_0200")

    def handle(self, *args, **opciones):
        destino = Path(opciones["carpeta"]) / f"db_{opciones['sello']}{basedatos.extension()}"
        try:
            basedatos.respaldar(destino)
        except basedatos.ErrorDeBaseDeDatos as error:
            raise CommandError(f"Falló el respaldo de la base de datos: {error}") from None
        self.stdout.write(f"Base de datos respaldada: {destino}")
