"""Real-browser help reader, responsive overlay and print-only-help checks."""
import argparse
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from pypdf import PdfReader

STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste'/'static'

def fixture():
    css=(STATIC/'tf-help.css').read_text()
    scripts='\n'.join((STATIC/name).read_text() for name in ['tf-help-content.js','tf-help.js','work-report-feedback.js'])
    checks=r'''
(async()=>{
 const assert=(condition,message)=>{if(!condition)throw Error(message);};
 const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 const opener=document.getElementById('opener'),privateField=document.getElementById('private');
 window.TfHelp.mountHub(document.getElementById('helpWorkspace'));opener.focus();window.TfHelp.open('arbeit');
 const dialog=document.getElementById('tfHelpDialog'),close=dialog.querySelector('.tf-help-close'),printer=dialog.querySelector('.tf-help-print'),search=dialog.querySelector('input[type=search]');
 assert(dialog.open,'Help opens as overlay');assert(document.activeElement===close,'Focus starts at X');
 const box=dialog.getBoundingClientRect(),x=close.getBoundingClientRect(),print=printer.getBoundingClientRect();
 assert(box.left>=0&&box.right<=innerWidth,'Dialog fits viewport');assert(x.left<print.left&&x.top<=box.top+20,'X is at upper left');assert(print.right>=box.right-24&&print.top<=box.top+20,'Printer is at upper right');
 const side=dialog.querySelector('.tf-help-sidebar').getBoundingClientRect(),article=dialog.querySelector('article').getBoundingClientRect();
 if(innerWidth>700)assert(side.right<=article.left+1,'Topics on the left');else assert(side.bottom<=article.top+1,'Topics above reader on phone');
 assert(article.height>120,'Reader has usable scroll space');
 search.value='no-such-topic-xyz';search.dispatchEvent(new Event('input'));assert(!dialog.querySelector('[data-help-topic]'),'No-result search');search.value='GPS';search.dispatchEvent(new Event('input'));dialog.querySelector('[data-help-topic="gps"]').click();assert(dialog.querySelector('#tfHelpTitle').textContent.includes('GPS'),'Topic selected');
 let prints=0;window.print=()=>{prints++;assert(document.body.classList.contains('tf-help-printing'),'Isolated print mode');};printer.click();await tick();assert(prints===1,'Printer button opens browser print');assert(privateField.value==='PRIVATE_FORM_DATA','Original field preserved');window.dispatchEvent(new Event('afterprint'));assert(!document.body.classList.contains('tf-help-printing'),'Print mode cleaned up');
 let payload;window.AndroidPortal={printHelp:async value=>payload=value};printer.click();await tick();assert(payload.title.includes('GPS')&&!payload.text.includes('PRIVATE_FORM_DATA'),'Android prints only help');delete window.AndroidPortal;
 close.click();await tick();assert(!dialog.open&&document.activeElement===opener,'X restores opener focus');
 window.TfHelp.open('arbeit');dialog.dispatchEvent(new Event('cancel',{cancelable:true}));await tick();assert(!dialog.open,'Escape/cancel closes help');
 window.loadTfHelp=async()=>window.TfHelp;window.ReportFeedback.error('Bitte Dienstbeginn prüfen.');const error=document.querySelector('.report-feedback');error.querySelector('.report-feedback-actions').lastElementChild.click();await tick();assert(dialog.open&&error.open,'Help opens over an error without closing it');close.click();await tick();assert(error.open&&document.activeElement===error.querySelector('.report-feedback-actions').lastElementChild,'Nested help restores error help button');error.querySelector('.report-feedback-actions').firstElementChild.click();await tick();
 window.TfHelp.open('arbeit');
 if(new URLSearchParams(location.search).get('mode')==='print')document.body.classList.add('tf-help-printing');
 document.documentElement.dataset.helpStatus='pass';window.parent.postMessage({helpStatus:'pass'},'*');
})().catch(error=>{document.documentElement.dataset.helpStatus='fail';document.documentElement.dataset.helpMessage=error.stack;window.parent.postMessage({helpStatus:'fail',message:error.stack},'*');});
'''
    return '<!doctype html><html lang="de" data-help-status="pending"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Formular darf nicht gedruckt werden</title><style>body{margin:0;font:18px system-ui}main{padding:20px}input,button{font:inherit}</style><style>'+css+'</style></head><body><main><h1>PRIVATE_FORM_DATA</h1><button id="opener">Hilfe öffnen</button><input id="private" value="PRIVATE_FORM_DATA"><div id="helpWorkspace"></div></main><script>'+scripts+checks+'</script></body></html>'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(name) for name in ['google-chrome','google-chrome-stable','chromium','chromium-browser'] if shutil.which(name)),None)
    if not chrome:raise SystemExit('Chrome required for help reader checks')
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);(root/'help.html').write_text(fixture())
        for width in [1280,768,375,320]:
            host=root/f'host-{width}.html'
            host.write_text(f'''<!doctype html><html data-help-status="pending"><head><style>body{{margin:0}}iframe{{border:0;width:{width}px;height:1100px;display:block}}</style><script>addEventListener('message',event=>{{if(event.source!==document.querySelector('iframe')?.contentWindow)return;document.documentElement.dataset.helpStatus=event.data.helpStatus;document.documentElement.dataset.helpMessage=event.data.message||'';}});</script></head><body><iframe src="help.html"></iframe></body></html>''')
            command=[chrome,'--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--allow-file-access-from-files','--hide-scrollbars','--force-device-scale-factor=1','--window-size=1400,1100','--virtual-time-budget=5000',f'--user-data-dir={root/("profile-"+str(width))}',f'--screenshot={args.output_dir.resolve()/(str(width)+".png")}','--dump-dom',host.as_uri()]
            run=subprocess.run(command,capture_output=True,text=True,timeout=60)
            (args.output_dir/f'{width}.html').write_text(run.stdout)
            passed=run.returncode==0 and 'data-help-status="pass"' in run.stdout
            match=re.search(r'data-help-message="([^"]*)"',run.stdout);message=html.unescape(match.group(1)) if match else 'Help fixture did not finish'
            results.append(dict(width=width,passed=passed,message='' if passed else message));print(f'Help overlay {width}px: '+('PASS' if passed else 'FAIL '+message))
        pdf=args.output_dir.resolve()/'help-print.pdf'
        run=subprocess.run([chrome,'--headless=new','--no-sandbox','--disable-gpu','--disable-background-networking','--no-pdf-header-footer','--window-size=1280,1100','--virtual-time-budget=5000',f'--user-data-dir={root/"print-profile"}',f'--print-to-pdf={pdf}','--dump-dom',(root/'help.html').as_uri()+'?mode=print'],capture_output=True,text=True,timeout=60)
        (args.output_dir/'print.html').write_text(run.stdout)
        text='\n'.join(page.extract_text() for page in PdfReader(pdf).pages) if pdf.exists() else ''
        print_pass=run.returncode==0 and all(phrase in text for phrase in ['Arbeitsbericht','Zwischenspeichern','Was wird erfasst?','Wo stehen die Angaben?']) and all(phrase not in text for phrase in ['PRIVATE_FORM_DATA','Thema suchen','Internationalen Bremszettel ausfüllen'])
        results.append(dict(print=True,passed=print_pass));print('Help print content isolation: '+('PASS' if print_pass else 'FAIL'))
    (args.output_dir/'results.json').write_text(json.dumps(results,indent=2))
    if not all(row['passed'] for row in results):raise SystemExit(1)

if __name__=='__main__':main()
