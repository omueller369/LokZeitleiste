"""Stable message keys. Canonical values keep persisted domain contracts unchanged."""
import json
import re
from functools import lru_cache
from pathlib import Path

LANGUAGES = ('de', 'pl', 'en')
TOKEN = re.compile(r'\{\{([a-z][a-z0-9_]*\.text_[a-f0-9]{12})\}\}')


@lru_cache
def messages():
    return json.loads((Path(__file__).parent / 'locales/keys.json').read_text())


def source(key):
    return messages()['de'][key]


def text(key, language='de', **parameters):
    value = messages().get(language, messages()['de'])[key]
    for name, replacement in parameters.items():
        value = value.replace('{' + name + '}', str(replacement))
    return value


def resolve_placeholders(value, language='de'):
    return TOKEN.sub(lambda match: text(match[1], language), value)
