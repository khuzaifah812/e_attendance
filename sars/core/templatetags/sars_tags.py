from django import template
from ..icons import svg

register = template.Library()


@register.simple_tag
def icon(name, size=20):
    return svg(name, size)


@register.filter
def pct_class(p):
    try:
        p = float(p)
    except (TypeError, ValueError):
        return 'bad'
    return 'good' if p >= 75 else ('warn' if p >= 50 else 'bad')
