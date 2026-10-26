"""
Respaldo y restauración de la base de datos, igual para SQLite (desarrollo) y PostgreSQL (producción).

SQLite: copia consistente con la API de respaldo del propio motor (db_AAAAMMDD_HHMM.sqlite3).
PostgreSQL: pg_dump en formato personalizado (db_AAAAMMDD_HHMM.dump), que pg_restore devuelve entero o no toca nada (--single-transaction).
La contraseña de PostgreSQL viaja en la variable PGPASSWORD del proceso hijo, nunca en la línea de comandos.
"""
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from django.conf import settings
from django.db import connections


class ErrorDeBaseDeDatos(Exception):
    pass


def _config():
    return settings.DATABASES["default"]


def es_postgres():
    return _config()["ENGINE"].endswith("postgresql")


def extension():
    return ".dump" if es_postgres() else ".sqlite3"


def _herramienta(nombre):
    carpeta = os.environ.get("TICKETS_PG_BIN", r"C:\PostgreSQL\bin")
    ruta = Path(carpeta) / (nombre + ".exe")
    if ruta.exists():
        return str(ruta)
    encontrada = shutil.which(nombre)
    if encontrada:
        return encontrada
    raise ErrorDeBaseDeDatos(f"No encuentro {nombre} en {carpeta}. Define TICKETS_PG_BIN con la carpeta bin de PostgreSQL.")


def _conexion_pg():
    c = _config()
    return ["-h", str(c["HOST"]), "-p", str(c["PORT"]), "-U", c["USER"]], {**os.environ, "PGPASSWORD": c["PASSWORD"]}


def _ejecutar(argumentos, entorno):
    r = subprocess.run(argumentos, env=entorno, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise ErrorDeBaseDeDatos((r.stderr or r.stdout).strip()[-600:] or f"{Path(argumentos[0]).name} terminó con código {r.returncode}")
    return r


def respaldar(destino):
    """Crea el respaldo en la ruta `destino` (con la extensión que corresponda al motor)."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if es_postgres():
        conexion, entorno = _conexion_pg()
        _ejecutar([_herramienta("pg_dump"), *conexion, "-Fc", "--no-owner", "--no-privileges", "-f", str(destino), _config()["NAME"]], entorno)
        _ejecutar([_herramienta("pg_restore"), "--list", str(destino)], entorno)
    else:
        origen = sqlite3.connect(str(_config()["NAME"]))
        copia = sqlite3.connect(str(destino))
        try:
            origen.backup(copia)
        finally:
            copia.close()
            origen.close()
    return destino


def restaurar(archivo):
    """Reemplaza el contenido de la base de datos por el del respaldo. La aplicación debe estar detenida."""
    archivo = Path(archivo)
    if not archivo.exists():
        raise ErrorDeBaseDeDatos(f"No existe {archivo}")
    connections.close_all()
    if es_postgres():
        conexion, entorno = _conexion_pg()
        _ejecutar([_herramienta("pg_restore"), *conexion, "-d", _config()["NAME"], "--clean", "--if-exists", "--no-owner", "--no-privileges",
                   "--single-transaction", str(archivo)], entorno)
    else:
        shutil.copyfile(archivo, str(_config()["NAME"]))
