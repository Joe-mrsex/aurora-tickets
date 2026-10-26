"""Filtros de formato para las plantillas."""
from django import template
from django.utils.timesince import timesince

register = template.Library()


@register.filter
def hace(valor):
    """
    Tiempo transcurrido desde una fecha, solo con la unidad mayor: «3 semanas» en lugar de «3 semanas, 2 días».
    Ocupa menos sitio en las tablas. Si el valor no es una fecha, devuelve un texto vacío (no rompe la página).
    """
    try:
        return timesince(valor).split(",")[0].strip()
    except (AttributeError, TypeError, ValueError):
        return ""
