"""Exercise real notes UI, not a duplicate implementation, at desktop and phone widths."""
import argparse
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste'/'static'

MOCK=r"""
const records=new Map();let nextId=1,failSave=false;
window.fetch=async(url,options={})=>{
 const uri=new URL(url,'https://testserver'),parts=uri.pathname.split('/'),id=Number(parts.at(-1)),method=options.method||'GET',data=options.body?JSON.parse(options.body):null;
 let status=200,result;
 if(method==='GET')result=Number.isInteger(id)&&id>0?records.get(id):[...records.values()].reverse().map(({text,...note})=>note);
 else if(method==='POST'){if(failSave){status=503;result={detail:'Keine Verbindung. Bitte erneut versuchen.'};}else{result={...data,id:nextId++,revision:1,created_at:'2026-11-03T13:05:33Z',updated_at:'2026-11-03T13:05:33Z'};records.set(result.id,result);status=201;}}
 else if(method==='PUT'){const old=records.get(id);if(old.revision!==data.expected_revision){status=409;result={detail:'Die Notiz wurde inzwischen geändert.'};}else{result={...old,title:data.title,text:data.text,revision:old.revision+1};records.set(id,result);}}
 else if(method==='DELETE'){const old=records.get(id);if(old.revision!==Number(uri.searchParams.get('expected_revision'))){status=409;result={detail:'Die Notiz wurde inzwischen geändert.'};}else{records.delete(id);result={deleted:id};}}
 return {ok:status<400,status,json:async()=>structuredClone(result)};
};
"""
CHECKS=r"""
(async()=>{
 const assert=(condition,message)=>{if(!condition)throw Error(message);},tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 const wait=async test=>{for(let i=0;i<100;i++){if(test())return;await tick();}throw Error('UI did not finish');};
 await window.startTfNotes();
 const root=document.getElementById('notesWorkspace'),add=root.querySelector('button'),dialog=document.getElementById('tfNoteDialog'),deletion=document.getElementById('tfNoteDeleteDialog'),title=document.getElementById('noteTitle'),body=document.getElementById('noteText'),form=dialog.querySelector('form'),save=form.querySelector('button'),count=document.getElementById('noteRemaining');
 const click=button=>{button.focus();button.click();},input=(field,value)=>{field.value=value;field.dispatchEvent(new Event('input'));};
 const submit=()=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
 assert(!dialog.open,'No editor until Neu hinzufügen');click(add);assert(dialog.open&&!form.hidden,'New opens form');assert(count.textContent.startsWith('1000 / 1000'),'Countdown begins at 1000');
 input(title,'Mein Titel');input(body,'😀'.repeat(1000));assert(count.textContent.startsWith('0 / 1000')&&!save.disabled,'Unicode count equals server characters');
 input(body,'😀'.repeat(1001));assert(save.disabled&&count.textContent.startsWith('-1'),'Over limit cannot save');
 input(body,'<b>Persönlicher Text</b>\nZweite Zeile');failSave=true;submit();await wait(()=>!body.disabled);assert(dialog.querySelector('[role=alert]').textContent.includes('Keine Verbindung')&&body.value.includes('Zweite Zeile'),'Failed save preserves input');
 failSave=false;submit();await wait(()=>root.querySelectorAll('.tf-note-open').length===1&&!body.disabled);
 assert(form.hidden&&dialog.querySelector('.tf-note-text').textContent===body.value,'Saved note full read view');assert(!dialog.querySelector('.tf-note-text b'),'Content rendered as text');
 assert(root.querySelector('time').textContent==='03.11.26 14:05','Exact dd.mm.yy HH:MM Europe/Berlin');
 click(dialog.querySelector('article button'));input(title,'Geändert');input(body,'Neuer Text');submit();await wait(()=>root.querySelector('.tf-note-open strong').textContent==='Geändert'&&!body.disabled);
 assert(root.querySelector('time').textContent==='03.11.26 14:05','Editing preserves creation timestamp');
 click(dialog.querySelector('.tf-notes-heading button'));await tick();
 click(root.querySelector('.tf-note-open'));await wait(()=>dialog.open&&!body.disabled);assert(dialog.querySelector('.tf-note-text').textContent==='Neuer Text','Click list loads whole note');click(dialog.querySelector('.tf-notes-heading button'));await tick();
 const trash=root.querySelector('.tf-note-trash');click(trash);assert(deletion.open&&records.size===1,'Trash first asks confirmation');click(deletion.querySelectorAll('button')[1]);await tick();assert(!deletion.open&&records.size===1,'Cancel keeps note');
 click(trash);click(deletion.querySelector('button'));await wait(()=>!deletion.open&&!root.querySelector('.tf-note-open'));assert(records.size===0,'Confirm deletes row and whole text');
 // Leave a real readable note for the screenshot.
 click(add);input(title,'Hinweis für morgen');input(body,'Unterlagen vor Dienstbeginn bereitlegen.\nRückruf bei der Disposition nicht vergessen.');submit();await wait(()=>root.querySelector('.tf-note-open')&&!body.disabled);
 const box=dialog.getBoundingClientRect();assert(box.left>=0&&box.right<=innerWidth,'Dialog fits viewport');assert(dialog.scrollHeight>=dialog.clientHeight,'Text remains scrollable');
 document.documentElement.dataset.notesStatus='pass';window.parent.postMessage({notesStatus:'pass'},'*');
})().catch(error=>{document.documentElement.dataset.notesStatus='fail';document.documentElement.dataset.notesMessage=error.stack;window.parent.postMessage({notesStatus:'fail',message:error.stack},'*');});
"""

def fixture():
    return '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+(STATIC/'tf-portal.css').read_text()+'</style></head><body><main><h1>Notizen</h1><div id="notesWorkspace"></div></main><script>'+(STATIC/'messages.js').read_text()+MOCK+(STATIC/'tf-notes.js').read_text()+CHECKS+'</script></body></html>'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(name) for name in ['google-chrome','google-chrome-stable','chromium','chromium-browser'] if shutil.which(name)),None)
    if not chrome:raise SystemExit('Chrome required for notes UI checks')
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/'notes.html').write_text(fixture())
        for width in [1280,375,320]:
            host=root/f'host-{width}.html'
            host.write_text(f'''<!doctype html><html data-notes-status="pending"><head><style>body{{margin:0}}iframe{{border:0;width:{width}px;height:1000px;display:block}}</style><script>addEventListener('message',event=>{{if(event.source!==document.querySelector('iframe')?.contentWindow)return;document.documentElement.dataset.notesStatus=event.data.notesStatus;document.documentElement.dataset.notesMessage=event.data.message||'';}});</script></head><body><iframe src="notes.html"></iframe></body></html>''')
            run=subprocess.run([chrome,'--headless=new','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--hide-scrollbars','--force-device-scale-factor=1','--window-size=1400,1000','--virtual-time-budget=10000',f'--user-data-dir={root/("profile-"+str(width))}',f'--screenshot={args.output_dir.resolve()/(str(width)+".png")}','--dump-dom',host.as_uri()],capture_output=True,text=True,timeout=60)
            (args.output_dir/f'{width}.html').write_text(run.stdout)
            passed=run.returncode==0 and 'data-notes-status="pass"' in run.stdout
            match=re.search(r'data-notes-message="([^"]*)"',run.stdout);message=html.unescape(match.group(1)) if match else 'Notes fixture did not finish'
            results.append(dict(width=width,passed=passed,message='' if passed else message));print(f'Notes UI {width}px: '+('PASS' if passed else 'FAIL '+message))
    (args.output_dir/'results.json').write_text(json.dumps(results,indent=2))
    if not all(row['passed'] for row in results):raise SystemExit(1)

if __name__=='__main__':main()
