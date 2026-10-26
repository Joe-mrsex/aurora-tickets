"""
Etiqueta de plantilla {% icono "ticket" %}: dibuja un icono de línea como SVG en línea.

- Va dentro de la página (no hace peticiones extra ni depende de internet) y hereda el color del texto.
- Solo se aceptan los nombres que existen en accounts/iconos_data.py; un nombre desconocido no rompe la página.
"""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from accounts.iconos_data import ICONOS

register = template.Library()


@register.simple_tag
def icono(nombre, clase=""):
    interior = ICONOS.get(nombre)
    if interior is None:
        return ""
    return mark_safe(
        f'<svg class="icono {escape(clase)}" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{interior}</svg>'
    )
