from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from accounts.iconos_data import ICONOS
register = template.Library()

@register.simple_tag
def icono(nombre, clase=''):
    interior = ICONOS.get(nombre)
    if interior is None:
        return ''
    return mark_safe(f'<svg class="icono {escape(clase)}" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">{interior}</svg>')
