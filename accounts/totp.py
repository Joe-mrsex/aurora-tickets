import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote
PASO = 30
DIGITOS = 6

def generar_secreto():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')

def _clave(secreto):
    return base64.b32decode(secreto + '=' * (-len(secreto) % 8), casefold=True)

def codigo(secreto, paso, digitos=DIGITOS):
    mac = hmac.new(_clave(secreto), struct.pack('>Q', paso), hashlib.sha1).digest()
    desplazamiento = mac[-1] & 15
    numero = (struct.unpack('>I', mac[desplazamiento:desplazamiento + 4])[0] & 2147483647) % 10 ** digitos
    return str(numero).zfill(digitos)

def paso_actual(ahora=None):
    return int((time.time() if ahora is None else ahora) // PASO)

def verificar(secreto, texto, ahora=None, ultimo_paso=0, ventana=1):
    texto = ''.join(texto.split()) if isinstance(texto, str) else ''
    if len(texto) != DIGITOS or not texto.isascii() or (not texto.isdigit()):
        return None
    actual = paso_actual(ahora)
    aceptado = None
    for paso in range(actual - ventana, actual + ventana + 1):
        if hmac.compare_digest(codigo(secreto, paso), texto) and paso > ultimo_paso:
            aceptado = paso
    return aceptado

def uri_aprovisionamiento(secreto, usuario, emisor):
    etiqueta = quote(f'{emisor}:{usuario}', safe='')
    return f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(emisor, safe='')}&algorithm=SHA1&digits={DIGITOS}&period={PASO}"

def qr_svg(uri):
    import segno
    return segno.make(uri, error='m').svg_inline(scale=5, border=2, dark='#000000', light='#ffffff')
