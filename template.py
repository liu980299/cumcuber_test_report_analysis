import django
from django.conf import settings
from django.template import Template,Context
from django.template.defaulttags import register



Templates = [
    {
        'BACKEND':'django.template.backends.django.DjangoTemplates'
    }
]

settings.configure(TEMPLATES=Templates)

django.setup()
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
