"""Real Chrome contrast, layout, module surfaces, modal and print palette checks."""
import argparse
from localized_fixtures import localize_html
import html,json,re,shutil,subprocess,tempfile
from pathlib import Path
from pypdf import PdfReader
from pypdf.generic import ContentStream
STATIC=Path(__file__).resolve().parents[1]/'lokzeitleiste'/'static'
PAGES={
 'start':('tf-portal.html','landing'),'arbeitsbericht':('tf-portal.html','workReport'),
 'arbeitsplan':('tf-portal.html','plan'),'leuna':('tf-portal.html','placeholder'),
 'bahnhoefe':('tf-portal.html','stationDirectory'),'notizen':('tf-portal.html','personalNotes'),
 'hilfe':('tf-portal.html','helpCatalog'),'dokumente':('documents.html',None),
 'konto':('tf-profile.html',None),'nachrichten':('tf-messages.html',None),
 'lok':('loco-handover.html',None),'bremszettel':('brake-sheet.html',None),
 'bremszettel-de':('national-brake-sheet.html',None),'anmeldung':('account.html',None),
 'verwaltung':('backend-start.html',None),
}
CHECKS=r'''
(()=>{
 const assert=(value,message)=>{if(!value)throw Error(message);};
 const rgb=value=>value.match(/[\d.]+/g).slice(0,3).map(Number);
 const luminance=color=>rgb(color).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
 const contrast=(a,b)=>(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05);
 const theme=window.PortalTheme,button=document.getElementById('portalThemeToggle'),input=document.getElementById('themeProbe');
 assert(button&&button.getAttribute('aria-label')==='Nachtmodus','Accessible header switch on every page');
 input.value='Ungespeicherter Text';const light=getComputedStyle(document.body).backgroundColor;
 button.click();assert(document.documentElement.dataset.theme==='dark','Switch enables night mode');
 const dark=getComputedStyle(document.body);assert(dark.backgroundColor==='rgb(13, 23, 34)','Dark page canvas');assert(contrast(dark.backgroundColor,dark.color)>7,'High body contrast');
 const field=getComputedStyle(input);assert(contrast(field.color,field.backgroundColor)>4.5,'Readable field');
 assert(input.value==='Ungespeicherter Text','Switch preserves form values');
 for(const node of document.querySelectorAll('.card,main>section,.module,dialog,.tf-help-sidebar,.tf-note-open')){const style=getComputedStyle(node);assert(luminance(style.backgroundColor)<.12,'Dark module/dialog surface: '+node.className);assert(contrast(style.color,style.backgroundColor)>4.5,'Readable module/dialog surface');}
 for(const node of document.querySelectorAll('.module-number')){const style=getComputedStyle(node);assert(contrast(style.color,style.backgroundColor)>4.5,'Readable module number');}const original=document.getElementById('originalImage');assert(getComputedStyle(original).filter==='none','Original images never inverted');
 const signature=document.getElementById('signatureCanvas');if(signature)assert(getComputedStyle(signature).backgroundColor==='rgb(255, 255, 255)','Handwriting remains on white');
 const size=button.getBoundingClientRect();assert(size.width>=44&&size.height>=44,'44 pixel touch target');assert(size.left>=0&&size.right<=innerWidth,'Switch fits narrow viewport');
 button.click();assert(document.documentElement.dataset.theme==='light','Switch returns to day mode');assert(getComputedStyle(document.body).backgroundColor===light,'Day palette restored');assert(input.value==='Ungespeicherter Text','Values retained through both modes');
 theme.set('dark');if(document.getElementById('helpWorkspace')){window.TfHelp.mountHub(document.getElementById('helpWorkspace'));window.TfHelp.open('darstellung');const dialog=document.getElementById('tfHelpDialog');assert(getComputedStyle(dialog).backgroundColor==='rgb(23, 38, 53)','Late-created help is dark');dialog.querySelector('.tf-help-close').click();}
 document.documentElement.dataset.themeStatus='pass';window.parent.postMessage({themeStatus:'pass'},'*');
})()
'''
def fixture(name,source,section):
    page=localize_html((STATIC/source).read_text())
    page=re.sub(r'<script\b[^>]*>.*?</script>','',page,flags=re.S)
    page=re.sub(r'<link\b[^>]*>','',page)
    css='\n'.join((STATIC/f).read_text() for f in ['portal-theme.css','portal.css','tf-portal.css','tf-shell.css','work-report.css','documents.css','tf-help.css','brake-sheet.css','national-brake-sheet.css','tf-signature.css','backend-nav.css','responsive.css'])
    page=page.replace('</head>','<style>'+css+'</style></head>')
    if section:page=page.replace('id="'+section+'" hidden','id="'+section+'"')
    if section=='workReport':page=page.replace('id="reportDetails" hidden','id="reportDetails"')
    scripts=(STATIC/'messages.js').read_text()+'\n'+'\n'.join((STATIC/f).read_text() for f in ['tf-help-content.js','tf-help.js','portal-theme.js'])
    tests="document.addEventListener('DOMContentLoaded',()=>{try{"+CHECKS+"}catch(error){document.documentElement.dataset.themeStatus='fail';document.documentElement.dataset.themeMessage=error.stack;window.parent.postMessage({themeStatus:'fail',message:error.stack},'*');}},{once:true});"
    return page.replace('</body>','<section class="card"><label>Prüfeingabe<input id="themeProbe"></label><img id="originalImage" alt="Beispielbild"><dialog>Testdialog</dialog></section><script>'+scripts+tests+'</script></body>')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    chrome=next((shutil.which(x) for x in ['google-chrome','google-chrome-stable','chromium'] if shutil.which(x)),None)
    if not chrome:raise SystemExit('Chrome is required')
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for name,(source,section) in PAGES.items():
            (root/(name+'.html')).write_text(fixture(name,source,section))
            for width in [1280,375]:
                host=root/'host.html';host.write_text(f'''<!doctype html><html data-theme-status="pending"><head><style>body{{margin:0}}iframe{{border:0;width:{width}px;height:1000px}}</style><script>addEventListener('message',event=>{{document.documentElement.dataset.themeStatus=event.data.themeStatus;document.documentElement.dataset.themeMessage=event.data.message||'';}})</script></head><body><iframe src="{name}.html"></iframe></body></html>''')
                command=[chrome,'--headless=new','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--force-device-scale-factor=1','--window-size=1400,1000','--virtual-time-budget=3000',f'--user-data-dir={root/(name+str(width))}',f'--screenshot={args.output_dir.resolve()/(name+"-"+str(width)+".png")}','--dump-dom',host.as_uri()]
                run=subprocess.run(command,capture_output=True,text=True,timeout=60);passed=run.returncode==0 and 'data-theme-status="pass"' in run.stdout
                match=re.search('data-theme-message="([^"]*)"',run.stdout);message=html.unescape(match.group(1)) if match else 'Fixture did not complete'
                (args.output_dir/(name+'-'+str(width)+'.html')).write_text(run.stdout)
                results.append(dict(module=name,width=width,passed=passed,message='' if passed else message));print(name,str(width), 'PASS' if passed else 'FAIL '+message)
        # Print media must ignore the night palette, including forms and help dialogs.
        (root/'print.html').write_text(fixture('druck','tf-portal.html','workReport').replace("document.documentElement.dataset.themeStatus='pass';", "document.documentElement.dataset.themeStatus='pass';document.body.setAttribute('data-print-body',getComputedStyle(document.body).backgroundColor);"))
        run=subprocess.run([chrome,'--headless=new','--no-sandbox','--disable-gpu','--allow-file-access-from-files','--virtual-time-budget=3000',f'--user-data-dir={root/"print-profile"}',f'--print-to-pdf={args.output_dir.resolve()/"theme-print.pdf"}','--dump-dom',(root/'print.html').as_uri()],capture_output=True,text=True,timeout=60)
        pdf=args.output_dir/'theme-print.pdf'
        colors=[]
        if pdf.exists():
            reader=PdfReader(pdf)
            for page in reader.pages:
                colors.extend(tuple(float(v) for v in operands) for operands,op in ContentStream(page.get_contents(),reader).operations if op==b'rg')
        near=lambda color,target: all(abs(a-b)<.006 for a,b in zip(color,target))
        print_pass=run.returncode==0 and bool(colors) and not any(near(color,(13/255,23/255,34/255)) or near(color,(23/255,38/255,53/255)) for color in colors)
        (args.output_dir/'print.html').write_text(run.stdout);print('Print palette', 'PASS' if print_pass else 'FAIL');results.append(dict(print=True,passed=print_pass))
    (args.output_dir/'results.json').write_text(json.dumps(results,indent=2))
    if not all(r['passed'] for r in results):raise SystemExit(1)
if __name__=='__main__':main()
