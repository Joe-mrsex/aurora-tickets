import csv
import os
import re
import stat
import unicodedata
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from accounts.claves import generar_clave_temporal
from auditoria.servicios import Modulo, registrar
from notificaciones.servicios import silencio
Usuario = get_user_model()
NOMBRE_VALIDO = re.compile('^[A-Za-z0-9._-]{3,150}$')
CEDULA_VALIDA = re.compile('^[A-Za-z0-9]{6,20}$')
PARTICULAS = {'de', 'del', 'la', 'las', 'los', 'san', 'santa', 'y'}
COLUMNAS = ('nombre', 'apellido', 'cedula', 'usuario', 'correo', 'departamento', 'cargo', 'rol')

def _letras(texto):
    sin_tildes = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    return re.sub('[^a-z0-9]', '', sin_tildes.lower())

def usuario_desde_nombre(nombre, apellido):
    nombres = [p for p in re.split('\\s+', (nombre or '').strip()) if p]
    palabras = [p for p in re.split('\\s+', (apellido or '').strip()) if p]
    if not nombres or not palabras:
        return ''
    primer_apellido = []
    for palabra in palabras:
        primer_apellido.append(palabra)
        if _letras(palabra) not in PARTICULAS:
            break
    return _letras(nombres[0])[:1] + _letras(''.join(primer_apellido))

class Command(BaseCommand):
    help = 'Crea cuentas desde un CSV; cada persona cambia su contraseña temporal en su primer ingreso.'

    def add_arguments(self, parser):
        parser.add_argument('archivo', help='CSV con las columnas: ' + ', '.join(COLUMNAS))
        parser.add_argument('--salida', default='credenciales_iniciales.csv', help='Archivo con los usuarios (y las contraseñas, si son aleatorias)')
        parser.add_argument('--clave-cedula', action='store_true', help='La contraseña temporal de cada persona es su cédula (columna «cedula»)')
        parser.add_argument('--probar', action='store_true', help='Solo revisa el archivo y muestra lo que haría, sin crear nada')

    def handle(self, *args, **opciones):
        filas = self._leer(opciones['archivo'])
        con_cedula = opciones['clave_cedula']
        crear, errores, existentes = ([], [], [])
        ocupados = {u.lower() for u in Usuario.objects.values_list('username', flat=True)}
        escritos = set()
        for numero, fila in enumerate(filas, start=2):
            fila = {(k or '').strip().lower(): (v or '').strip() for k, v in fila.items() if k}
            usuario = fila.get('usuario') or usuario_desde_nombre(fila.get('nombre'), fila.get('apellido'))
            automatico = not fila.get('usuario')
            rol = (fila.get('rol') or 'SOLICITANTE').upper()
            cedula = re.sub('[\\s.-]', '', fila.get('cedula', ''))
            if not usuario:
                errores.append(f'fila {numero}: no hay «usuario» ni «nombre» y «apellido» para formarlo')
                continue
            if not NOMBRE_VALIDO.match(usuario):
                errores.append(f'fila {numero}: usuario «{usuario}» no válido (3 a 150 letras o números, sin espacios)')
                continue
            if rol not in Usuario.Rol.values:
                errores.append(f'fila {numero}: rol «{rol}» no válido (usa SOLICITANTE, TECNICO o JEFE)')
                continue
            if fila.get('correo') and (not self._correo_valido(fila['correo'])):
                errores.append(f"fila {numero}: correo «{fila['correo']}» no válido")
                continue
            if con_cedula and (not CEDULA_VALIDA.match(cedula)):
                errores.append(f"fila {numero}: cédula «{fila.get('cedula', '')}» no válida (6 a 20 letras o números)")
                continue
            if not automatico:
                if usuario.lower() in escritos:
                    errores.append(f'fila {numero}: el usuario «{usuario}» está repetido en el archivo')
                    continue
                escritos.add(usuario.lower())
                if usuario.lower() in ocupados:
                    existentes.append(usuario)
                    continue
            if automatico:
                base, n = (usuario, 1)
                while usuario.lower() in ocupados:
                    n += 1
                    usuario = f'{base}{n}'
            ocupados.add(usuario.lower())
            crear.append((usuario, rol, cedula, fila))
        for e in errores:
            self.stdout.write(self.style.ERROR(e))
        if errores:
            raise CommandError(f'Hay {len(errores)} error(es): no se creó nada. Corrige el archivo y vuelve a ejecutar.')
        if opciones['probar']:
            for usuario, _rol, _cedula, fila in crear[:15]:
                self.stdout.write(f"  {usuario:<22} {fila.get('nombre', '')} {fila.get('apellido', '')}".rstrip())
            if len(crear) > 15:
                self.stdout.write(f'  ... y {len(crear) - 15} más')
            self.stdout.write(f'Revisado: se crearían {len(crear)} cuenta(s); {len(existentes)} ya existen.')
            return
        creados = []
        with silencio():
            for usuario, rol, cedula, fila in crear:
                temporal = cedula if con_cedula else generar_clave_temporal()
                cuenta = Usuario(username=usuario, first_name=fila.get('nombre', '')[:150], last_name=fila.get('apellido', '')[:150], email=fila.get('correo', ''), departamento=fila.get('departamento', '')[:100], cargo=fila.get('cargo', '')[:100], rol=rol, debe_cambiar_clave=True)
                cuenta.set_password(temporal)
                cuenta.save()
                creados.append((usuario, f'{cuenta.first_name} {cuenta.last_name}'.strip(), 'su cédula' if con_cedula else temporal))
            if creados:
                registrar(Modulo.USUARIOS, 'IMPORTAR', referencia=f'{len(creados)} cuentas', detalle=f'Se importaron {len(creados)} cuentas desde un archivo; todas deben cambiar su contraseña al entrar', usuario_nombre='Importación')
        salida = opciones['salida']
        if creados:
            with open(salida, 'w', newline='', encoding='utf-8-sig') as f:
                escritor = csv.writer(f)
                escritor.writerow(['usuario', 'nombre', 'contrasena_temporal'])
                escritor.writerows(creados)
            try:
                os.chmod(salida, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        self.stdout.write(self.style.SUCCESS(f'Cuentas creadas: {len(creados)}. Ya existían (no se tocaron): {len(existentes)}.'))
        if creados:
            if con_cedula:
                self.stdout.write(f'Los usuarios están en «{salida}». La contraseña temporal de cada persona es su cédula; la cambiará al entrar.')
            else:
                self.stdout.write(f'Las contraseñas temporales están en «{salida}». Entrégalas una a una y BORRA ese archivo cuando termines.')

    def _leer(self, archivo):
        try:
            with open(archivo, newline='', encoding='utf-8-sig') as f:
                muestra = f.read(4096)
                f.seek(0)
                try:
                    dialecto = csv.Sniffer().sniff(muestra, delimiters=',;\t')
                except csv.Error:
                    dialecto = csv.excel
                filas = list(csv.DictReader(f, dialect=dialecto))
        except (OSError, csv.Error, UnicodeDecodeError) as error:
            raise CommandError(f'No se pudo leer el archivo: {error}') from None
        if not filas:
            raise CommandError('El archivo está vacío.')
        titulos = {(t or '').strip().lower() for t in filas[0]}
        if 'usuario' not in titulos and (not {'nombre', 'apellido'} <= titulos):
            raise CommandError('Faltan columnas: se necesita «usuario» o bien «nombre» y «apellido» (la primera fila lleva los títulos).')
        return filas

    @staticmethod
    def _correo_valido(texto):
        try:
            validate_email(texto)
            return True
        except ValidationError:
            return False
