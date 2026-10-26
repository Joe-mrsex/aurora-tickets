from django.conf import settings
from django.db import models
from django.utils import timezone

class Actividad(models.Model):

    class Tipo(models.TextChoices):
        CORRECTIVO = ('CORRECTIVO', 'Mantenimiento correctivo')
        PREVENTIVO = ('PREVENTIVO', 'Mantenimiento preventivo')
        INSTALACION = ('INSTALACION', 'Instalación / configuración')
        REDES = ('REDES', 'Redes y conectividad')
        RESPALDO = ('RESPALDO', 'Respaldos (backup)')
        SEGURIDAD = ('SEGURIDAD', 'Seguridad informática')
        CUENTAS = ('CUENTAS', 'Usuarios y cuentas (accesos, correo)')
        ASESORIA = ('ASESORIA', 'Asesoría / capacitación')
        COMPRAS = ('COMPRAS', 'Compras / proveedores')
        DOCUMENTACION = ('DOCUMENTACION', 'Documentación')
        TICKET = ('TICKET', 'Atención de ticket')
        OTRO = ('OTRO', 'Otro')
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='actividades')
    fecha = models.DateField(default=timezone.localdate, db_index=True)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.OTRO)
    titulo = models.CharField('Actividad', max_length=150)
    descripcion = models.TextField('Detalle de lo realizado', blank=True)
    duracion_minutos = models.PositiveIntegerField('Duración (minutos)', default=0)
    equipo = models.ForeignKey('tickets.Equipo', null=True, blank=True, on_delete=models.SET_NULL, related_name='actividades')
    ticket = models.ForeignKey('tickets.Ticket', null=True, blank=True, on_delete=models.SET_NULL, related_name='actividades')
    automatica = models.BooleanField(default=False, editable=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name_plural = 'actividades'

    def __str__(self):
        return f'{self.fecha} - {self.tecnico} - {self.titulo}'
