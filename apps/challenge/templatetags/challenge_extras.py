from django import template

register = template.Library()


@register.filter
def pluralize_ru(value, forms):
    """Russian plural: forms='form1,form2,form3' for 1/2-4/5+."""
    forms = forms.split(",")
    n = abs(int(value))
    n10 = n % 10
    n100 = n % 100
    if 11 <= n100 <= 19:
        return forms[2]
    if n10 == 1:
        return forms[0]
    if 2 <= n10 <= 4:
        return forms[1]
    return forms[2]
