from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from . import temas
from .cifrado import CampoCifrado


class Usuario(AbstractUser):
    """
    Usuario del sistema. Extiende el usuario estándar de Django con:
      - rol: define qué puede hacer dentro del sistema.
      - datos organizativos (departamento, cargo, teléfono).
      - debe_cambiar_clave: la persona entra con una contraseña temporal y debe elegir una propia antes de usar el sistema.
    """

    class Rol(models.TextChoices):
        SOLICITANTE = "SOLICITANTE", "Solicitante (personal)"
        TECNICO = "TECNICO", "Técnico de TI"
        JEFE = "JEFE", "Jefe de TI"

    rol = models.CharField(max_length=12, choices=Rol.choices, default=Rol.SOLICITANTE)
    departamento = models.CharField(max_length=100, blank=True)
    cargo = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    debe_cambiar_clave = models.BooleanField(
        "Debe cambiar la contraseña", default=False,
        help_text="Se marca sola al crear la cuenta o restablecer la contraseña; se desmarca cuando la persona elige la suya.")
    recibe_correos = models.BooleanField(
        "Recibe avisos por correo", default=True,
        help_text="Si se desmarca, el sistema no le envía notificaciones (necesita un correo en su perfil).")
    totp_secreto = CampoCifrado(max_length=255, blank=True, editable=False)
    totp_activo = models.BooleanField("Segundo factor activo", default=False, editable=False)
    totp_epoca = models.PositiveIntegerField(default=0, editable=False)
    totp_ultimo_paso = models.BigIntegerField(default=0, editable=False)
    totp_fallos = models.PositiveSmallIntegerField(default=0, editable=False)
    totp_bloqueado_hasta = models.DateTimeField(null=True, blank=True, editable=False)
    tema = models.CharField("Tema visual", max_length=12, choices=temas.CHOICES, default=temas.TEMA_POR_DEFECTO)

    class Meta:
        ordering = ["first_name", "last_name", "username"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    # -- Ayudas de rol (se usan en vistas y plantillas) ------------------- #
    @property
    def es_jefe(self):
        return self.rol == self.Rol.JEFE

    @property
    def es_tecnico(self):
        """Técnico o Jefe: cualquier persona del área de TI."""
        return self.rol in (self.Rol.TECNICO, self.Rol.JEFE)

    @classmethod
    def personal_ti(cls, solo_activos=True):
        """Técnicos y jefe: quienes pueden atender tickets. Es la única definición de «personal de TI» para las consultas."""
        personal = cls.objects.filter(rol__in=(cls.Rol.TECNICO, cls.Rol.JEFE))
        return personal.filter(is_active=True) if solo_activos else personal

    @property
    def nombre_completo(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return self.nombre_completo

    def save(self, *args, **kwargs):
        # Un superusuario siempre debe poder administrar: lo tratamos como Jefe.
        if self.is_superuser and self.rol == self.Rol.SOLICITANTE:
            self.rol = self.Rol.JEFE
        super().save(*args, **kwargs)


class CodigoRecuperacion(models.Model):
    """Códigos de un solo uso para entrar si se pierde el celular. En la base solo se guarda su huella, nunca el código."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codigos_recuperacion")
    huella = models.CharField(max_length=64)
    usado = models.BooleanField(default=False)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "código de recuperación"
        verbose_name_plural = "códigos de recuperación"
