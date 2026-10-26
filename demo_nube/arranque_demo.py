import os
import secrets
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ.setdefault('TICKETS_SECRET_KEY', secrets.token_urlsafe(50))
os.environ.setdefault('TICKETS_ALLOWED_HOSTS', '.onrender.com,localhost,127.0.0.1')
os.environ.setdefault('TICKETS_CSRF_ORIGINS', 'https://*.onrender.com')
os.environ.setdefault('TICKETS_PROXY_CONFIABLE', '*')
os.environ.setdefault('TICKETS_DB', os.path.join(tempfile.gettempdir(), 'demo.sqlite3'))
import django
django.setup()
from django.core.management import call_command
from waitress import serve
call_command('migrate', interactive=False, verbosity=0)
call_command('crear_datos_demo', forzar=True)
from config.wsgi import application
puerto = int(os.environ.get('PORT', '10000'))
print(f'Demostración en el puerto {puerto}')
serve(application, host='0.0.0.0', port=puerto, threads=8, trusted_proxy='*', trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'}, clear_untrusted_proxy_headers=True)
