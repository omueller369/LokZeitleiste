"""Build the shared web/backend/Android catalogue from reviewed translations."""
import csv
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'backend/lokzeitleiste/locales/translations.tsv'
rows=list(csv.reader(source.open(encoding='utf-8'),delimiter='|'))
result={language:{} for language in rows[0]}
for number,row in enumerate(rows[1:],2):
    if len(row)!=7 or any(not value for value in row):
        raise ValueError(f'Incomplete translation row {number}')
    if row[0] in result['de']:
        raise ValueError(f'Duplicate key in row {number}: {row[0]}')
    for language,value in zip(rows[0],row):result[language][row[0]]=value
text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
for destination in [root/'backend/lokzeitleiste/locales/catalog.json',root/'app/src/main/assets/catalog.json']:
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text,encoding='utf-8')
print(f'{len(result["de"])} complete entries × {len(result)} languages; Android and backend synchronized.')
