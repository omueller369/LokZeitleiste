"""Headless Chrome layout checks using the real portal CSS and editor controllers.

The fixture contains no account data and makes no server requests. Chrome is
provided by GitHub's ubuntu runner; no npm/browser download is required.
"""
import argparse
from localized_fixtures import localize_html
import html
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'lokzeitleiste' / 'static'


def fixture():
    page = localize_html((STATIC / 'tf-portal.html').read_text())
    page = re.sub(r'<script\b[^>]*>.*?</script>', '', page, flags=re.S)
    page = re.sub(r'<link\b[^>]*>', '', page)
    css = '\n'.join((STATIC / name).read_text() for name in ['tf-portal.css', 'work-report.css', 'responsive.css'])
    page = page.replace('</head>', '<style>' + css + '</style></head>')
    source = (STATIC / 'work-report.js').read_text().split('// Keep collapse buttons')[0]
    source = re.sub(r'\}\)\(\);\s*$', '''window.LayoutReport={fill(editor,day){
        trainEditor=editor;user={id:1};key='layout-test';trips=[];
        state={kind:'Sonstige Erfassung',client_id:'layout',legacy_pause:30,ausbleibe:[]};
        el('dutyStart').value=day+'T08:00';el('dutyEnd').value=day+'T16:00';totals();
    }};})();''', source)
    controllers = (STATIC/'messages.js').read_text()+'\n'+'\n'.join((STATIC / name).read_text() for name in ['train-journeys.js', 'gps.js'])
    checks = r'''
(async()=>{
 const assert=(condition,message)=>{if(!condition)throw Error(message);};
 const rect=selector=>document.querySelector(selector).getBoundingClientRect();
 const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 document.getElementById('workReport').hidden=false;document.getElementById('reportDetails').hidden=false;
 let id=0;
 const editor=new window.TrainJourneyEditor({userId:1,button:document.getElementById('newTrainJourney'),container:document.getElementById('trainJourneyEditor'),readonly:()=>false,viewOnly:()=>false,bounds:()=>({start:day+'T08:00',end:day+'T16:00'}),minute:value=>Date.parse(value)/60000,clock:n=>Math.floor(n/60)+':'+String(n%60).padStart(2,'0'),uuid:()=>String(++id),stations(){},resolve:async()=>({code:'BBB',name:'Beispiel'}),changed(){},editingChanged(){},message(){},block(){}});
 editor.restore([{id:'layout-journey',train_number:'123',start_station:'BBB',start_station_name:'Beispiel',end_station:'CCC',end_station_name:'Ziel',start_at:day+'T08:00',end_at:day+'T16:00',events:[{id:'event',station:'BBB',station_name:'Beispiel',reason:'V1',cause:'CTL',start_at:day+'T10:00',end_at:day+'T10:15'}]}]);
 window.LayoutReport.fill(editor,day);
 // Bounding-rectangle reads below force synchronous layout; no animation-frame race in headless mode.
 const kinds=[...document.querySelectorAll('#dutyKinds label span')].map(el=>el.textContent);
 assert(kinds.join(',')==='DS,BS,RBS,AS,U,K','Dienstart abbreviations');
 const ids=['dutyDuration','requiredPause','netDuration','documentedPauseTotal'];
 assert(ids.map(id=>document.getElementById(id).textContent).join(',')==='8:00,0:30,8:00,0:30','Metrics contain h:mm only');
 const overview=rect('.duty-overview'),k=rect('#dutyKinds'),metrics=rect('#dutyMetrics'),begin=rect('.duty-begin'),end=rect('.duty-end'),allowance=rect('#absenceAllowance');
 assert(end.top>=begin.bottom-1,'Dienstende below Dienstbeginn');
 assert(allowance.top>=end.bottom-1,'Ausbleibe below Dienstende');
 if(innerWidth>800){
  assert(begin.left>k.right,'Duty times on the right');
  assert(Math.abs(k.left-metrics.left)<2,'Metrics aligned left below kinds');
  assert(metrics.top>=k.bottom,'Metrics below kinds');
  assert(allowance.width/overview.width>.30&&allowance.width/overview.width<.35,'Ausbleibe occupies one third');
 }else{
  assert(begin.top>=metrics.bottom,'Mobile duty times stack below left groups');
 }
 for(const selector of ['#dutyKinds','#dutyMetrics','#absenceAllowance']){
  const el=document.querySelector(selector),box=el.getBoundingClientRect(),style=getComputedStyle(el);
  assert(style.borderTopWidth==='1px'&&parseFloat(style.borderTopLeftRadius)>0,'Thin rounded group frame');
  assert(box.left>=0&&box.right<=innerWidth+1,'Group fits viewport: '+selector);
 }
 for(const el of document.querySelectorAll('.duty-metric')){
  const label=el.querySelector('span').getBoundingClientRect(),value=el.querySelector('strong').getBoundingClientRect();
  assert(value.top>=label.bottom,'Metric value below its label');assert(el.scrollWidth<=el.clientWidth+1,'Metric text fits its column');
  assert(Math.abs((label.left+label.right)/2-(value.left+value.right)/2)<2,'Metric value aligned with label');
 }
 const item=editor.items[0],gps=item.gps;
 assert(item.eventTable.compareDocumentPosition(gps.box)&Node.DOCUMENT_POSITION_FOLLOWING,'Details precede GPS');
 assert(gps.content.hidden&&gps.collapseButton.textContent==='+','GPS collapsed by default');
 assert(gps.collapseButton.getAttribute('aria-expanded')==='false','Collapsed accessibility state');
 assert(rect('.gps-box>h3').right-rect('.gps-box .report-block-toggle').right<2,'GPS toggle at top right');
 gps.collapseButton.click();assert(!gps.content.hidden&&gps.collapseButton.textContent==='−','GPS expands with minus');
 const point={lat:52,lon:13,accuracy:5,speed:0};gps.record={train_number:'123',ended:true,detection_version:3,points:Array.from({length:63},(_,i)=>({...point,t:Date.now()-310000+i*5000}))};gps.draw();
 const before=gps.record.points.length;gps.collapseButton.click();assert(gps.content.hidden&&gps.record.points.length===before,'Collapse preserves recorded fixes');
 assert(getComputedStyle(gps.content).display==='none','GPS body hidden visually');
 window.parent.postMessage({layoutStatus:'pass',width:innerWidth},'*');
})().catch(error=>window.parent.postMessage({layoutStatus:'fail',message:error.stack},'*'));
'''
    mocks = "Object.defineProperty(navigator,'onLine',{get:()=>false});window.fetch=async()=>({ok:false,status:404,json:async()=>({})});"
    return page.replace('</body>', '<script>' + mocks + controllers + source + checks + '</script></body>')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    chrome = next((shutil.which(name) for name in ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'] if shutil.which(name)), None)
    if not chrome:
        raise SystemExit('Headless Chrome is required for responsive layout checks.')
    results = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / 'fixture.html').write_text(fixture())
        for width in [1280, 768, 375, 320]:
            host = root / f'host-{width}.html'
            host.write_text(f'''<!doctype html><html data-layout-status="pending"><head><meta charset="utf-8"><style>body{{margin:0;background:#eef3f5}}iframe{{border:0;width:{width}px;height:1800px;display:block}}</style><script>
addEventListener('message',event=>{{if(event.source!==document.querySelector('iframe')?.contentWindow)return;document.documentElement.dataset.layoutStatus=event.data.layoutStatus;document.documentElement.dataset.layoutMessage=event.data.message||'';}});
</script></head><body><iframe src="fixture.html"></iframe></body></html>''')
            command = [chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-background-networking', '--allow-file-access-from-files', '--hide-scrollbars', '--force-device-scale-factor=1', '--window-size=1400,1800', '--virtual-time-budget=5000', f'--user-data-dir={root / ("profile-"+str(width))}', f'--screenshot={args.output_dir.resolve() / (str(width)+".png")}', '--dump-dom', host.as_uri()]
            run = subprocess.run(command, capture_output=True, text=True, timeout=60)
            (args.output_dir / f'{width}.html').write_text(run.stdout)
            passed = run.returncode == 0 and 'data-layout-status="pass"' in run.stdout
            match = re.search(r'data-layout-message="([^"]*)"', run.stdout)
            message = html.unescape(match.group(1)) if match else ('Layout fixture did not finish' if 'data-layout-status="pending"' in run.stdout else run.stderr[-2000:])
            results.append(dict(width=width,passed=passed,message=message))
            print(f'Work report layout {width}px: '+('PASS' if passed else 'FAIL '+message))
    (args.output_dir / 'results.json').write_text(json.dumps(results,indent=2))
    if not all(row['passed'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
