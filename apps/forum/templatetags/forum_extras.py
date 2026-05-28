from django import template
from django.utils.html import escape, mark_safe

from ..search import SNIPPET_START_SEL, SNIPPET_STOP_SEL

register = template.Library()


@register.filter
def ru_pluralize(value, arg):
    """
    Russian three-form pluralization: arg is "form1,form2,form3"
    e.g. {{ count|ru_pluralize:"сообщение,сообщения,сообщений" }}
    """
    try:
        n = int(value)
    except TypeError, ValueError:
        return ""
    forms = arg.split(",")
    if len(forms) != 3:
        return ""
    mod100 = n % 100
    mod10 = n % 10
    if 11 <= mod100 <= 19:
        return forms[2]
    if mod10 == 1:
        return forms[0]
    if 2 <= mod10 <= 4:
        return forms[1]
    return forms[2]


@register.filter(is_safe=True)
def highlight_snippet(value):
    """Convert SearchHeadline output with sentinels into HTML with <mark> tags.

    Escapes all HTML from the snippet first (XSS-safe), then substitutes
    the sentinel markers with <mark></mark>.
    """
    if not value:
        return mark_safe("")
    safe = escape(str(value))
    safe = safe.replace(SNIPPET_START_SEL, "<mark>")
    safe = safe.replace(SNIPPET_STOP_SEL, "</mark>")
    return mark_safe(safe)
