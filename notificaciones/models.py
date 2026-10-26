from django.conf import settings
from django.db import models
from django.utils import timezone

class Notificacion(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = ('PENDIENTE', 'Pendiente de enviar')
        ENVIANDO = ('ENVIANDO', 'Enviando')
        ENVIADO = ('ENVIADO', 'Enviado')
        FALLIDO = ('FALLIDO', 'Fallido (se agotaron los reintentos)')

    class Evento(models.TextChoices):
        ASIGNADO = ('ASIGNADO', 'Ticket asignado')
        ATENDIENDO = ('ATENDIENDO', 'Ya lo atienden')
        COMENTARIO = ('COMENTARIO', 'Comentario nuevo')
        NOTA_INTERNA = ('NOTA_INTERNA', 'Nota interna')
        ESTADO = ('ESTADO', 'Cambio de estado')
        RESUELTO = ('RESUELTO', 'Ticket resuelto')
        CERRADO = ('CERRADO', 'Ticket cerrado')
        REABIERTO = ('REABIERTO', 'Ticket reabierto')
        REPROGRAMADO = ('REPROGRAMADO', 'Ticket reprogramado')
        RECORDATORIO = ('RECORDATORIO', 'Recordatorio del día')
        SLA_POR_VENCER = ('SLA_POR_VENCER', 'SLA por vencer')
        SLA_VENCIDO = ('SLA_VENCIDO', 'SLA vencido')
        PRUEBA = ('PRUEBA', 'Correo de prueba')
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='notificaciones')
    email = models.EmailField('Correo de destino', max_length=254)
    ticket = models.ForeignKey('tickets.Ticket', null=True, blank=True, on_delete=models.CASCADE, related_name='notificaciones')
    evento = models.CharField(max_length=15, choices=Evento.choices, db_index=True)
    asunto = models.CharField(max_length=200)
    texto = models.TextField('Cuerpo (texto)')
    html = models.TextField('Cuerpo (HTML)', blank=True)
    clave = models.CharField(max_length=160, unique=True, null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    creada = models.DateTimeField(default=timezone.now, db_index=True)
    enviar_despues_de = models.DateTimeField(default=timezone.now, db_index=True)
    enviada = models.DateTimeField(null=True, blank=True)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'notificación'
        verbose_name_plural = 'notificaciones'
        indexes = [models.Index(fields=['estado', 'enviar_despues_de'])]

    def __str__(self):
        return f'#{self.pk} {self.evento} → {self.email} [{self.estado}]'
