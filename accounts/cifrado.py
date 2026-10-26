import base64
import logging
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import models
logger = logging.getLogger('accounts')
PREFIJO = 'f1:'
CONTEXTO = b'tickets-tics/secreto-segundo-factor/v1'

@lru_cache(maxsize=4)
def _fernet(clave_secreta):
    llave = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=CONTEXTO).derive(clave_secreta.encode('utf-8'))
    return Fernet(base64.urlsafe_b64encode(llave))

def cifrar(texto):
    if not texto:
        return ''
    return PREFIJO + _fernet(settings.SECRET_KEY).encrypt(texto.encode('utf-8')).decode('ascii')

def descifrar(valor):
    if not valor:
        return ''
    if not valor.startswith(PREFIJO):
        return valor
    try:
        return _fernet(settings.SECRET_KEY).decrypt(valor[len(PREFIJO):].encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError):
        return None

class Ilegible(str):

    def __new__(cls, original):
        objeto = super().__new__(cls, '')
        objeto.original = original
        return objeto

class CampoCifrado(models.CharField):

    def from_db_value(self, value, expression, connection):
        if not value:
            return ''
        abierto = descifrar(value)
        if abierto is None:
            logger.critical('No se pudo descifrar un secreto del segundo factor: ¿cambió TICKETS_SECRET_KEY o se restauró una base de datos sin su configuracion_local.bat?')
            return Ilegible(value)
        return abierto

    def get_prep_value(self, value):
        if isinstance(value, Ilegible):
            return value.original
        value = super().get_prep_value(value)
        return cifrar(value) if value else ''
