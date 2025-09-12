# care/templatetags/form_tags.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name="add_class")
def add_class(value, css):
    """
    Adiciona classes Tailwind ao campo.
    - Se for BoundField, usa .as_widget()
    - Se já vier renderizado como string, injeta o class="..."
    """
    # Tenta caminho normal (BoundField)
    try:
        return value.as_widget(attrs={"class": css})
    except AttributeError:
        pass

    # Aqui, value é string HTML já renderizada.
    html = str(value)

    # Se já tem class=, só prefixa as classes
    if ' class="' in html:
        return mark_safe(html.replace(' class="', f' class="{css} ', 1))

    # Caso não tenha class, injeta no 1º input/select/textarea
    for tag in ("input", "select", "textarea"):
        i = html.find(f"<{tag}")
        if i != -1:
            j = html.find(">", i)
            if j != -1:
                new_html = html[:j] + f' class="{css}"' + html[j:]
                return mark_safe(new_html)

    # Se não achou nenhuma tag, devolve como veio
    return mark_safe(html)