import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from django.conf import settings
from .imagenes import CONTENT_ID, imagen_correo, lleva_imagen
logger = logging.getLogger('notificaciones')
TIMEOUT = 20

class ErrorTemporal(Exception):
    pass

class ErrorPermanente(Exception):
    pass
_token = {'valor': None, 'expira': 0.0}

def _peticion(url, datos, cabeceras, json_body=False):
    cuerpo = json.dumps(datos).encode('utf-8') if json_body else urllib.parse.urlencode(datos).encode('utf-8')
    cab = {'Content-Type': 'application/json' if json_body else 'application/x-www-form-urlencoded', **cabeceras}
    return urllib.request.Request(url, data=cuerpo, headers=cab, method='POST')

def _mensaje_graph(error):
    try:
        cuerpo = json.loads(error.read().decode('utf-8', 'replace'))
        info = cuerpo.get('error', {})
        if isinstance(info, dict):
            return f"{info.get('code', '')}: {info.get('message', '')}"[:250]
        return f"{cuerpo.get('error', '')}: {cuerpo.get('error_description', '')}"[:250]
    except Exception:
        return ''

def obtener_token(forzar=False):
    ahora = time.time()
    if not forzar and _token['valor'] and (ahora < _token['expira'] - 60):
        return _token['valor']
    url = f'https://login.microsoftonline.com/{urllib.parse.quote(settings.GRAPH_TENANT)}/oauth2/v2.0/token'
    datos = {'grant_type': 'client_credentials', 'client_id': settings.GRAPH_CLIENT_ID, 'client_secret': settings.GRAPH_CLIENT_SECRET, 'scope': 'https://graph.microsoft.com/.default'}
    try:
        with urllib.request.urlopen(_peticion(url, datos, {}), timeout=TIMEOUT) as r:
            respuesta = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        detalle = _mensaje_graph(e)
        if e.code in (400, 401):
            raise ErrorPermanente(f'Microsoft rechazó las credenciales de la aplicación (HTTP {e.code}). {detalle}') from None
        raise ErrorTemporal(f'No se pudo obtener el token de Microsoft (HTTP {e.code}). {detalle}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorTemporal(f'No se pudo contactar con Microsoft: {type(e).__name__}') from None
    _token['valor'] = respuesta['access_token']
    _token['expira'] = ahora + int(respuesta.get('expires_in', 3600))
    return _token['valor']

def enviar(destino, asunto, texto, html=''):
    remitente = settings.CORREO_REMITENTE
    url = f'https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(remitente)}/sendMail'
    mensaje = {'message': {'subject': asunto, 'body': {'contentType': 'HTML' if html else 'Text', 'content': html or texto}, 'toRecipients': [{'emailAddress': {'address': destino}}]}, 'saveToSentItems': False}
    imagen = imagen_correo() if lleva_imagen(html) else None
    if imagen:
        mensaje['message']['attachments'] = [{'@odata.type': '#microsoft.graph.fileAttachment', 'name': 'aurora.png', 'contentType': 'image/png', 'contentBytes': base64.b64encode(imagen).decode('ascii'), 'isInline': True, 'contentId': CONTENT_ID}]
    for intento in (1, 2):
        token = obtener_token(forzar=intento == 2)
        try:
            with urllib.request.urlopen(_peticion(url, mensaje, {'Authorization': f'Bearer {token}'}, json_body=True), timeout=TIMEOUT) as r:
                if r.status not in (200, 202):
                    raise ErrorTemporal(f'Respuesta inesperada de Microsoft: HTTP {r.status}')
                return
        except urllib.error.HTTPError as e:
            detalle = _mensaje_graph(e)
            if e.code == 401 and intento == 1:
                _token['valor'] = None
                continue
            if e.code in (429, 500, 502, 503, 504) or e.code == 401:
                raise ErrorTemporal(f'Microsoft no pudo atender el envío (HTTP {e.code}). {detalle}') from None
            raise ErrorPermanente(f'Microsoft rechazó el envío (HTTP {e.code}). {detalle}') from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErrorTemporal(f'No se pudo contactar con Microsoft: {type(e).__name__}') from None
