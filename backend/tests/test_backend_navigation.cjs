// Browser contract simulation: desktop sidebar, mobile modal, focus and cleanup.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let document;
class E{
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.style={};this.attributes={};this.className='';this.hidden=false;this.inert=false;this.events=new Map();const classes=()=>new Set(this.className.split(/\s+/).filter(Boolean));this.classList={add:(...names)=>{const set=classes();names.forEach(n=>set.add(n));this.className=[...set].join(' ');},remove:(...names)=>{const set=classes();names.forEach(n=>set.delete(n));this.className=[...set].join(' ');},contains:name=>classes().has(name),toggle:(name,force)=>{const set=classes(),yes=force===undefined?!set.has(name):force;if(yes)set.add(name);else set.delete(name);this.className=[...set].join(' ');return yes;}};}
 append(...children){for(const child of children){child.remove();child.parentElement=this;this.children.push(child);}}
 after(child){child.remove();child.parentElement=this.parentElement;this.parentElement.children.splice(this.parentElement.children.indexOf(this)+1,0,child);}
 prepend(child){child.remove();child.parentElement=this;this.children.unshift(child);}
 replaceChildren(){this.children.forEach(n=>n.parentElement=null);this.children=[];}
 remove(){if(this.parentElement){this.parentElement.children=this.parentElement.children.filter(n=>n!==this);this.parentElement=null;}}
 setAttribute(k,v){this.attributes[k]=String(v);}
 removeAttribute(k){delete this.attributes[k];}
 addEventListener(name,fn){if(!this.events.has(name))this.events.set(name,new Set());this.events.get(name).add(fn);}
 removeEventListener(name,fn){this.events.get(name)?.delete(fn);}
 dispatch(name,event={}){for(const fn of this.events.get(name)||[])fn(event);}
 contains(other){return flatten(this).includes(other);}
 closest(selector){for(let n=this;n;n=n.parentElement)if(selector==='[hidden]'?n.hidden:n.tagName===selector.toUpperCase())return n;return null;}
 querySelectorAll(selector){return flatten(this).slice(1).filter(n=>matches(n,selector));}
 querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 focus(){document.activeElement=this;}
 get isConnected(){return document.body.contains(this)||document.head.contains(this);}
}
function flatten(root){return [root,...root.children.flatMap(flatten)];}
function matches(n,selector){if(selector.startsWith('a[href],'))return (n.tagName==='A'&&n.href)||(n.tagName==='BUTTON'&&!n.disabled)||(n.tabIndex>=0);if(selector==='link[href^="/responsive.css"]')return n.tagName==='LINK'&&n.href?.startsWith('/responsive.css');if(selector==='link[data-backend-sidebar]')return n.tagName==='LINK'&&n.dataset.backendSidebar;if(selector.startsWith('.'))return n.classList.contains(selector.slice(1));return n.tagName===selector.toUpperCase();}
const head=new E('head'),body=new E('body'),header=new E('header'),main=new E('main'),sheet=new E('link');sheet.href='/responsive.css';head.append(sheet);body.append(header,main);body.style.overflow='auto';
document=new E('document');Object.assign(document,{body,head,activeElement:body,createElement:tag=>new E(tag),getElementById:id=>[...flatten(head),...flatten(body)].find(n=>n.id===id),querySelector:selector=>[...flatten(head),...flatten(body)].find(n=>matches(n,selector))||null});
const media=new E('media');media.matches=true;const window=new E('window');window.matchMedia=()=>media;let me={id:1,role:'staff',permissions:{planning:1,vehicles:0}},status=200,savedVariant='sidebar';
const context={document,window,location:{pathname:'/admin/start',search:'',href:'https://testserver/admin/start'},URL,URLSearchParams,console,fetch:async(url)=>({ok:status===200,status,json:async()=>url.endsWith("menu-preference")?{user_id:me.id,variant:savedVariant}:me})};
const source=fs.readFileSync('backend/lokzeitleiste/static/backend-nav.js','utf8'),tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const get=selector=>document.querySelector(selector),byId=id=>document.getElementById(id);
(async()=>{
 vm.runInNewContext(source,context);await tick();let panel=byId('backend-sidebar'),control=get('.backend-menu-control'),toggle=control.children[0],close=get('.backend-sidebar-close'),overlay=get('.backend-sidebar-overlay');
 assert(panel);assert.equal(panel.hidden,false);assert(body.classList.contains('backend-sidebar-desktop'));assert(control.hidden);assert(close.hidden);assert(overlay.hidden);
 const groups=flatten(panel).filter(n=>n.className==='menu-group-row');assert.equal(groups.length,7);assert(!flatten(panel).some(n=>n.textContent==='Administration'));for(const row of groups){const button=row.children.find(n=>n.tagName==='BUTTON'),children=row.parentElement.children[1];assert(children.hidden);button.onclick();assert.equal(children.hidden,false);button.onclick();assert(children.hidden);}
 const home=flatten(panel).find(n=>n.href==='/admin/start');assert.equal(home.attributes['aria-current'],'page');panel.dispatch('click',{target:home});assert.equal(panel.hidden,false);
 media.matches=false;media.dispatch('change');assert(panel.hidden);assert.equal(control.hidden,false);assert.equal(body.classList.contains('backend-sidebar-desktop'),false);
 toggle.focus();toggle.onclick();assert.equal(panel.hidden,false);assert.equal(panel.attributes.role,'dialog');assert.equal(panel.attributes['aria-modal'],'true');assert.equal(overlay.hidden,false);assert(main.inert&&header.inert);assert.equal(body.style.overflow,'hidden');assert.equal(document.activeElement,close);
 const logout=flatten(panel).find(n=>n.textContent==='Abmelden');logout.focus();let prevented=false;document.dispatch('keydown',{key:'Tab',shiftKey:false,preventDefault(){prevented=true;}});assert(prevented);assert.equal(document.activeElement,close);
 document.dispatch('keydown',{key:'Tab',shiftKey:true,preventDefault(){}});assert.equal(document.activeElement,logout);
 document.dispatch('keydown',{key:'Escape',preventDefault(){}});assert(panel.hidden);assert(overlay.hidden);assert.equal(main.inert,false);assert.equal(header.inert,false);assert.equal(body.style.overflow,'auto');assert.equal(document.activeElement,toggle);
 toggle.onclick();overlay.onclick();assert(panel.hidden);toggle.onclick();panel.dispatch('click',{target:home});assert(panel.hidden);assert.equal(body.style.overflow,'auto');
 toggle.focus();toggle.onclick();media.matches=true;media.dispatch('change');assert.equal(panel.hidden,false);assert(overlay.hidden);assert.equal(main.inert,false);assert(control.hidden);assert.equal(document.activeElement,home);
 vm.runInNewContext(source,context);await tick();assert.equal(flatten(body).filter(n=>n.id==='backend-sidebar').length,1);
 me={...me,permissions:{planning:1,vehicles:2}};vm.runInNewContext(source,context);await tick();assert.equal(flatten(body).filter(n=>n.id==='backend-sidebar').length,1);assert.equal(document.events.get('keydown').size,1);assert.equal(head.children.filter(n=>n.dataset.backendSidebar).length,1);
 window.dispatch('backendmenuchange',{detail:{user_id:me.id,variant:'compact'}});panel=byId('backend-sidebar');control=get('.backend-menu-control');assert(panel.hidden);assert(!control.hidden);control.children[0].onclick();assert(!panel.hidden);assert.equal(main.inert,false);document.dispatch('pointerdown',{target:main});assert(panel.hidden);
 window.dispatch('backendmenuchange',{detail:{user_id:me.id,variant:'sections'}});const bar=get('.backend-section-bar');assert(!bar.hidden);assert(control.hidden);bar.children.at(-1).onclick();assert(!panel.hidden);media.matches=false;media.dispatch('change');bar.children.at(-1).onclick();assert(main.inert);overlay=get('.backend-sidebar-overlay');overlay.onclick();assert(!main.inert);
 savedVariant='compact';vm.runInNewContext(source,context);await tick();assert.equal(byId('backend-sidebar').dataset.variant,'compact');assert(!get('.backend-menu-control').hidden);window.dispatch('backendmenuchange',{detail:{user_id:999,variant:'sections'}});assert.equal(byId('backend-sidebar').dataset.variant,'compact');
 me={...me,role:'admin'};vm.runInNewContext(source,context);await tick();assert(flatten(byId('backend-sidebar')).some(n=>n.textContent==='Administration'));
 me={...me,role:'staff'};vm.runInNewContext(source,context);await tick();assert(!flatten(byId('backend-sidebar')).some(n=>n.textContent==='Administration'));
 status=401;vm.runInNewContext(source,context);await tick();assert.equal(byId('backend-sidebar'),undefined);assert.equal(get('.backend-menu-control'),null);assert.equal(document.events.get('keydown').size,0);assert.equal(body.classList.contains('backend-sidebar-desktop'),false);
 console.log('Backend navigation: desktop sidebar, collapsed groups, mobile focus trap/Escape/backdrop, background restoration, breakpoint switching, permission refresh and cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
