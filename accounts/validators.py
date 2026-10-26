"""
Política de contraseñas del sistema: al menos 10 caracteres, con mayúsculas, minúsculas, números y símbolos.
Se aplica en el cambio obligatorio del primer ingreso, en «Cambiar contraseña» y en /admin. Se suma a los validadores de Django
(no puede parecerse al usuario, ni ser una clave común, ni solo números).
"""
import re

from django.core.exceptions import ValidationError

LARGO_MINIMO = 10

REGLAS = (
    (r"[A-ZÁÉÍÓÚÑ]", "al menos una letra mayúscula"),
    (r"[a-záéíóúñ]", "al menos una letra minúscula"),
    (r"[0-9]", "al menos un número"),
    (r"[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ\s]", "al menos un símbolo (por ejemplo ! # $ % & * - _ . ?)"),
)

AYUDA = (f"Mínimo {LARGO_MINIMO} caracteres, con mayúsculas, minúsculas, números y símbolos. "
         "No puede parecerse a tu usuario ni ser una clave común.")


class ContrasenaSegura:
    """Exige mayúsculas, minúsculas, números y símbolos. Se puede usar en AUTH_PASSWORD_VALIDATORS."""

    def validate(self, password, user=None):
        faltan = [texto for patron, texto in REGLAS if not re.search(patron, password)]
        if faltan:
            raise ValidationError("La contraseña debe tener " + ", ".join(faltan) + ".", code="contrasena_insegura")

    def get_help_text(self):
        return AYUDA
