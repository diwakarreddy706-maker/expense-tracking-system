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
