"""
Cifrado de los secretos del segundo factor dentro de la base de datos.

El secreto de cada persona (con el que el servidor calcula su código de 6 dígitos) no se puede guardar «con hash» porque el servidor necesita
el valor real. Por eso se guarda CIFRADO (Fernet: AES-128-CBC + HMAC-SHA256): quien consiga solo la base de datos (un respaldo, el archivo, una
inyección SQL) ve texto ilegible y no puede generar códigos.

La llave NO está en la base de datos: se deriva de TICKETS_SECRET_KEY (configuracion_local.bat). Si esa clave se pierde o se cambia, los secretos
quedan ilegibles: nadie puede pasar el segundo factor hasta reiniciarlo (manage.py reiniciar_2fa --todos). Por eso hay que respaldar
configuracion_local.bat junto con la base de datos.

CampoCifrado es un campo de texto que cifra al guardar y descifra al leer: el resto del código sigue usando el secreto normal.
"""
import base64
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import models

logger = logging.getLogger("accounts")

PREFIJO = "f1:"
CONTEXTO = b"tickets-tics/secreto-segundo-factor/v1"


@lru_cache(maxsize=4)
def _fernet(clave_secreta):
    llave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXTO).derive(clave_secreta.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(llave))


def cifrar(texto):
    if not texto:
        return ""
    return PREFIJO + _fernet(settings.SECRET_KEY).encrypt(texto.encode("utf-8")).decode("ascii")


def descifrar(valor):
    """Devuelve el texto original. Un valor sin prefijo es un secreto antiguo sin cifrar (la migración lo cifra). None si no se puede abrir."""
    if not valor:
        return ""
    if not valor.startswith(PREFIJO):
        return valor
    try:
        return _fernet(settings.SECRET_KEY).decrypt(valor[len(PREFIJO):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


class Ilegible(str):
    """Secreto que no se pudo abrir (llave distinta o dato alterado). Vale «» para verificar, pero al guardar conserva el dato original intacto."""

    def __new__(cls, original):
        objeto = super().__new__(cls, "")
        objeto.original = original
        return objeto


class CampoCifrado(models.CharField):
    def from_db_value(self, value, expression, connection):
        if not value:
            return ""
        abierto = descifrar(value)
        if abierto is None:
            logger.critical("No se pudo descifrar un secreto del segundo factor: ¿cambió TICKETS_SECRET_KEY o se restauró una base de datos sin su configuracion_local.bat?")
            return Ilegible(value)
        return abierto

    def get_prep_value(self, value):
        if isinstance(value, Ilegible):
            return value.original
        value = super().get_prep_value(value)
        return cifrar(value) if value else ""
