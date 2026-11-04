// Regression: asynchronously replaced header must not interrupt TF list/navigation.
const fs=require('node:fs'),vm=require('./localized-vm.cjs'),assert=require('node:assert/strict');
const source=fs.readFileSync('backend/lokzeitleiste/static/admin.js','utf8');
const html=fs.readFileSync('backend/lokzeitleiste/static/admin.html','utf8');
for(const id of ['createTfCard','employeeCard','newTfLink'])assert(new RegExp('id="'+id+'"[^>]*hidden').test(html));
class E{
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.style={};this.dataset={};this.hidden=false;this.value='';}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attrs[k]=v;}
 removeAttribute(k){delete this.attrs[k];}
 remove(){this.removed=true;}
 closest(){return new E('label');}
 addEventListener(){}
 querySelectorAll(){return [];}
 querySelector(q){if(q==='button:not([type])')return this.save;if(q==='.photo-editor')return this.photo;return null;}
 showModal(){this.open=true;}
 close(){this.open=false;this.onclose?.();}
 cloneNode(){return form();}
}
function form(){const f=new E('form');f.elements={};for(const key of ['bahncard','bahncard_valid_until','email','first_name','last_name','personnel_number','vacation_days','birth_date','driver_type','username'])f.elements[key]=new E('input');f.save=new E('button');f.photo=new E();return f;}
const tick=()=>new Promise(setImmediate);
async function scenario(path,search='',employees=3){
 const ids={};for(const id of ['login','dashboard','loginMessage','pageMessage','tfPhotoSelection','createTfCard','employeeCard','newTfLink','users','tfTypeFilter','tfSearch','tfNoResults','months','loginForm','tfMessage'])ids[id]=new E();ids.tfForm=form();ids.tfTypeFilter.value='';ids.dashboard.hidden=true;
 const body=new E('body'),grid=new E(),calls=[],metadata={};
 const document={body,getElementById:id=>ids[id]||null,createElement:tag=>new E(tag),querySelector:q=>q==='.grid'?grid:q==='dialog[data-tf-profile]'?body.children.find(n=>n.tagName==='DIALOG'&&n.attrs['data-tf-profile']&&!n.removed)||null:q==='dialog'?new E('dialog'):null};
 const users=[{id:10,first_name:'Alex',last_name:'Route',username:'123456',driver_type:'route',personnel_number:'1',email:'alex@example.test',bahncard:0},{id:11,first_name:'Sam',last_name:'Border',username:'234567',driver_type:'border',personnel_number:'2',bahncard:0}];
 const context={document,window:{employeeEmailField:async()=>{},openTfOvertime(){}},location:{pathname:path,search},URLSearchParams,console,alert:()=>{},photoSelection:()=>({close(){},value:async()=>null}),profilePhoto(){},tfDefaultValidity:()=>'',tfExtraForm:()=>({close(){},payload(){}}),fetch:async url=>{calls.push(url);return {ok:true,json:async()=>url==='/api/v1/account/me'?{role:'admin'}:url==='/api/v1/admin/me'?{permissions:{employees,reports:1,planning:1,worktime:1}}:url.endsWith('tf-metadata')?metadata:users};}};
 vm.runInNewContext(source,context);await tick();await tick();return {ids,body,calls,document};
}
(async()=>{
 // There is deliberately no legacy #logout: the shared shell has replaced it.
 const list=await scenario('/admin/tf');assert.equal(list.ids.users.children.length,2);assert(list.ids.createTfCard.hidden);assert(!list.ids.employeeCard.hidden);assert(!list.ids.newTfLink.hidden);assert(list.body.children.some(n=>n.tagName==='SCRIPT'&&n.src==='/admin/backend-nav.js'));assert(!list.ids.pageMessage.textContent);
 const requests=list.calls.length;list.ids.tfSearch.value='ALEX 123';list.ids.tfSearch.oninput();assert.equal(list.ids.users.children.length,1);list.ids.tfTypeFilter.value='border';list.ids.tfTypeFilter.onchange();assert.equal(list.ids.users.children.length,0);assert(!list.ids.tfNoResults.hidden);list.ids.tfSearch.value='';list.ids.tfSearch.oninput();assert.equal(list.ids.users.children.length,1);list.ids.tfTypeFilter.value='';list.ids.tfTypeFilter.onchange();assert.equal(list.ids.users.children.length,2);assert.equal(list.calls.length,requests,'Filtering uses loaded data');list.ids.tfSearch.value='example.test';list.ids.tfSearch.oninput();assert.equal(list.ids.users.children.length,1);list.ids.tfSearch.value='';list.ids.tfSearch.oninput();
 const actions=list.ids.users.children[0].children.at(-1).children;assert.equal(actions.length,7);for(const a of actions){assert(a.title);assert.equal(a.attrs['aria-label'],a.title);assert.equal(a.children[0].attrs['aria-hidden'],'true');}
 let prevented=false;actions[1].onclick({preventDefault(){prevented=true;}});assert(prevented);let dialog=list.document.querySelector('dialog[data-tf-profile]');assert(dialog?.open);assert.equal(dialog.children[1].save.hidden,false);dialog.close();
 actions[0].onclick({preventDefault(){}});dialog=list.document.querySelector('dialog[data-tf-profile]');assert(dialog.open);assert(dialog.children[1].save.hidden);
 const deep=await scenario('/admin/tf','?id=11&mode=edit');assert(deep.document.querySelector('dialog[data-tf-profile]')?.open,'Unrelated dialogs must not block profile deep links');
 const add=await scenario('/admin/tf/new');assert(!add.ids.createTfCard.hidden);assert(add.ids.employeeCard.hidden);assert(!add.calls.includes('/api/v1/admin/tf'));
 const readonly=await scenario('/admin/tf','',1);assert(readonly.ids.newTfLink.hidden);assert.equal(readonly.ids.users.children[0].children.at(-1).children.length,6);
 const denied=await scenario('/admin/tf/new','',1);assert(denied.ids.createTfCard.hidden);
 const planner=await scenario('/admin/tf','',null);assert(planner.ids.newTfLink.hidden);planner.ids.tfSearch.value='example.test';planner.ids.tfSearch.oninput();assert.equal(planner.ids.users.children.length,0,'Hidden email must not be searchable');
 console.log('TF administration: header race, immediate all-driver list, explicit create route, direct view/edit, deep links and accessible permission-aware action icons passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
