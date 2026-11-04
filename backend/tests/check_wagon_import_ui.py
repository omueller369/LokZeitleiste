"""Exercise the actual international brake-sheet import preview and apply flow in Chrome."""
import argparse, html, re, shutil, subprocess, sys
from pathlib import Path
STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste/static'
sys.path.insert(0,str(STATIC.parent.parent))
from lokzeitleiste.localization import resolve_placeholders
MOCK=r'''
window.confirm=()=>true;window.ReportFeedback={error:message=>{document.documentElement.dataset.error=message;}};
const imported={station_from:'Origin',station_to:'FIRST',first_vehicle:'330000000000',last_vehicle:'330000000007',brake_mode:'G',wagon:{count:8,length:121,weight:641,brake:472},wagon_import:{sheet:'Dynamic',first_row:10,last_row:17,total_row:18,length_total:'120.08',weight_total:'640.08',g_total:'472',p_total:'560',rows:Array.from({length:8},(_,i)=>({number:String(330000000000+i),length:'15.01',weight:'80.01',g:'59',p:'70'}))}};
const locomotives=[{id:1,revision:1,vehicle_number:'91 80 6185 002-0',series:'185',length_m:30,weight_kg:90000,brake_g:80,brake_p:100,brake_r:120},{id:2,revision:1,vehicle_number:'91 80 6185 003-8',series:'185',length_m:10,weight_kg:80000,brake_g:40,brake_p:60,brake_r:80}];let rootMeta=null;
function calculation(data){const active=data.towed||[],first=active.find(row=>row.position===1),last=active.find(row=>row.position===8+active.length),destination=!data.section_parent&&active.length?active[0].destination:data.station_to;return {lines:[],a:{count:0,length:null,weight:null,holding:null,brake:null},b:data.wagon_import?{...imported.wagon,count:8+active.length}:data.wagon,total:{count:0,length:null,weight:null,holding:null,brake:null},available:null,missing:null,preview_missing:['Tfz'],station_to:destination,final_station:data.final_station||'',first_vehicle:first?'918061850020':imported.first_vehicle,last_vehicle:last?'918061850038':imported.last_vehicle,remarks:active.length?'Mitgeführte Tfz nur bis Stop X.':'',towed:[]};}
window.fetch=async(path,options={})=>({ok:true,json:async()=>{if(path.endsWith('/account/me'))return {id:1,role:'tf'};if(path.endsWith('/vehicles'))return locomotives;if(path.endsWith('/import-wagons')){if(!(options.body instanceof FormData))throw Error('Multipart upload required');return imported;}if(path.endsWith('/calculate'))return calculation(JSON.parse(options.body));if(options.method==='PUT'){const data=JSON.parse(options.body).sheet,id=path.split('/').at(-1),result=calculation(data);data.station_to=result.station_to;rootMeta={id,revision:1,sheet:data,calculation:result,created_at:'2026-11-04T10:00:00Z',created_by_name:'Test',sections:[{id,section_index:0,station_from:'Origin',station_to:'Stop X'},{id:'00000000-0000-0000-0000-000000000001',section_index:1,station_from:'Stop X',station_to:'Stop Y'},{id:'00000000-0000-0000-0000-000000000002',section_index:2,station_from:'Stop Y',station_to:'FIRST'}]};return rootMeta;}if(rootMeta&&path.endsWith(rootMeta.id))return rootMeta;if(rootMeta&&path.endsWith('00000000-0000-0000-0000-000000000001')){const data=JSON.parse(JSON.stringify(rootMeta.sheet));data.section_parent=rootMeta.id;data.section_index=1;data.station_from='Stop X';data.station_to='Stop Y';data.towed=data.towed.slice(1);data.towed[0].position=9;return {...rootMeta,id:'00000000-0000-0000-0000-000000000001',sheet:data,calculation:calculation(data)};}return [];} });
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
 document.getElementById('addTowed').click();document.getElementById('addTowed').click();
 const boxes=[...document.querySelectorAll('.brake-towed')],field=(box,name)=>box.querySelector('[data-towed='+name+']'),change=input=>input.dispatchEvent(new Event('change',{bubbles:true}));
 field(boxes[0],'vehicle').value='1';change(field(boxes[0],'vehicle'));assert(field(boxes[0],'count').value==='','G count requires explicit choice');field(boxes[0],'position').value='1';field(boxes[0],'count').value='no';change(field(boxes[0],'count'));field(boxes[0],'destination').value='Stop X';change(field(boxes[0],'destination'));
 field(boxes[1],'vehicle').value='2';change(field(boxes[1],'vehicle'));field(boxes[1],'brakePosition').value='P';change(field(boxes[1],'brakePosition'));field(boxes[1],'position').value='10';field(boxes[1],'destination').value='Stop Y';field(boxes[1],'order').value='2';change(field(boxes[1],'order'));
 let state=JSON.parse(localStorage.getItem('lokzeitleiste.brake-sheet.1')).sheet;assert(state.towed.length===2&&state.towed[0].count_g===false,'Ordered tows and explicit zero stored');assert(state.towed[1].brake_position==='P','Independent towed brake mode');
 await new Promise(resolve=>setTimeout(resolve,350));assert(document.getElementById('station_to').value==='Stop X','First section ends at drop-off');assert(document.getElementById('final_station').value==='FIRST','Final destination retained');assert(document.getElementById('station_to').readOnly,'Computed section destination protected');
 assert(field(boxes[0],'brake').getBoundingClientRect().height>=44,'Towed input touch target');assert(boxes[0].getBoundingClientRect().right<=innerWidth,'Towed editor fits viewport');
 await document.getElementById('brakeSave').onclick();assert(!document.getElementById('brakeSections').hidden,'Section buttons shown after save');assert(document.getElementById('brakeSectionLinks').children.length===3,'Three sections listed');
 await document.getElementById('brakeSectionLinks').children[1].onclick();assert(document.getElementById('brakeFields').disabled,'Generated section read-only');assert(document.getElementById('brakeSave').disabled,'Generated section cannot be saved separately');assert(!document.getElementById('brakeRootEdit').hidden,'Original edit action available');
 document.getElementById('brakeRootEdit').click();for(let i=0;i<100&&(document.getElementById('brakeFields').disabled||document.getElementById('brakeSave').disabled);i++)await tick();assert(!document.getElementById('brakeFields').disabled,'Original becomes editable');
 for(const box of [...document.querySelectorAll('.brake-towed')])box.querySelector('button').click();assert(!document.getElementById('station_to').readOnly,'Normal editing restored after removing all tows');assert(document.getElementById('wagon_count').value==='8','Base wagon count restored immediately');assert(document.getElementById('wagon_brake').value==='','Stale combined brake sum cleared before recalculation');
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
