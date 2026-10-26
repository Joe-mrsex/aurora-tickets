from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from accounts import segundo_factor
from auditoria.servicios import Modulo, registrar

class Command(BaseCommand):
    help = 'Quita el segundo factor de una cuenta (o de todas con --todos): deberán activarlo de nuevo en su próximo ingreso.'

    def add_arguments(self, parser):
        parser.add_argument('usuario', nargs='?')
        parser.add_argument('--todos', action='store_true', help='Reinicia el segundo factor de TODAS las cuentas que lo tienen activo')

    def handle(self, *args, **opciones):
        Usuario = get_user_model()
        if opciones['todos']:
            if opciones['usuario']:
                raise CommandError('Usa un usuario o --todos, no los dos.')
            cuentas = list(Usuario.objects.filter(totp_activo=True))
            for cuenta in cuentas:
                segundo_factor.reiniciar(cuenta)
            registrar(Modulo.USUARIOS, 'REINICIAR_SEGUNDO_FACTOR', referencia='todos', usuario_nombre='Servidor', detalle=f'Se reinició el segundo factor de {len(cuentas)} cuenta(s) desde el servidor')
            self.stdout.write(self.style.SUCCESS(f'Segundo factor reiniciado en {len(cuentas)} cuenta(s).'))
            return
        if not opciones['usuario']:
            raise CommandError('Indica un usuario o usa --todos.')
        try:
            cuenta = Usuario.objects.get(username=opciones['usuario'])
        except Usuario.DoesNotExist:
            raise CommandError(f"No existe el usuario «{opciones['usuario']}».") from None
        segundo_factor.reiniciar(cuenta)
        registrar(Modulo.USUARIOS, 'REINICIAR_SEGUNDO_FACTOR', referencia=cuenta.username, usuario_nombre='Servidor', detalle=f'Se reinició el segundo factor de {cuenta.username} desde el servidor')
        self.stdout.write(self.style.SUCCESS(f'Segundo factor de {cuenta.username} reiniciado.'))
