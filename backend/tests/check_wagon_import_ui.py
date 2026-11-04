"""Exercise the actual international brake-sheet import preview and apply flow in Chrome."""
import argparse, html, re, shutil, subprocess, sys
from pathlib import Path
STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste/static'
sys.path.insert(0,str(STATIC.parent.parent))
from lokzeitleiste.localization import resolve_placeholders
MOCK=r'''
window.confirm=()=>true;window.ReportFeedback={error:message=>{document.documentElement.dataset.error=message;}};
const imported={station_from:'Origin',station_to:'FIRST',first_vehicle:'330000000000',last_vehicle:'330000000007',brake_mode:'G',wagon:{count:8,length:121,weight:641,brake:472},wagon_import:{sheet:'Dynamic',first_row:10,last_row:17,total_row:18,length_total:'120.08',weight_total:'640.08',g_total:'472',p_total:'560',rows:Array.from({length:8},(_,i)=>({number:String(330000000000+i),length:'15.01',weight:'80.01',g:'59',p:'70'}))}};
window.fetch=async(path,options={})=>({ok:true,json:async()=>{if(path.endsWith('/account/me'))return {id:1,role:'tf'};if(path.endsWith('/vehicles'))return [];if(path.endsWith('/import-wagons')){if(!(options.body instanceof FormData))throw Error('Multipart upload required');return imported;}if(path.endsWith('/calculate')){const data=JSON.parse(options.body),b=data.wagon_import?imported.wagon:data.wagon;return {lines:[],a:{count:0,length:null,weight:null,holding:null,brake:null},b,total:{count:0,length:null,weight:null,holding:null,brake:null},available:null,missing:null,preview_missing:['Tfz']};}return [];} });
'''
CHECKS=r'''
(async()=>{
 const assert=(ok,message)=>{if(!ok)throw Error(message);},tick=()=>new Promise(r=>setTimeout(r,0));
 for(let i=0;i<100&&!document.getElementById('wagon_count');i++)await tick();
 const file=document.getElementById('brakeImportFile');const pick=async()=>{const transfer=new DataTransfer();transfer.items.add(new File(['synthetic'],'wagons.xlsx'));file.files=transfer.files;await file.onchange();};await pick();
 const dialog=document.getElementById('brakeImportDialog');assert(dialog.open,'Import preview opens');assert(document.getElementById('station_to').value==='','No fields overwritten before applying');assert(dialog.textContent.includes('FIRST'),'Recognized destination shown');
 document.getElementById('brakeImportCancel').click();await tick();assert(!dialog.open,'Cancel closes preview');assert(document.getElementById('wagon_count').value==='','Cancel preserves form');
 await pick();assert(dialog.open,'Second import preview opens: '+document.getElementById('brakeStatus').textContent);assert(document.getElementById('brakeImportApply').getBoundingClientRect().height>=44,'Touch target');assert(dialog.getBoundingClientRect().width<=innerWidth,'Preview fits viewport');document.getElementById('brakeImportApply').click();await tick();
 assert(!dialog.open,'Apply closes preview');assert(document.getElementById('station_from').value==='Origin','Origin applied');assert(document.getElementById('station_to').value==='FIRST','First word destination applied');
 assert(document.getElementById('section_to').value==='FIRST','Section destination copied');assert(document.getElementById('wagon_count').value==='8','Dynamic wagon count applied');assert(document.getElementById('wagon_brake').value==='472','Brake sum applied');
 const saved=JSON.parse(localStorage.getItem('lokzeitleiste.brake-sheet.1'));assert(saved.sheet.wagon_import.rows.length===8,'Source rows saved with local draft');
 const weight=document.getElementById('wagon_weight');weight.value='700';weight.dispatchEvent(new Event('input',{bubbles:true}));
 assert(JSON.parse(localStorage.getItem('lokzeitleiste.brake-sheet.1')).sheet.wagon_import===null,'Manual override detaches automatic source');
 document.documentElement.dataset.wagonStatus='pass';
})().catch(error=>{document.documentElement.dataset.wagonStatus='fail';document.documentElement.dataset.wagonMessage=error.stack;});
'''
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);out=parser.parse_args().output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(n) for n in ['google-chrome','google-chrome-stable','chromium'] if shutil.which(n)),None)
    if not chrome:raise SystemExit('Chrome required')
    page=resolve_placeholders((STATIC/'brake-sheet.html').read_text());page=re.sub(r'<script\b[^>]*>.*?</script>','',page,flags=re.S);page=re.sub(r'<link\b[^>]*>','',page)
    css='\n'.join((STATIC/f).read_text() for f in ['portal.css','responsive.css','brake-sheet.css'])
    code=(STATIC/'messages.js').read_text()+MOCK+'\n'+(STATIC/'brake-sheet.js').read_text()+CHECKS
    path=out/'fixture.html';path.write_text(page.replace('</head>','<style>'+css+'</style></head>').replace('</body>','<script>'+code+'</script></body>'))
    for width in [1280,375]:
        result=subprocess.run([chrome,'--headless','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--window-size='+str(width)+',900','--virtual-time-budget=5000','--user-data-dir='+str(out/('profile'+str(width))),'--screenshot='+str(out/(str(width)+'.png')),'--dump-dom',path.as_uri()],capture_output=True,text=True,timeout=45)
        (out/(str(width)+'-result.html')).write_text(result.stdout)
        if 'data-wagon-status="pass"' not in result.stdout:
            message=re.search(r'data-wagon-message="([^"]*)"',result.stdout);raise SystemExit(html.unescape(message[1]) if message else result.stderr[-1200:])
        print(width,'PASS')
if __name__=='__main__':main()
