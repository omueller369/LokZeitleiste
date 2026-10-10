"""Shared seven-language catalogue for UI, API messages and generated outputs."""
import json
import re
from functools import lru_cache
from pathlib import Path
from contextvars import ContextVar
from .models import UserLocale

LANGUAGES = ('de','en','pl','ru','tr','ar','es')
request_language = ContextVar('request_language', default='de')


def language(value):
    code=(value or '').split(',')[0].split(';')[0].split('-')[0].strip().lower()
    return code if code in LANGUAGES else 'de'


@lru_cache
def catalog():
    return json.loads((Path(__file__).parent/'locales'/'catalog.json').read_text())


@lru_cache
def pattern():
    return re.compile(r'(?<!\w)('+ '|'.join(re.escape(key) for key in sorted(catalog()['de'],key=len,reverse=True)) +r')(?!\w)')


def translate(value, lang=None):
    lang=language(lang or request_language.get())
    text=str(value)
    if lang=='de':return text
    mapping=catalog()[lang]
    if text in mapping:return mapping[text]
    return pattern().sub(lambda match:mapping[match.group(0)],text)


def user_language(db,user_id):
    stored=db.get(UserLocale,user_id)
    return stored.language if stored else 'de'


def display(value,lang=None):
    translated=translate(value,lang)
    if language(lang or request_language.get())=='ar':
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(translated))
    return translated
