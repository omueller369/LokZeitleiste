"""Check the shared source catalogue and the actual HTML shipped in an APK."""
import argparse
import fnmatch
import json
import re
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'backend/lokzeitleiste/static'
TOKEN = re.compile(r'\{\{([a-z][a-z0-9_]*\.text_[a-f0-9]{12})\}\}')
ANY_TOKEN = re.compile(r'\{\{[a-z][a-z0-9_]*\.[a-z0-9_]+\}\}')


def source_pages():
    build = (ROOT / 'app/build.gradle.kts').read_text()
    includes = re.search(r'include\(([\s\S]*?)\)\s*\n', build)[1]
    patterns = re.findall(r'"([^"]+)"', includes)
    return [page for page in STATIC.glob('*.html')
            if any(fnmatch.fnmatchcase(page.name, pattern) for pattern in patterns)]


def check(apk=None):
    messages = json.loads((STATIC.parent / 'locales/keys.json').read_text())
    pages = source_pages()
    assert len(pages) >= 8, 'Packaged portal HTML selection is incomplete'
    archive = ZipFile(apk) if apk else None
    try:
        for page in pages:
            source = page.read_text()
            for key in TOKEN.findall(source):
                for lang in ('de', 'pl', 'en'):
                    assert messages[lang].get(key), f'{page.name}: missing {lang} key {key}'
            rendered = TOKEN.sub(lambda match: messages['de'][match[1]], source)
            assert not ANY_TOKEN.search(rendered), f'{page.name}: unsupported source placeholder'
            if archive:
                actual = archive.read('assets/tf-portal/' + page.name).decode('utf-8')
                assert not ANY_TOKEN.search(actual), f'{page.name}: unresolved placeholder in APK'
                assert actual.splitlines() == rendered.splitlines(), f'{page.name}: outdated or incorrectly rendered APK asset'
        if archive:
            assert archive.read('assets/tf-portal/messages.js') == (STATIC/'messages.js').read_bytes(), 'Outdated APK language bundle'
            assert archive.read('assets/catalog.json') == (ROOT/'app/src/main/assets/catalog.json').read_bytes(), 'Outdated native language catalogue'
    finally:
        if archive:
            archive.close()
    print(f'Android translations: {len(pages)} shared HTML pages, DE/PL/EN keys' +
          (', resolved APK templates and current language bundles' if apk else '') + ': PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apk', type=Path)
    args = parser.parse_args()
    check(args.apk)
