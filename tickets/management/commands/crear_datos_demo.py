import random
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts import segundo_factor
from bitacora.models import Actividad
from notificaciones.servicios import silencio
from tickets import services
from tickets.models import Categoria, Equipo, Prioridad, Ticket
PASSWORD = 'Demo-Tickets-2026'
Usuario = get_user_model()
USUARIOS = [('jefe.demo', 'Juan', 'Montenegro', 'JEFE', 'TICS'), ('tecnico1.demo', 'Freddy', 'Cumbicus', 'TECNICO', 'TICS'), ('tecnico2.demo', 'Danny', 'Olmedo', 'TECNICO', 'TICS'), ('usuario1.demo', 'María', 'Gómez', 'SOLICITANTE', 'Contabilidad'), ('usuario2.demo', 'Pedro', 'Ríos', 'SOLICITANTE', 'Recursos Humanos'), ('usuario3.demo', 'Lucía', 'Paredes', 'SOLICITANTE', 'Ventas')]
PROBLEMAS = [('No enciende mi laptop', 'Hardware'), ('Sin internet en mi escritorio', 'Red e Internet'), ('Outlook no sincroniza', 'Correo electrónico'), ('Olvidé mi contraseña de dominio', 'Cuentas y accesos'), ('La impresora del piso 2 no imprime', 'Impresoras'), ('Instalar Adobe Reader', 'Software'), ('Pantalla parpadea', 'Hardware'), ('Solicito monitor adicional', 'Solicitud de equipo o servicio'), ('El sistema interno da error 500', 'Sistemas internos'), ('Teclado con teclas dañadas', 'Hardware')]

class Command(BaseCommand):
    help = 'Carga usuarios, equipos y tickets de demostración.'

    def add_arguments(self, parser):
        parser.add_argument('--primer-ingreso', action='store_true', help='Deja las cuentas de ejemplo como recién creadas: deben elegir contraseña y activar el segundo factor (para probar ese recorrido)')
        parser.add_argument('--forzar', action='store_true', help='Permite ejecutarlo fuera del modo desarrollo (SOLO en un laboratorio: crea cuentas con una contraseña conocida)')

    def handle(self, *args, **opciones):
        if not settings.DEBUG and (not opciones['forzar']):
            raise CommandError('Este comando crea cuentas de ejemplo con una contraseña CONOCIDA (están escritas en el código) y es un riesgo de seguridad en un sistema real. Solo funciona en modo desarrollo (TICKETS_DEBUG=True). En un laboratorio puedes usar --forzar; en producción, no lo uses.')
        with silencio():
            self._crear(opciones['primer_ingreso'])

    def _crear(self, primer_ingreso=False):
        call_command('iniciar_sistema')
        usuarios = {}
        for username, nombre, apellido, rol, depto in USUARIOS:
            u, _ = Usuario.objects.get_or_create(username=username, defaults={'first_name': nombre, 'last_name': apellido, 'rol': rol, 'departamento': depto, 'email': f'{username}@ejemplo.local'})
            u.set_password(PASSWORD)
            if rol == 'JEFE':
                u.is_staff = u.is_superuser = True
            u.debe_cambiar_clave = primer_ingreso
            u.save()
            if primer_ingreso:
                segundo_factor.reiniciar(u)
            usuarios[username] = u
        solicitantes = [u for u in usuarios.values() if u.rol == 'SOLICITANTE']
        for i, s in enumerate(solicitantes, start=1):
            Equipo.objects.get_or_create(codigo=f'LAP-{i:03d}', defaults={'tipo': 'LAPTOP', 'marca': 'Dell', 'modelo': 'Latitude 5420', 'serial': f'SN{i}ABC', 'asignado_a': s, 'ubicacion': s.departamento})
        tecnicos = [usuarios['tecnico1.demo'], usuarios['tecnico2.demo']]
        random.seed(7)
        for n in range(24):
            titulo, cat = random.choice(PROBLEMAS)
            s = random.choice(solicitantes)
            t = services.crear_ticket(solicitante=s, titulo=titulo, descripcion=f'{titulo}. Ejemplo de descripción del problema #{n}.', categoria=Categoria.objects.get(nombre=cat), prioridad=random.choice([Prioridad.BAJA, Prioridad.MEDIA, Prioridad.ALTA]), equipo=s.equipos.first())
            atras = timedelta(days=random.randint(0, 29), hours=random.randint(0, 8))
            Ticket.objects.filter(pk=t.pk).update(creado=timezone.now() - atras, fecha_limite=timezone.now() - atras + timedelta(hours=24))
            t.refresh_from_db()
            destino = random.choice(['nuevo', 'asignado', 'proceso', 'resuelto', 'resuelto', 'cerrado'])
            tec = random.choice(tecnicos)
            if destino != 'nuevo':
                services.asignar(t, tec, usuarios['jefe.demo'])
            if destino in ('proceso', 'resuelto', 'cerrado'):
                services.tomar(t, tec)
            if destino in ('resuelto', 'cerrado'):
                services.resolver(t, 'Se revisó el equipo y se corrigió el problema (ejemplo).', tec, random.choice([15, 30, 45, 60]))
            if destino == 'cerrado':
                services.cerrar(t, tec)
            if destino in ('resuelto', 'cerrado'):
                resuelto = t.creado + timedelta(hours=random.randint(1, 40))
                Ticket.objects.filter(pk=t.pk).update(fecha_resolucion=resuelto, fecha_primera_atencion=t.creado + timedelta(minutes=random.randint(10, 180)), fecha_asignacion=t.creado + timedelta(minutes=5), fecha_cierre=resuelto + timedelta(hours=2) if destino == 'cerrado' else None)
        for dia in range(5):
            Actividad.objects.create(tecnico=random.choice(tecnicos), fecha=timezone.localdate() - timedelta(days=dia), tipo=random.choice([Actividad.Tipo.PREVENTIVO, Actividad.Tipo.RESPALDO, Actividad.Tipo.REDES]), titulo='Actividad de ejemplo de la bitácora', descripcion='Detalle de ejemplo.', duracion_minutos=random.choice([30, 60, 90]))
        self.stdout.write(self.style.SUCCESS(f'Datos demo creados. Contraseña de las cuentas *.demo: {PASSWORD}'))
