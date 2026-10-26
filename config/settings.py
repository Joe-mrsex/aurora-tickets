"""
Configuración del Sistema de Tickets TICS.

Todo lo que cambia entre tu PC (pruebas) y el servidor de la empresa se lee de
variables de entorno, con valores seguros por defecto. La lista completa de variables está en docs/GUIA_MAESTRA.md (sección «Referencia»).
"""
import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


PRUEBAS = len(sys.argv) > 1 and sys.argv[1] == "test"  # manage.py test


def env_bool(nombre, defecto=False):
    return os.environ.get(nombre, str(defecto)).strip().lower() in ("1", "true", "si", "yes")


# --------------------------------------------------------------------------- #
# Seguridad
# --------------------------------------------------------------------------- #
# EN PRODUCCIÓN: definir TICKETS_SECRET_KEY con un valor largo y aleatorio y
# TICKETS_DEBUG=False.
# SEGURO POR DEFECTO: sin variables de entorno el sistema arranca en modo producción (DEBUG apagado).
# Para desarrollar en tu PC usa iniciar_desarrollo.bat, que activa TICKETS_DEBUG=True.
DEBUG = env_bool("TICKETS_DEBUG", False)

# Nombre con el que se presenta el sistema (barra, título de las pestañas, correos, aplicación del celular del segundo factor y app instalada)
NOMBRE_SISTEMA = os.environ.get("TICKETS_NOMBRE", "Aurora")
SUBTITULO_SISTEMA = os.environ.get("TICKETS_SUBTITULO", "Tickets TICS")
_CLAVE_DESARROLLO = "clave-solo-para-desarrollo-cambiar-en-produccion"
SECRET_KEY = os.environ.get("TICKETS_SECRET_KEY", _CLAVE_DESARROLLO)
if not DEBUG and not PRUEBAS and (SECRET_KEY == _CLAVE_DESARROLLO or len(SECRET_KEY) < 40 or SECRET_KEY.startswith("CAMBIAR")):
    raise ImproperlyConfigured(
        "Falta TICKETS_SECRET_KEY (mínimo 40 caracteres aleatorios). Genera una con: "
        "python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )
ALLOWED_HOSTS = [h for h in os.environ.get("TICKETS_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("TICKETS_CSRF_ORIGINS", "").split(",") if o]

# --------------------------------------------------------------------------- #
# Aplicaciones
# --------------------------------------------------------------------------- #
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",  # límite de intentos de inicio de sesión
    # Apps propias
    "accounts",
    "tickets",
    "bitacora",
    "auditoria",
    "dashboard",
    "notificaciones",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.seguridad.RechazaNulosMiddleware",  # un %00 en un parámetro daría error 500 en PostgreSQL
    "whitenoise.middleware.WhiteNoiseMiddleware",  # sirve los archivos estáticos (CSS) en producción
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.CambioDeClaveObligatorioMiddleware",  # quien tiene contraseña temporal solo puede cambiarla
    "accounts.middleware.SegundoFactorMiddleware",  # con TICKETS_2FA=True, nadie entra sin el código de su celular
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Guarda usuario e IP de la petición actual para que la auditoría los conozca
    "auditoria.middleware.ContextoAuditoriaMiddleware",
    "config.seguridad.CabecerasSeguridadMiddleware",  # CSP, Permissions-Policy, no-cache en páginas privadas
    "axes.middleware.AxesMiddleware",  # debe ir al final
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.roles",
                "accounts.context_processors.tema",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------- #
# Base de datos
# --------------------------------------------------------------------------- #
# TICKETS_DB_MOTOR=postgres usa PostgreSQL (lo que deja el instalador en producción); sin esa variable se usa SQLite (desarrollo y pruebas rápidas).
MOTOR_BD = os.environ.get("TICKETS_DB_MOTOR", "sqlite").strip().lower()
if MOTOR_BD == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("TICKETS_PG_NOMBRE", "tickets"),
            "USER": os.environ.get("TICKETS_PG_USUARIO", "tickets_app"),
            "PASSWORD": os.environ.get("TICKETS_PG_CLAVE", ""),
            "HOST": os.environ.get("TICKETS_PG_HOST", "127.0.0.1"),  # la base solo escucha en este mismo equipo
            "PORT": os.environ.get("TICKETS_PG_PUERTO", "5432"),
            "CONN_MAX_AGE": 60,  # reutiliza la conexión de cada hilo en vez de abrir una por petición
            "CONN_HEALTH_CHECKS": True,  # si el servicio de la base se reinició, descarta la conexión rota y abre otra
            "OPTIONS": {"connect_timeout": 10},
        }
    }
    if not PRUEBAS and not DEBUG and not DATABASES["default"]["PASSWORD"]:
        raise ImproperlyConfigured("Falta TICKETS_PG_CLAVE (la contraseña del usuario de la base de datos PostgreSQL).")
elif MOTOR_BD == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("TICKETS_DB", BASE_DIR / "db.sqlite3"),  # TICKETS_DB: otra ruta (pruebas, otro disco)
            # IMMEDIATE: cada transacción de escritura toma el candado desde el inicio, así dos técnicos que
            # "toman" el mismo ticket a la vez no pisan el cambio del otro (evita condiciones de carrera).
            "OPTIONS": {"timeout": 20, "transaction_mode": "IMMEDIATE"},
        }
    }
else:
    raise ImproperlyConfigured("TICKETS_DB_MOTOR debe ser: sqlite o postgres.")

# --------------------------------------------------------------------------- #
# Usuarios y autenticación
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.Usuario"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesBackend",  # 1º: bloquea tras demasiados intentos fallidos
    "django.contrib.auth.backends.ModelBackend",  # usuarios y contraseñas guardados en la base de datos
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "accounts:login"

# Contraseñas: 10 caracteres o más, con mayúsculas, minúsculas, números y símbolos (accounts/validators.py)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "accounts.validators.ContrasenaSegura"},
]

# Sesión: se cierra tras 8 horas de inactividad
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True   # JavaScript no puede leer la cookie de sesión
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Segundo factor: código de 6 dígitos que genera la aplicación del celular (Microsoft/Google Authenticator). Obligatorio para todos cuando está activo.
SEGUNDO_FACTOR = env_bool("TICKETS_2FA", False)
DIAS_EQUIPO_RECORDADO = 30   # «recordar este equipo»: durante este tiempo no se pide el código en ese navegador
TOTP_INTENTOS = 5            # códigos incorrectos seguidos antes de bloquear el segundo factor de esa persona
TOTP_BLOQUEO_MINUTOS = 15

# Límite de intentos de inicio de sesión (django-axes)
AXES_FAILURE_LIMIT = 5                                    # intentos fallidos permitidos
AXES_COOLOFF_TIME = timedelta(minutes=15)                 # duración del bloqueo
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]     # bloquea por usuario Y por IP (cada uno por separado)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "bloqueado.html"
AXES_ENABLED = not PRUEBAS  # en las pruebas se activa solo donde se prueba el bloqueo

# Detrás de un proxy inverso (Caddy/IIS/Nginx) la IP real llega en X-Forwarded-For. SOLO se confía en esa
# cabecera si el proxy está declarado: si no, cualquiera podría falsificar su IP en la auditoría y esquivar el bloqueo.
TICKETS_PROXY_CONFIABLE = os.environ.get("TICKETS_PROXY_CONFIABLE", "")  # ej: 127.0.0.1
if TICKETS_PROXY_CONFIABLE:
    AXES_IPWARE_PROXY_COUNT = 1
    AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------- #
# Reglas de negocio
# --------------------------------------------------------------------------- #
# Tiempo máximo de atención (SLA) por prioridad, en horas. Son valores
# iniciales: luego se pueden editar desde el panel /admin (Configuración SLA).
SLA_HORAS_POR_DEFECTO = {"CRITICA": 4, "ALTA": 8, "MEDIA": 24, "BAJA": 72}
# Días tras los cuales un ticket "Resuelto" se cierra solo si el usuario no responde
DIAS_AUTOCIERRE = 3
# La depuración de auditoría solo permite borrar registros con más de estos días de antigüedad
AUDITORIA_RETENCION_MINIMA_DIAS = 365

# --------------------------------------------------------------------------- #
# Notificaciones por correo
# --------------------------------------------------------------------------- #
# Modo de envío (variable TICKETS_CORREO):
#   desactivado  no se envía ni se guarda nada (valor por defecto)
#   smtp         servidor SMTP interno / relay (TICKETS_SMTP_*)
#   graph        Microsoft 365 mediante Microsoft Graph, con una aplicación registrada (TICKETS_GRAPH_*)
# Ver docs/GUIA_CORREO_M365.md.
CORREO_MODO = os.environ.get("TICKETS_CORREO", "desactivado").strip().lower()
if CORREO_MODO not in ("desactivado", "smtp", "graph"):
    raise ImproperlyConfigured("TICKETS_CORREO debe ser: desactivado, smtp o graph.")
URL_BASE = os.environ.get("TICKETS_URL_BASE", "http://localhost:8000").rstrip("/")  # para los enlaces de los correos
CORREO_REMITENTE = os.environ.get("TICKETS_CORREO_REMITENTE", "tickets@localhost")  # buzón desde el que se envía
CORREO_NOMBRE = os.environ.get("TICKETS_CORREO_NOMBRE", NOMBRE_SISTEMA)

# SMTP (modo smtp)
EMAIL_HOST = os.environ.get("TICKETS_SMTP_HOST", "")
EMAIL_PORT = int(os.environ.get("TICKETS_SMTP_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("TICKETS_SMTP_USUARIO", "")
EMAIL_HOST_PASSWORD = os.environ.get("TICKETS_SMTP_CLAVE", "")
EMAIL_USE_TLS = env_bool("TICKETS_SMTP_TLS", True)
EMAIL_TIMEOUT = 20
DEFAULT_FROM_EMAIL = f"{CORREO_NOMBRE} <{CORREO_REMITENTE}>"

# Microsoft Graph (modo graph)
GRAPH_TENANT = os.environ.get("TICKETS_GRAPH_TENANT", "")
GRAPH_CLIENT_ID = os.environ.get("TICKETS_GRAPH_CLIENT_ID", "")
GRAPH_CLIENT_SECRET = os.environ.get("TICKETS_GRAPH_CLIENT_SECRET", "")
if CORREO_MODO == "graph" and not PRUEBAS and not all((GRAPH_TENANT, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET)):
    raise ImproperlyConfigured("Modo graph: faltan TICKETS_GRAPH_TENANT, TICKETS_GRAPH_CLIENT_ID o TICKETS_GRAPH_CLIENT_SECRET.")
if CORREO_MODO == "smtp" and not PRUEBAS and not EMAIL_HOST:
    raise ImproperlyConfigured("Modo smtp: falta TICKETS_SMTP_HOST.")

# Reglas de los avisos y de la reprogramación
SLA_AVISO_HORAS = 2             # aviso al técnico cuando a un ticket le quedan estas horas de SLA
HORA_RECORDATORIO = 8           # hora local (0-23) a la que se envía el recordatorio de los tickets programados para hoy
DIAS_MAX_REPROGRAMACION = 90    # máximo de días hacia adelante al reprogramar
NOTIF_MAX_INTENTOS = 5          # intentos de envío antes de dar el aviso por fallido
NOTIF_RETENCION_DIAS = 90       # se borran de la bandeja los avisos enviados hace más de estos días

# --------------------------------------------------------------------------- #
# Idioma, zona horaria
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "es"
TIME_ZONE = os.environ.get("TICKETS_TZ", "America/Bogota")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Archivos estáticos y subidos
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# En producción cada archivo estático se publica con una huella en el nombre (estilos.3f2a1b.css) y comprimido: el
# navegador lo guarda «para siempre» y no vuelve a pedirlo hasta que cambie de verdad (una actualización cambia la huella).
# Lo prepara «collectstatic», que ya ejecutan el instalador, el actualizador y el arranque.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG or PRUEBAS
                    else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_MANIFEST_STRICT = False  # si faltara el índice de huellas, se sirve el archivo normal en vez de dar error

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
MAX_ADJUNTO_MB = 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Registro de errores en archivo
# --------------------------------------------------------------------------- #
(BASE_DIR / "logs").mkdir(exist_ok=True)  # la carpeta no viaja a GitHub: se crea sola si falta

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {
        "archivo": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "tickets.log",
            "formatter": "simple",
            "encoding": "utf-8",
        },
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
    } if not PRUEBAS else {
        # Las pruebas provocan errores a propósito (correo caído, servidor que no responde...): no deben ensuciar el registro real
        "archivo": {"class": "logging.NullHandler"},
        "consola": {"class": "logging.NullHandler"},
    },
    "loggers": {
        "tickets": {"handlers": ["archivo", "consola"], "level": "INFO"},
        "accounts": {"handlers": ["archivo", "consola"], "level": "INFO"},
        "auditoria": {"handlers": ["archivo", "consola"], "level": "INFO"},
        "notificaciones": {"handlers": ["archivo", "consola"], "level": "INFO"},
    },
}

# /salud/ se puede consultar por HTTP desde el propio servidor (el actualizador y el monitoreo no hablan HTTPS con el proxy)
SECURE_REDIRECT_EXEMPT = [r"^salud/$"]

# Cabeceras que Django añade siempre
X_FRAME_OPTIONS = "DENY"                     # nadie puede incrustar el sistema en otra página (clickjacking)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Límites contra subidas y peticiones abusivas
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024   # 15 MB de datos de formulario
DATA_UPLOAD_MAX_NUMBER_FIELDS = 200
DATA_UPLOAD_MAX_NUMBER_FILES = 20                 # Django 5.x+: máximo de archivos por petición
FILE_UPLOAD_PERMISSIONS = 0o640

if not DEBUG:
    _https = env_bool("TICKETS_HTTPS", False)
    SESSION_COOKIE_SECURE = _https
    CSRF_COOKIE_SECURE = _https
    SECURE_SSL_REDIRECT = _https
    SECURE_HSTS_SECONDS = int(os.environ.get("TICKETS_HSTS", "3600")) if _https else 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _https
