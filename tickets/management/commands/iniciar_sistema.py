from django.conf import settings
from django.core.management.base import BaseCommand

from tickets.models import Categoria, ConfiguracionSLA

CATEGORIAS = [
    ("Hardware", "Laptops, computadoras, monitores, periféricos"),
    ("Software", "Instalación, licencias, errores de programas"),
    ("Red e Internet", "Sin conexión, Wi-Fi, VPN, lentitud"),
    ("Correo electrónico", "Buzón, outlook, listas de distribución"),
    ("Cuentas y accesos", "Usuario de dominio, contraseñas, permisos"),
    ("Impresoras", "Impresión, escáner, tóner"),
    ("Sistemas internos", "Aplicaciones propias de la empresa"),
    ("Solicitud de equipo o servicio", "Equipos nuevos, cambios, altas y bajas"),
    ("Otros", "Lo que no encaje en las demás"),
]


class Command(BaseCommand):
    help = "Carga la configuración inicial (SLA y categorías). Es seguro ejecutarlo varias veces."

    def handle(self, *args, **opciones):
        for prioridad, horas in settings.SLA_HORAS_POR_DEFECTO.items():
            ConfiguracionSLA.objects.get_or_create(prioridad=prioridad, defaults={"horas": horas})
        for nombre, descripcion in CATEGORIAS:
            Categoria.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})
        self.stdout.write(self.style.SUCCESS("Configuración inicial lista (SLA y categorías)."))
