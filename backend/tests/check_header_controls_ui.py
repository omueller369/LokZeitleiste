"""Real shared header layout, glyph-only help, reload and keyboard order."""
import argparse
import html
import re
import shutil
import subprocess
from pathlib import Path

STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste/static'
CHECKS=r'''
(async()=>{
 const assert=(v,m)=>{if(!v)throw Error(m);};
 const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 await window.AppShellReady;for(let i=0;i<200&&!window.I18n?.ready;i++)await tick();await tick();
 const header=document.querySelector('header.tf-shell'),brand=header.querySelector('.tf-shell-brand'),controls=header.querySelector('.tf-shell-controls');
 assert(header&&controls,'Shared header rendered');
 assert(brand.children.length===2&&brand.querySelector('img')&&brand.querySelector('button'),'Logo and logout alone on the left');
 const theme=controls.querySelector('#portalThemeToggle'),language=controls.querySelector('#ctlLanguageSelect'),help=controls.querySelector('.tf-shell-help');
 assert(theme&&language,'Theme and language inside right controls');
 const rect=n=>n.getBoundingClientRect(),tr=rect(theme),lr=rect(language),hr=rect(header),br=rect(brand);
 assert(br.right<=rect(controls).left+1,'Brand and right controls do not overlap');
 assert(tr.right<=lr.left+1,'Theme before language');
 if(document.body.dataset.area==='tf'){assert(help&&help.textContent==='?','Help shows only ?');assert(help.getAttribute('aria-label'),'Accessible help label');const r=rect(help);assert(tr.right<=r.left+1&&r.right<=lr.left+1,'Visual order theme, help, language');
 const buttons=[...controls.querySelectorAll('button,select')];assert(buttons[0]===theme&&buttons[1]===help&&buttons[2]===language,'Keyboard order matches visual order');}
 assert(Math.abs(lr.right-(hr.right-parseFloat(getComputedStyle(header).paddingRight)))<2,'Language at far right');
 for(const n of [theme,language,...(help?[help]:[])]){const r=rect(n);assert(r.left>=0&&r.right<=innerWidth+1,'Control fits viewport');assert(r.height>=44,'Touch target');}
 theme.click();assert(document.documentElement.dataset.theme==='dark','Theme still works');theme.click();
 language.value='pl';language.dispatchEvent(new Event('change'));await tick();assert(window.I18n.language==='pl','Language still works');
 const homes=[...document.querySelectorAll('.backend-home-button')];
 if(document.body.dataset.area==='backend'){assert(homes.length===2,'Two backend home buttons');for(const link of homes){assert(link.getAttribute('href')==='/admin/start','Home targets backend dashboard');assert(link.textContent===CtlText.text('portal_tf_shell.text_e04d24c52b3d',{},'pl'),'Home buttons switch language');const r=rect(link);assert(r.height>=44&&r.left>=0&&r.right<=innerWidth,'Home button fits viewport');}assert(document.querySelector('header').nextElementSibling.classList.contains('backend-home-top'),'Home above content');assert(document.querySelector('footer').previousElementSibling.classList.contains('backend-home-bottom'),'Home below content');}else assert(homes.length===0,'TF portal has no backend home controls');
 const old=header.querySelector('.tf-shell-title').textContent;await window.I18n.set('de');assert(brand.querySelector('button'),'Logout retained');
 document.documentElement.dataset.headerStatus='pass';parent.postMessage({headerStatus:'pass'},'*');
})().catch(error=>{document.documentElement.dataset.headerStatus='fail';parent.postMessage({headerStatus:'fail',message:error.stack},'*');});
'''

def fixture(area):
    css='\n'.join((STATIC/f).read_text() for f in ['portal.css','responsive.css','tf-shell.css','portal-theme.css'])
    mock="sessionStorage.setItem('ctl.area',"+repr(area)+");window.fetch=async(input,options={})=>({ok:true,json:async()=>String(input).includes('/locale')?{language:'de',configured:false}:String(input).includes('/unread')?{count:0}:{first_name:'Mira',last_name:'Beispiel',tf_number:'787123',personnel_number:'00123',last_login_at:'2026-11-04T01:00:00Z',software:'LokZeitleiste',version:'0.26',copyright_year:2026}});window.alert=()=>{};window.confirm=()=>true;"
    scripts=(STATIC/'messages.js').read_text()+mock+'\n'+'\n'.join((STATIC/f).read_text() for f in ['i18n.js','portal-theme.js','tf-shell.js'])
    return '<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+'</style></head><body data-area="'+area+'"><header></header><main><h2>Test</h2></main><footer></footer><script>'+scripts+"\ndocument.addEventListener('DOMContentLoaded',()=>{"+CHECKS+'});</script></body></html>'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(n) for n in ['google-chrome','google-chrome-stable','chromium'] if shutil.which(n)),None)
    if not chrome:raise SystemExit('Chrome is required')
    for area in ['tf','backend']:
        page=out/(area+'.html');page.write_text(fixture(area))
        for width in [1280,375,320]:
            host=out/'host.html';host.write_text('<!doctype html><html><head><style>body{margin:0}iframe{border:0;width:'+str(width)+'px;height:600px}</style><script>addEventListener("message",e=>{document.documentElement.dataset.headerStatus=e.data.headerStatus;document.documentElement.dataset.headerMessage=e.data.message||"";});</script></head><body><iframe src="'+area+'.html"></iframe></body></html>')
            r=subprocess.run([chrome,'--headless','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--window-size=1400,800','--virtual-time-budget=4000','--user-data-dir='+str(out/(area+str(width))), '--screenshot='+str(out/(area+str(width)+'.png')),'--dump-dom',host.as_uri()],capture_output=True,text=True,timeout=45)
            (out/(area+str(width)+'-result.html')).write_text(r.stdout)
            if 'data-header-status="pass"' not in r.stdout:
                m=re.search('data-header-message="([^"]*)"',r.stdout);raise SystemExit(area+' '+str(width)+': '+(html.unescape(m[1]) if m else r.stderr[-1000:]))
            print(area,width,'PASS')

if __name__=='__main__':main()
