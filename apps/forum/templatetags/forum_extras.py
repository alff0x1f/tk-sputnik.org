from django import template

register = template.Library()


@register.filter
def ru_pluralize(value, arg):
    """
    Russian three-form pluralization: arg is "form1,form2,form3"
    e.g. {{ count|ru_pluralize:"сообщение,сообщения,сообщений" }}
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
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
