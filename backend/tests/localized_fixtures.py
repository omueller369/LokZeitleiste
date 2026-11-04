"""Render default-language fixture markup without relying on a running server."""
import json
import re
from pathlib import Path
MESSAGES = json.loads((Path(__file__).parents[1] / 'lokzeitleiste/locales/keys.json').read_text())
def localize_html(value, language='de'):
    return re.sub(r'\{\{([a-z][a-z0-9_]*\.text_[a-f0-9]{12})\}\}', lambda m: MESSAGES[language][m[1]], value)
