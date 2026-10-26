"""
Códigos de un solo uso por tiempo (TOTP, RFC 6238), los mismos que generan Microsoft Authenticator, Google Authenticator y similares.

El sistema y el celular comparten un secreto (se transmite una sola vez, al escanear el QR). Cada 30 segundos ambos calculan el mismo número de
6 dígitos a partir de ese secreto y la hora, sin necesidad de internet, de correo ni de SMS.
"""
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
    """20 bytes aleatorios (160 bits) en base32, el formato que entienden las aplicaciones."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _clave(secreto):
    return base64.b32decode(secreto + "=" * (-len(secreto) % 8), casefold=True)


def codigo(secreto, paso, digitos=DIGITOS):
    """El número que corresponde al intervalo de tiempo `paso` (segundos desde 1970 divididos entre 30)."""
    mac = hmac.new(_clave(secreto), struct.pack(">Q", paso), hashlib.sha1).digest()
    desplazamiento = mac[-1] & 0x0F
    numero = (struct.unpack(">I", mac[desplazamiento:desplazamiento + 4])[0] & 0x7FFFFFFF) % (10 ** digitos)
    return str(numero).zfill(digitos)


def paso_actual(ahora=None):
    return int((time.time() if ahora is None else ahora) // PASO)


def verificar(secreto, texto, ahora=None, ultimo_paso=0, ventana=1):
    """
    Devuelve el intervalo (paso) al que corresponde el código escrito, o None si no es válido.
    - Se tolera `ventana` intervalos antes y después (el reloj del celular puede estar desfasado unos segundos).
    - Un intervalo ya usado (o anterior) no se acepta otra vez: así un código espiado no sirve para entrar de nuevo.
    """
    texto = "".join(texto.split()) if isinstance(texto, str) else ""
    if len(texto) != DIGITOS or not texto.isascii() or not texto.isdigit():
        return None
    actual = paso_actual(ahora)
    aceptado = None
    for paso in range(actual - ventana, actual + ventana + 1):  # se recorren todos, siempre: el tiempo de respuesta no revela cuál acertó
        if hmac.compare_digest(codigo(secreto, paso), texto) and paso > ultimo_paso:
            aceptado = paso
    return aceptado


def uri_aprovisionamiento(secreto, usuario, emisor):
    """La dirección que el QR contiene y que la aplicación del celular sabe leer."""
    etiqueta = quote(f"{emisor}:{usuario}", safe="")
    return f"otpauth://totp/{etiqueta}?secret={secreto}&issuer={quote(emisor, safe='')}&algorithm=SHA1&digits={DIGITOS}&period={PASO}"


def qr_svg(uri):
    """El QR como imagen SVG dentro de la propia página (sin JavaScript, sin archivos, sin servicios externos)."""
    import segno
    return segno.make(uri, error="m").svg_inline(scale=5, border=2, dark="#000000", light="#ffffff")
