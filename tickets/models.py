from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


# --------------------------------------------------------------------------- #
# Catálogos de configuración
# --------------------------------------------------------------------------- #
class Prioridad(models.TextChoices):
    CRITICA = "CRITICA", "Crítica"
    ALTA = "ALTA", "Alta"
    MEDIA = "MEDIA", "Media"
    BAJA = "BAJA", "Baja"


class ConfiguracionSLA(models.Model):
    """Tiempo máximo de atención (en horas) para cada prioridad. Editable en /admin."""

    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, unique=True)
    horas = models.PositiveIntegerField(help_text="Horas máximas para resolver un ticket de esta prioridad")

    class Meta:
        verbose_name = "configuración SLA"
        verbose_name_plural = "configuración SLA"

    def __str__(self):
        return f"{self.get_prioridad_display()}: {self.horas} h"

    @classmethod
    def horas_para(cls, prioridad):
        registro = cls.objects.filter(prioridad=prioridad).first()
        if registro:
            return registro.horas
        return settings.SLA_HORAS_POR_DEFECTO.get(prioridad, 24)


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    """Inventario básico de equipos (laptops, computadoras, impresoras...)."""

    class Tipo(models.TextChoices):
        LAPTOP = "LAPTOP", "Laptop"
        ESCRITORIO = "ESCRITORIO", "Computadora de escritorio"
        IMPRESORA = "IMPRESORA", "Impresora / Multifuncional"
        MONITOR = "MONITOR", "Monitor"
        RED = "RED", "Equipo de red"
        SERVIDOR = "SERVIDOR", "Servidor"
        OTRO = "OTRO", "Otro"

    codigo = models.CharField("Código / placa de activo", max_length=40, unique=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.LAPTOP)
    marca = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=60, blank=True)
    serial = models.CharField("Número de serie", max_length=80, blank=True)
    asignado_a = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="equipos"
    )
    ubicacion = models.CharField("Ubicación / área", max_length=100, blank=True)
    observaciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["codigo"]

    def __str__(self):
        detalle = " ".join(p for p in (self.marca, self.modelo) if p)
        return f"{self.codigo} - {self.get_tipo_display()}" + (f" ({detalle})" if detalle else "")


# --------------------------------------------------------------------------- #
# Ticket
# --------------------------------------------------------------------------- #
class Estado(models.TextChoices):
    NUEVO = "NUEVO", "Nuevo"
    ASIGNADO = "ASIGNADO", "Asignado"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    PENDIENTE = "PENDIENTE", "Pendiente (esperando al usuario)"
    RESUELTO = "RESUELTO", "Resuelto"
    CERRADO = "CERRADO", "Cerrado"
    CANCELADO = "CANCELADO", "Cancelado"


ESTADOS_ABIERTOS = (Estado.NUEVO, Estado.ASIGNADO, Estado.EN_PROCESO, Estado.PENDIENTE)
ESTADOS_FINALES = (Estado.RESUELTO, Estado.CERRADO, Estado.CANCELADO)


class Ticket(models.Model):
    titulo = models.CharField("Asunto", max_length=150)
    descripcion = models.TextField("Descripción del problema")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets_creados")
    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets_asignados"
    )
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="tickets")
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.NUEVO, db_index=True)
    equipo = models.ForeignKey(
        Equipo, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets", verbose_name="Equipo afectado"
    )

    creado = models.DateTimeField(default=timezone.now, db_index=True)
    actualizado = models.DateTimeField(auto_now=True)
    fecha_limite = models.DateTimeField("Vence (SLA)", null=True, blank=True)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    fecha_primera_atencion = models.DateTimeField(null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    solucion = models.TextField("Solución aplicada", blank=True)

    # Reprogramación: el técnico pospone la atención para otro día y el reloj del SLA se detiene hasta esa fecha.
    reprogramado_para = models.DateField("Reprogramado para", null=True, blank=True)
    pausado_desde = models.DateTimeField("SLA en pausa desde", null=True, blank=True)
    sla_pausado_total = models.DurationField("Tiempo de SLA pausado (acumulado)", default=timedelta)
    reprogramaciones = models.PositiveSmallIntegerField("Veces reprogramado", default=0)

    class Meta:
        ordering = ["-creado"]
        indexes = [models.Index(fields=["estado", "prioridad"])]

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    # -- Identificación ----------------------------------------------------- #
    @property
    def codigo(self):
        """Código legible: TI-00042. Se calcula a partir del id, no se guarda."""
        return f"TI-{self.pk:05d}" if self.pk else "TI-(nuevo)"

    # -- SLA ---------------------------------------------------------------- #
    def calcular_fecha_limite(self):
        """Creación + horas del SLA + el tiempo que el reloj estuvo en pausa por reprogramaciones ya terminadas."""
        return self.creado + timedelta(hours=ConfiguracionSLA.horas_para(self.prioridad)) + self.sla_pausado_total

    def save(self, *args, **kwargs):
        if not self.fecha_limite:
            self.fecha_limite = self.calcular_fecha_limite()
        super().save(*args, **kwargs)

    @property
    def esta_abierto(self):
        return self.estado in ESTADOS_ABIERTOS

    @property
    def en_pausa(self):
        """True mientras el ticket está reprogramado: el reloj del SLA está detenido."""
        return self.esta_abierto and self.pausado_desde is not None

    @property
    def esta_vencido(self):
        """Abierto, con el reloj en marcha, y ya pasó su fecha límite (un ticket reprogramado NO vence)."""
        return (self.esta_abierto and not self.en_pausa and self.fecha_limite is not None
                and timezone.now() > self.fecha_limite)

    def cerrar_pausa(self, hasta=None):
        """
        Termina la pausa del SLA: el vencimiento se corre tanto como duró la pausa, de modo que el tiempo
        que estuvo reprogramado no cuenta contra el plazo. No guarda; quien llama debe hacer save().
        Devuelve lo que duró la pausa (timedelta) o None si no había.
        """
        if self.pausado_desde is None:
            return None
        hasta = hasta or timezone.now()
        duracion = max(hasta - self.pausado_desde, timedelta(0))
        self.fecha_limite = (self.fecha_limite or self.calcular_fecha_limite()) + duracion
        self.sla_pausado_total = self.sla_pausado_total + duracion
        self.pausado_desde = None
        self.reprogramado_para = None
        return duracion

    @property
    def cumplio_sla(self):
        """None si aún no se resuelve; True/False cuando ya se resolvió."""
        if not self.fecha_resolucion or not self.fecha_limite:
            return None
        return self.fecha_resolucion <= self.fecha_limite

    @property
    def horas_restantes(self):
        """Horas que quedan para el vencimiento. En pausa, es el tiempo que quedaba al reprogramar (congelado)."""
        if not self.esta_abierto or not self.fecha_limite:
            return None
        referencia = self.pausado_desde or timezone.now()
        return (self.fecha_limite - referencia).total_seconds() / 3600

    @property
    def tiempo_resolucion(self):
        """timedelta entre la creación y la resolución (None si no se resolvió)."""
        if self.fecha_resolucion:
            return self.fecha_resolucion - self.creado
        return None

    @property
    def clase_estado(self):
        """Nombre de clase CSS para pintar la etiqueta de estado."""
        return f"estado-{self.estado.lower()}"

    @property
    def clase_prioridad(self):
        return f"prioridad-{self.prioridad.lower()}"


class Comentario(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comentarios")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    texto = models.TextField()
    interno = models.BooleanField(
        "Nota interna de TI", default=False, help_text="Solo la ven los técnicos; el solicitante no."
    )
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["creado"]

    def __str__(self):
        return f"Comentario de {self.autor} en {self.ticket.codigo}"


def ruta_adjunto(instancia, nombre):
    return f"adjuntos/ticket_{instancia.ticket_id}/{timezone.now():%Y%m%d%H%M%S}_{Path(nombre).name}"


class Adjunto(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="adjuntos")
    comentario = models.ForeignKey(Comentario, null=True, blank=True, on_delete=models.CASCADE, related_name="adjuntos",
                                   help_text="Si el comentario es una nota interna, el archivo solo lo ve TI.")
    archivo = models.FileField(upload_to=ruta_adjunto)
    nombre_original = models.CharField(max_length=255)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["creado"]

    @property
    def es_interno(self):
        return bool(self.comentario_id and self.comentario.interno)

    def __str__(self):
        return self.nombre_original


class HistorialTicket(models.Model):
    """Línea de tiempo del ticket: cada cambio queda registrado (quién, cuándo, qué)."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="historial")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(default=timezone.now)
    accion = models.CharField(max_length=40)
    detalle = models.TextField(blank=True)
    visible_solicitante = models.BooleanField(default=True, help_text="False para notas internas de TI")

    class Meta:
        ordering = ["fecha", "id"]
        verbose_name_plural = "historial de tickets"

    def __str__(self):
        return f"{self.ticket.codigo} {self.accion}"
