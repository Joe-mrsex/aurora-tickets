"""
Temas visuales del sistema.

SEGURIDAD: esta es la ÚNICA lista de temas válidos. El servidor solo acepta una clave que esté aquí; cualquier otro
valor (de un formulario, de una cookie, de la base de datos) se ignora y se usa el tema por defecto. Así el nombre del
tema nunca puede usarse para inyectar contenido en la página.

Cada tema es un bloque de variables CSS en static/css/temas.css con el mismo nombre de clave.
Para añadir un tema: 1) una entrada aquí, 2) su bloque en temas.css, 3) (si usa otra tipografía) su fuente en fuentes.css.
"""
from collections import OrderedDict

TEMA_POR_DEFECTO = "titanio"

# clave -> datos para el selector (los colores son solo de la vista previa; el tema real vive en temas.css)
TEMAS = OrderedDict([
    ("titanio", {"nombre": "Titanio", "descripcion": "Claro, gris acero y azul hielo",
                 "fondo": "#E9ECEF", "primario": "#0369A1", "acento": "#EA580C"}),
    ("grafito", {"nombre": "Grafito", "descripcion": "Oscuro minimalista, naranja brasa",
                 "fondo": "#121214", "primario": "#FF5A36", "acento": "#A1A1AA"}),
    ("neon", {"nombre": "Neón", "descripcion": "Oscuro cyberpunk, cian eléctrico",
              "fondo": "#0B0F1A", "primario": "#22D3EE", "acento": "#FF9F43"}),
    ("tinta", {"nombre": "Tinta", "descripcion": "Claro tono papel, azul tinta",
               "fondo": "#FAF7F2", "primario": "#D9381E", "acento": "#2F4B9A"}),
])

CHOICES = [(clave, datos["nombre"]) for clave, datos in TEMAS.items()]


def tema_valido(valor):
    """Devuelve la clave si es un tema conocido; si no, el tema por defecto."""
    return valor if isinstance(valor, str) and valor in TEMAS else TEMA_POR_DEFECTO


def lista_para_selector():
    return [dict(clave=clave, **datos) for clave, datos in TEMAS.items()]
