from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter(name="mul")
def mul(a, b):
    """Умножение, безопасно для Decimal/чисел, возвращает Decimal при возможности."""
    try:
        if isinstance(a, Decimal) or isinstance(b, Decimal):
            return (Decimal(a) * Decimal(b))
        return a * b
    except (InvalidOperation, Exception):
        try:
            return Decimal(str(a)) * Decimal(str(b))
        except Exception:
            return 0


@register.filter(name="get_item")
def get_item(mapping, key):
    try:
        if mapping is None:
            return None
        return mapping.get(key)
    except Exception:
        return None
