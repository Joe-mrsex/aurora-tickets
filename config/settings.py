import os
import sys
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
BASE_DIR = Path(__file__).resolve().parent.parent
PRUEBAS = len(sys.argv) > 1 and sys.argv[1] == 'test'

def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).strip().lower() in ('1', 'true', 'si', 'yes')
DEBUG = env_bool('TICKETS_DEBUG', False)
NOMBRE_SISTEMA = os.environ.get('TICKETS_NOMBRE', 'Aurora')
SUBTITULO_SISTEMA = os.environ.get('TICKETS_SUBTITULO', 'Tickets TICS')
_CLAVE_DESARROLLO = 'clave-solo-para-desarrollo-cambiar-en-produccion'
SECRET_KEY = os.environ.get('TICKETS_SECRET_KEY', _CLAVE_DESARROLLO)
if not DEBUG and (not PRUEBAS) and (SECRET_KEY == _CLAVE_DESARROLLO or len(SECRET_KEY) < 40 or SECRET_KEY.startswith('CAMBIAR')):
    raise ImproperlyConfigured('Falta TICKETS_SECRET_KEY (mínimo 40 caracteres aleatorios). Genera una con: python -c "import secrets; print(secrets.token_urlsafe(50))"')
ALLOWED_HOSTS = [h for h in os.environ.get('TICKETS_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('TICKETS_CSRF_ORIGINS', '').split(',') if o]
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'axes', 'accounts', 'tickets', 'bitacora', 'auditoria', 'dashboard', 'notificaciones']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'config.seguridad.RechazaNulosMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'accounts.middleware.CambioDeClaveObligatorioMiddleware', 'accounts.middleware.SegundoFactorMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'auditoria.middleware.ContextoAuditoriaMiddleware', 'config.seguridad.CabecerasSeguridadMiddleware', 'axes.middleware.AxesMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'accounts.context_processors.roles', 'accounts.context_processors.tema']}}]
WSGI_APPLICATION = 'config.wsgi.application'
MOTOR_BD = os.environ.get('TICKETS_DB_MOTOR', 'sqlite').strip().lower()
if MOTOR_BD == 'postgres':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ.get('TICKETS_PG_NOMBRE', 'tickets'), 'USER': os.environ.get('TICKETS_PG_USUARIO', 'tickets_app'), 'PASSWORD': os.environ.get('TICKETS_PG_CLAVE', ''), 'HOST': os.environ.get('TICKETS_PG_HOST', '127.0.0.1'), 'PORT': os.environ.get('TICKETS_PG_PUERTO', '5432'), 'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True, 'OPTIONS': {'connect_timeout': 10}}}
    if not PRUEBAS and (not DEBUG) and (not DATABASES['default']['PASSWORD']):
        raise ImproperlyConfigured('Falta TICKETS_PG_CLAVE (la contraseña del usuario de la base de datos PostgreSQL).')
elif MOTOR_BD == 'sqlite':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('TICKETS_DB', BASE_DIR / 'db.sqlite3'), 'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}}
else:
    raise ImproperlyConfigured('TICKETS_DB_MOTOR debe ser: sqlite o postgres.')
AUTH_USER_MODEL = 'accounts.Usuario'
AUTHENTICATION_BACKENDS = ['axes.backends.AxesBackend', 'django.contrib.auth.backends.ModelBackend']
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'inicio'
LOGOUT_REDIRECT_URL = 'accounts:login'
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}, {'NAME': 'accounts.validators.ContrasenaSegura'}]
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
SEGUNDO_FACTOR = env_bool('TICKETS_2FA', False)
DIAS_EQUIPO_RECORDADO = 30
TOTP_INTENTOS = 5
TOTP_BLOQUEO_MINUTOS = 15
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ['username', 'ip_address']
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = 'bloqueado.html'
AXES_ENABLED = not PRUEBAS
TICKETS_PROXY_CONFIABLE = os.environ.get('TICKETS_PROXY_CONFIABLE', '')
if TICKETS_PROXY_CONFIABLE:
    AXES_IPWARE_PROXY_COUNT = 1
    AXES_IPWARE_META_PRECEDENCE_ORDER = ['HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR']
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SLA_HORAS_POR_DEFECTO = {'CRITICA': 4, 'ALTA': 8, 'MEDIA': 24, 'BAJA': 72}
DIAS_AUTOCIERRE = 3
AUDITORIA_RETENCION_MINIMA_DIAS = 365
CORREO_MODO = os.environ.get('TICKETS_CORREO', 'desactivado').strip().lower()
if CORREO_MODO not in ('desactivado', 'smtp', 'graph'):
    raise ImproperlyConfigured('TICKETS_CORREO debe ser: desactivado, smtp o graph.')
URL_BASE = os.environ.get('TICKETS_URL_BASE', 'http://localhost:8000').rstrip('/')
CORREO_REMITENTE = os.environ.get('TICKETS_CORREO_REMITENTE', 'tickets@localhost')
CORREO_NOMBRE = os.environ.get('TICKETS_CORREO_NOMBRE', NOMBRE_SISTEMA)
EMAIL_HOST = os.environ.get('TICKETS_SMTP_HOST', '')
EMAIL_PORT = int(os.environ.get('TICKETS_SMTP_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('TICKETS_SMTP_USUARIO', '')
EMAIL_HOST_PASSWORD = os.environ.get('TICKETS_SMTP_CLAVE', '')
EMAIL_USE_TLS = env_bool('TICKETS_SMTP_TLS', True)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = f'{CORREO_NOMBRE} <{CORREO_REMITENTE}>'
GRAPH_TENANT = os.environ.get('TICKETS_GRAPH_TENANT', '')
GRAPH_CLIENT_ID = os.environ.get('TICKETS_GRAPH_CLIENT_ID', '')
GRAPH_CLIENT_SECRET = os.environ.get('TICKETS_GRAPH_CLIENT_SECRET', '')
if CORREO_MODO == 'graph' and (not PRUEBAS) and (not all((GRAPH_TENANT, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET))):
    raise ImproperlyConfigured('Modo graph: faltan TICKETS_GRAPH_TENANT, TICKETS_GRAPH_CLIENT_ID o TICKETS_GRAPH_CLIENT_SECRET.')
if CORREO_MODO == 'smtp' and (not PRUEBAS) and (not EMAIL_HOST):
    raise ImproperlyConfigured('Modo smtp: falta TICKETS_SMTP_HOST.')
SLA_AVISO_HORAS = 2
HORA_RECORDATORIO = 8
DIAS_MAX_REPROGRAMACION = 90
NOTIF_MAX_INTENTOS = 5
NOTIF_RETENCION_DIAS = 90
LANGUAGE_CODE = 'es'
TIME_ZONE = os.environ.get('TICKETS_TZ', 'America/Bogota')
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage' if DEBUG or PRUEBAS else 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
WHITENOISE_MANIFEST_STRICT = False
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'
MAX_ADJUNTO_MB = 10
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
(BASE_DIR / 'logs').mkdir(exist_ok=True)
LOGGING = {'version': 1, 'disable_existing_loggers': False, 'formatters': {'simple': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'}}, 'handlers': {'archivo': {'class': 'logging.FileHandler', 'filename': BASE_DIR / 'logs' / 'tickets.log', 'formatter': 'simple', 'encoding': 'utf-8'}, 'consola': {'class': 'logging.StreamHandler', 'formatter': 'simple'}} if not PRUEBAS else {'archivo': {'class': 'logging.NullHandler'}, 'consola': {'class': 'logging.NullHandler'}}, 'loggers': {'tickets': {'handlers': ['archivo', 'consola'], 'level': 'INFO'}, 'accounts': {'handlers': ['archivo', 'consola'], 'level': 'INFO'}, 'auditoria': {'handlers': ['archivo', 'consola'], 'level': 'INFO'}, 'notificaciones': {'handlers': ['archivo', 'consola'], 'level': 'INFO'}}}
SECURE_REDIRECT_EXEMPT = ['^salud/$']
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 20
FILE_UPLOAD_PERMISSIONS = 416
if not DEBUG:
    _https = env_bool('TICKETS_HTTPS', False)
    SESSION_COOKIE_SECURE = _https
    CSRF_COOKIE_SECURE = _https
    SECURE_SSL_REDIRECT = _https
    SECURE_HSTS_SECONDS = int(os.environ.get('TICKETS_HSTS', '3600')) if _https else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _https
