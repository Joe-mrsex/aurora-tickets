"""Arranque de la DEMOSTRACIÓN pública (Render u otro hospedaje gratuito): prepara la base, carga datos de ejemplo y sirve con Waitress.
Cada vez que el servicio se reinicia, los datos vuelven a empezar de cero. Nunca usarlo con datos reales."""
import os
import secrets
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("TICKETS_SECRET_KEY", secrets.token_urlsafe(50))
os.environ.setdefault("TICKETS_ALLOWED_HOSTS", ".onrender.com,localhost,127.0.0.1")
os.environ.setdefault("TICKETS_CSRF_ORIGINS", "https://*.onrender.com")
os.environ.setdefault("TICKETS_PROXY_CONFIABLE", "*")
os.environ.setdefault("TICKETS_DB", os.path.join(tempfile.gettempdir(), "demo.sqlite3"))

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from waitress import serve  # noqa: E402

call_command("migrate", interactive=False, verbosity=0)
call_command("crear_datos_demo", forzar=True)

from config.wsgi import application  # noqa: E402

puerto = int(os.environ.get("PORT", "10000"))
print(f"Demostración en el puerto {puerto}")
serve(application, host="0.0.0.0", port=puerto, threads=8, trusted_proxy="*", trusted_proxy_headers={"x-forwarded-for", "x-forwarded-proto"},
      clear_untrusted_proxy_headers=True)
