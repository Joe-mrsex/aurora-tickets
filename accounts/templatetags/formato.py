from django import template
from django.utils.timesince import timesince
register = template.Library()

@register.filter
def hace(valor):
    try:
        return timesince(valor).split(',')[0].strip()
    except (AttributeError, TypeError, ValueError):
        return ''
