"""Exercise the real key bundle, language picker and help in headless Chrome."""
import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'lokzeitleiste/static'
CHECKS = r'''
(async()=>{
 const assert=(condition,message)=>{if(!condition)throw Error(message);};
 const tick=()=>new Promise(resolve=>setTimeout(resolve,0));await tick();await tick();
 const picker=document.getElementById('ctlLanguageSelect');assert(picker,'Language picker exists');assert([...picker.options].map(o=>o.value).join(',')==='de,pl,en','Exactly three requested languages');
 const user=document.getElementById('privateValue');user.value='Speichern';
 for(const [lang,label,title]of [['pl','Zapisz','Wybór języka'],['en','Save','Choose a language'],['de','Speichern','Sprache auswählen']]){
  picker.value=lang;picker.dispatchEvent(new Event('change'));await tick();await tick();
  assert(document.documentElement.lang===lang,'Document language '+lang);
  assert(document.getElementById('probe').textContent===label,'Static key translated '+lang);
  assert(document.getElementById('probe').title===label,'Tooltip translated '+lang);
  assert(user.value==='Speichern','Input value retained');assert(document.getElementById('privateText').textContent==='Speichern','User text retained');
  assert(document.getElementById('contract').value==='Urlaub','Persisted German option value unchanged');
  const dynamic=document.createElement('span');dynamic.textContent='Notiz gespeichert.';document.body.append(dynamic);await tick();assert(dynamic.textContent===window.I18n.t('Notiz gespeichert.'),'New dynamic text translated');dynamic.remove();
  window.TfHelp.open('sprache');assert(document.getElementById('tfHelpTitle').textContent===title,'Help title '+lang);assert(document.getElementById('tfHelpArticle').lang===lang,'Help language '+lang);
  const search=document.getElementById('tfHelpSearch');search.value=title;search.oninput();assert(document.querySelector('[data-help-topic="sprache"]'),'Translated help search');
 }
 window.I18n.set('pl',true);await tick();assert(document.getElementById('tfHelpTitle').textContent==='Wybór języka','Open help changes language');
 const payloads=[];window.AndroidPortal={printHelp:async value=>payloads.push(value)};await window.TfHelp.print();assert(payloads[0].title==='Wybór języka','Native print title translated');assert(payloads[0].text.includes('Wybierz u góry'),'Native print body translated');assert(!payloads[0].text.includes('Deine eigenen'),'No German help paragraph');
 const old=document.querySelector('header'),replacement=document.createElement('header');old.replaceWith(replacement);window.dispatchEvent(new Event('portal-shell-ready'));assert(replacement.contains(picker),'Picker survives shell replacement');
 await fetch('/api/v1/test');assert(window.lastLanguage==='pl','API language header');assert(localStorage.getItem('lokzeitleiste.language')==='pl','Language saved locally');assert(window.savedLanguages.includes('pl'),'Language saved to account');
 document.documentElement.dataset.i18nStatus='pass';
})().catch(error=>{document.documentElement.dataset.i18nStatus='fail';document.documentElement.dataset.i18nError=error.stack;});
'''


def fixture(source):
    page = (STATIC/source).read_text()
    page = re.sub(r'<script\b[^>]*>.*?</script>|<link\b[^>]*>', '', page, flags=re.S)
    key = next(k for k,v in json.loads((STATIC.parent/'locales/keys.json').read_text())['de'].items() if v=='Speichern')
    mock = "window.savedLanguages=[];window.fetch=async(input,options={})=>{window.lastLanguage=new Headers(options.headers).get('Accept-Language');if(options.method==='PUT')window.savedLanguages.push(JSON.parse(options.body).language);return {ok:true,json:async()=>({language:'de',configured:false})};};window.alert=()=>{};window.confirm=()=>true;"
    scripts = (STATIC/'messages.js').read_text()+mock+'\n'+'\n'.join((STATIC/name).read_text() for name in ['i18n.js','tf-help-content.js','tf-help.js'])
    script = '<script>'+scripts+"\ndocument.addEventListener('DOMContentLoaded',()=>{"+CHECKS+'});</script>'
    probes = '<div id="probe" title="{{'+key+'}}">{{'+key+'}}</div><input id="privateValue"><p id="privateText" data-i18n-ignore>Speichern</p><select id="contract"><option value="Urlaub">Urlaub</option></select>'
    return page.replace('</body>',probes+script+'</body>')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(x) for x in ['google-chrome','google-chrome-stable','chromium'] if shutil.which(x)),None)
    if not chrome:raise SystemExit('Chrome is required')
    for source in ['tf-portal.html','backend-start.html','account.html']:
        path=args.output_dir/source;path.write_text(fixture(source))
        result=subprocess.run([chrome,'--headless','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--virtual-time-budget=5000','--dump-dom',path.resolve().as_uri()],capture_output=True,text=True,timeout=45)
        (args.output_dir/(path.stem+'-result.html')).write_text(result.stdout)
        if 'data-i18n-status="pass"' not in result.stdout:
            error=re.search(r'data-i18n-error="([^"]*)"',result.stdout)
            raise SystemExit(source+': '+(html.unescape(error[1]) if error else result.stderr[-1000:]))
    print('DE/PL/EN: portal/backend/account, static/dynamic text, live help/search/print, stable values, persistence and shell remount: PASS')


if __name__=='__main__':main()
