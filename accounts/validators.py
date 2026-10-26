import re
from django.core.exceptions import ValidationError
LARGO_MINIMO = 10
REGLAS = (('[A-ZÁÉÍÓÚÑ]', 'al menos una letra mayúscula'), ('[a-záéíóúñ]', 'al menos una letra minúscula'), ('[0-9]', 'al menos un número'), ('[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ\\s]', 'al menos un símbolo (por ejemplo ! # $ % & * - _ . ?)'))
AYUDA = f'Mínimo {LARGO_MINIMO} caracteres, con mayúsculas, minúsculas, números y símbolos. No puede parecerse a tu usuario ni ser una clave común.'

class ContrasenaSegura:

    def validate(self, password, user=None):
        faltan = [texto for patron, texto in REGLAS if not re.search(patron, password)]
        if faltan:
            raise ValidationError('La contraseña debe tener ' + ', '.join(faltan) + '.', code='contrasena_insegura')

    def get_help_text(self):
        return AYUDA
