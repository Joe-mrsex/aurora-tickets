import hashlib
from datetime import UTC

from django.conf import settings
from django.db import connection, models, transaction
from django.utils import timezone

CANDADO_CADENA = 7421903518

class RegistroAuditoria(models.Model):
    """
    Una fila de la matriz de auditoría. Se crea automáticamente cada vez que
    alguien hace algo relevante en el sistema (ver auditoria/servicios.py).

    Características pensadas para auditorías:
      * Inmutable: no se puede editar ni borrar desde el sistema ni desde /admin.
      * Encadenado con hash (como una mini "blockchain"): cada registro incluye
        el hash del anterior. Si alguien modificara la base de datos a mano, el
        comando `verificar_auditoria` detecta dónde se rompió la cadena.
      * Guarda el nombre del usuario "congelado" (aunque luego se borre la cuenta).
    """

    class Modulo(models.TextChoices):
        ACCESO = "ACCESO", "Acceso al sistema"
        TICKETS = "TICKETS", "Tickets"
        BITACORA = "BITACORA", "Bitácora de actividades"
        INVENTARIO = "INVENTARIO", "Inventario de equipos"
        USUARIOS = "USUARIOS", "Usuarios"
        CONFIGURACION = "CONFIGURACION", "Configuración"
        AUDITORIA = "AUDITORIA", "Auditoría"

    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    usuario_nombre = models.CharField(max_length=200)
    usuario_rol = models.CharField(max_length=30, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    modulo = models.CharField(max_length=15, choices=Modulo.choices, db_index=True)
    accion = models.CharField(max_length=40, db_index=True)
    objeto_tipo = models.CharField(max_length=40, blank=True)
    objeto_id = models.CharField(max_length=40, blank=True)
    referencia = models.CharField("Referencia", max_length=120, blank=True, db_index=True)
    detalle = models.TextField(blank=True)
    hash_anterior = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"

    def __str__(self):
        return f"#{self.pk} {self.fecha:%Y-%m-%d %H:%M} {self.usuario_nombre} {self.accion} {self.referencia}"

    # -- Integridad -------------------------------------------------------- #
    def calcular_hash(self):
        # isoformat(timespec="microseconds") para que sea estable entre SQLite y memoria
        contenido = "|".join(
            [
                self.hash_anterior,
                self.fecha.astimezone(UTC).isoformat(timespec="microseconds"),
                self.usuario_nombre,
                self.usuario_rol,
                self.ip or "",
                self.modulo,
                self.accion,
                self.objeto_tipo,
                self.objeto_id,
                self.referencia,
                self.detalle,
            ]
        )
        return hashlib.sha256(contenido.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError("Los registros de auditoría son inmutables y no se pueden modificar.")
        # Leer el último eslabón y escribir el nuevo debe ser UNA sola operación: si dos registros se crearan a la vez
        # (dos inicios de sesión fallidos en el mismo instante) ambos tomarían el mismo «anterior» y la cadena parecería rota.
        # En SQLite la transacción toma el candado de escritura desde el principio (transaction_mode IMMEDIATE); en PostgreSQL se toma
        # un candado de aviso (advisory) que se suelta solo al terminar la transacción: los registros se encadenan de uno en uno.
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CANDADO_CADENA])
            ultimo = RegistroAuditoria.objects.order_by("-id").first()
            self.hash_anterior = ultimo.hash if ultimo else ""
            self.hash = self.calcular_hash()
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Los registros de auditoría no se pueden eliminar.")
