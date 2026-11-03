const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
let active;const events={};
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.attrs={};this.value='';this.isConnected=true;this.classes=new Set();this.classList={add:name=>this.classes.add(name),remove:name=>this.classes.delete(name),contains:name=>this.classes.has(name)};}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=[...nodes];}
 setAttribute(k,v){this.attrs[k]=String(v);}
 getAttribute(k){return this.attrs[k];}
 removeAttribute(k){delete this.attrs[k];}
 addEventListener(k,f){this.events??={};this.events[k]=f;}
 querySelectorAll(selector){return walk(this).filter(node=>selector==='[data-help-topic]'&&node.dataset.helpTopic);}
 focus(){active=this;}
 showModal(){this.open=true;}
 close(){this.open=false;this.events.close?.();}
}
const walk=root=>root.children.flatMap(child=>[child,...walk(child)]),body=new Element('body');
const document={body,title:'Private Arbeitsseite',get activeElement(){return active;},createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),getElementById:id=>walk(body).find(node=>node.id===id)};
let printed=0,nativePayload;const window={addEventListener:(name,fn)=>events[name]=fn,print(){printed++;assert(body.classList.contains('tf-help-printing'));}};
const context={window,document,location:{pathname:'/tf/arbeitsbericht'},console};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/tf-help-content.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/tf-help.js','utf8'),context);
const pages=window.TfHelpPages,help=window.TfHelp;
assert(!/\b(?:Sie|Ihnen|Ihr(?:e|er|em|en|es)?)\b/u.test(JSON.stringify(pages)), 'Help uses Du throughout');
assert(!/\bSie\b/u.test(fs.readFileSync('backend/lokzeitleiste/static/tf-help.js','utf8')), 'Help reader uses Du');
assert.equal(new Set(pages.map(p=>p.id)).size,pages.length);assert(pages.length>=20);
for(const page of pages){assert(page.title&&page.short&&page.group);assert(page.sections.length);for(const section of page.sections)assert(section.title&&(section.paragraphs.length||section.steps.length));}
const html=fs.readFileSync('backend/lokzeitleiste/static/tf-portal.html','utf8');for(const [,path]of html.matchAll(/<a class="module" href="([^"]+)"/g))assert(pages.some(p=>p.path===path||p.aliases.includes(path)),'Missing module help: '+path);
assert.equal(help.contextFor('/tf/lokuebergabebuch'),'lok');assert.equal(help.contextFor('/documents'),'dokumente');
(async()=>{
 const opener=new Element('button'),privateInput=new Element('input');privateInput.value='PRIVATE_FORM_DATA';body.append(opener,privateInput);opener.focus();help.open('arbeit');const dialog=document.getElementById('tfHelpDialog');assert(dialog.open);const [heading,status,layout]=dialog.children,[close,title,printer]=heading.children;assert.equal(close.textContent,'X');assert.equal(active,close);assert(printer.getAttribute('aria-label').includes('Anleitung drucken'));assert.equal(title.textContent,pages.find(p=>p.id==='arbeit').title);
 const search=document.getElementById('tfHelpSearch'),nav=layout.children[0].children.at(-1);search.value='zzzznothing';search.oninput();assert.equal(nav.querySelectorAll('[data-help-topic]').length,0);search.value='GPS';search.oninput();assert(nav.querySelectorAll('[data-help-topic]').length>0);const gps=nav.querySelectorAll('[data-help-topic]').find(b=>b.dataset.helpTopic==='gps');gps.onclick();assert.equal(gps.getAttribute('aria-current'),'page');assert(title.textContent.includes('GPS'));
 await printer.onclick();assert.equal(printed,1);assert.equal(privateInput.value,'PRIVATE_FORM_DATA');events.afterprint();assert(!body.classList.contains('tf-help-printing'));assert.equal(document.title,'Private Arbeitsseite');
 window.AndroidPortal={printHelp:async values=>nativePayload=values};await printer.onclick();assert(nativePayload.title.includes('GPS'));assert(nativePayload.text.includes('1. '));assert(!nativePayload.text.includes('PRIVATE_FORM_DATA'));delete window.AndroidPortal;
 close.onclick();assert.equal(dialog.open,false);assert.equal(active,opener);help.open('konto');let cancelled=false;dialog.events.cancel({preventDefault(){cancelled=true;}});assert(cancelled);assert.equal(dialog.open,false);
 const hub=new Element('div');body.append(hub);help.mountHub(hub);help.mountHub(hub);assert.equal(hub.children.length,2);assert(document.getElementById('tfHelpHubSearch'));
 console.log('TF help: complete module registry, grouped search, overlay/focus/X, browser and Android print isolation, and help hub: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
