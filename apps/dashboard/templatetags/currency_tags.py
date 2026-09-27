"""
Custom template filters for Indian Currency formatting (en-IN).
Formats monetary values using Indian numbering system (Lakhs, Crores):
Example: 336725.00 -> 3,36,725.00
"""

from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='inr')
def inr_format(value, show_decimals=True):
    """
    Formats a numeric value using the Indian numbering system (en-IN).
    336725.00 -> 3,36,725.00
    81075 -> 81,075.00
    """
    if value is None or value == "":
        return "0.00" if show_decimals else "0"

    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            val = Decimal(cleaned)
        else:
            val = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    is_negative = val < 0
    val = abs(val)

    parts = f"{val:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last3

    sign = "-" if is_negative else ""
    if show_decimals:
        return f"{sign}{formatted_int}.{decimal_part}"
    return f"{sign}{formatted_int}"


@register.filter(name='inr_curr')
def inr_curr(value, show_decimals=True):
    """Formats with the Rupee symbol: ₹3,36,725.00"""
    formatted = inr_format(value, show_decimals=show_decimals)
    if formatted.startswith("-"):
        return f"-₹{formatted[1:]}"
    return f"₹{formatted}"


from django.utils.safestring import mark_safe


@register.filter(name='inr_parts', is_safe=True)
def inr_parts(value):
    """
    Renders integer part and wraps decimals in smaller font with opacity:
    284326.50 -> 2,84,326<span class="text-[0.75em] font-semibold opacity-75">.50</span>
    """
    formatted = inr_format(value, show_decimals=True)
    if '.' in formatted:
        integer_part, decimal_part = formatted.rsplit('.', 1)
        return mark_safe(f'{integer_part}<span class="text-[0.75em] font-semibold opacity-75">.{decimal_part}</span>')
    return mark_safe(formatted)

