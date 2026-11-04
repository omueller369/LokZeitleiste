"""Real DOM regression for TF list, shell-header replacement and immediate editing."""
import argparse
import html
import json
import re
import shutil
import subprocess
from pathlib import Path

STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste/static'
MOCK=r'''
window.photoSelection=()=>({close(){},value:async()=>null,reset(){}});
window.profilePhoto=()=>{};window.tfDefaultValidity=()=>'';window.tfExtraForm=()=>({close(){},payload(){}});
window.employeeEmailField=async()=>{};window.tfMetadata=null;
const users=[{id:10,first_name:'Alex',last_name:'Route',username:'123456',driver_type:'route',personnel_number:'1',bahncard:0},{id:11,first_name:'Sam',last_name:'Border',username:'234567',driver_type:'border',personnel_number:'2',bahncard:0}];
window.fetch=async url=>{if(url==='/api/v1/account/me'){document.querySelector('header').innerHTML='<h1>TF-Verwaltung</h1>';return {ok:true,json:async()=>({role:'admin'})};}return {ok:true,json:async()=>url==='/api/v1/admin/me'?{permissions:{employees:3,reports:1,planning:1,worktime:1}}:url.endsWith('tf-metadata')?{}:users};};
window.alert=message=>{throw Error(message);};
'''
CHECKS=r'''
(async()=>{
 const assert=(v,m)=>{if(!v)throw Error(m);};
 for(let i=0;i<100&&!document.querySelector('#users tr');i++)await new Promise(r=>setTimeout(r,0));
 assert(document.querySelectorAll('#users tr').length===2,'All TF visible without filter change');
 assert(document.getElementById('createTfCard').hidden,'New form initially hidden');
 assert(!document.getElementById('employeeCard').hidden,'List initially visible');
 assert(document.getElementById('newTfLink').getAttribute('href')==='/admin/tf/new','Explicit add link');
 assert(document.querySelector('script[data-backend-nav]'),'Navigation bootstrap survives missing legacy logout');
 const unrelated=document.createElement('dialog');document.body.append(unrelated);
 const edit=document.querySelector('#users .tf-row-actions').children[1];
 assert(edit.title==='Bearbeiten'&&edit.getAttribute('aria-label'),'Accessible edit icon');edit.click();
 const modal=document.querySelector('dialog[data-tf-profile]');assert(modal?.open,'Edit opens immediately despite unrelated dialog');
 assert(modal.querySelector('[name=first_name]').value==='Alex','Correct driver loaded');assert(!modal.querySelector('button:not([type])').hidden,'Save available');
 modal.close();await new Promise(resolve=>setTimeout(resolve,0));document.querySelector('#users .tf-row-actions').children[0].click();
 const view=document.querySelector('dialog[data-tf-profile]');assert(view?.open,'View opens immediately');assert(view.querySelector('[name=first_name]').disabled,'View is read-only');
 document.documentElement.dataset.tfAdminStatus='pass';
})().catch(error=>{document.documentElement.dataset.tfAdminStatus='fail';document.documentElement.dataset.tfAdminMessage=error.stack;});
'''

def fixture():
    page=(STATIC/'admin.html').read_text()
    page=re.sub(r'<script\b[^>]*>.*?</script>','',page,flags=re.S)
    page=re.sub(r'<link\b[^>]*>','',page)
    keys=json.loads((STATIC.parent/'locales/keys.json').read_text())['de']
    page=re.sub(r'\{\{([^{}]+)\}\}',lambda m:html.escape(keys[m[1]]),page)
    css=(STATIC/'responsive.css').read_text()
    code=(STATIC/'messages.js').read_text()+MOCK+'\n'+(STATIC/'admin.js').read_text()+CHECKS
    return page.replace('</head>','<style>'+css+'</style></head>').replace('</body>','<script>'+code+'</script></body>')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(n) for n in ['google-chrome','google-chrome-stable','chromium'] if shutil.which(n)),None)
    if not chrome:raise SystemExit('Chrome is required')
    # Supply the route input while running the unchanged controller in a local fixture.
    route=out/'fixture.html';route.write_text(fixture().replace("location.pathname", "'/admin/tf'"))
    for width in [1280,375]:
        r=subprocess.run([chrome,'--headless','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--window-size='+str(width)+',900','--virtual-time-budget=4000','--user-data-dir='+str(out/('profile'+str(width))),'--screenshot='+str(out/(str(width)+'.png')),'--dump-dom',route.as_uri()],capture_output=True,text=True,timeout=45)
        (out/(str(width)+'-result.html')).write_text(r.stdout)
        if 'data-tf-admin-status="pass"' not in r.stdout:
            m=re.search('data-tf-admin-message="([^"]*)"',r.stdout);raise SystemExit(str(width)+': '+(html.unescape(m[1]) if m else r.stderr[-1000:]))
        print(width,'PASS')

if __name__=='__main__':main()
