const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag,text=''){this.tag=tag;this.textContent=text;this.children=[];this.value='';this.dataset={};this.disabled=false;this.hidden=false;}
 append(...nodes){for(const child of nodes){child.parentElement?.removeChild(child);this.children.push(child);child.parentElement=this;}}
 prepend(...nodes){for(const child of [...nodes].reverse()){child.parentElement?.removeChild(child);this.children.unshift(child);child.parentElement=this;}}
 removeChild(child){this.children.splice(this.children.indexOf(child),1);child.parentElement=null;}
 replaceChildren(){this.children=[];}
 querySelectorAll(selector){const tags=selector.split(',');return this.children.flatMap(c=>[...(tags.includes(c.tag)?[c]:[]),...c.querySelectorAll(selector)]);}
 focus(){} reportValidity(){return true;} reset(){for(const input of this.querySelectorAll('input'))input.value='';}
}
const root=new Element('div'),message=new Element('p'),rows=[{id:1,kind:'category',label:'Bremse',hotline_name:'Technik',hotline_email:'technik@example.com',revision:1},{id:2,kind:'damage',parent_id:1,label:'Vorne',revision:1},{id:3,kind:'category',label:'Antrieb',revision:1},{id:4,kind:'damage',parent_id:3,label:'Motor',revision:1},{id:5,kind:'pzb',label:'PZB Test',revision:1},{id:6,kind:'recipient',label:'Empfänger',email:'mail@example.com',revision:1}];let written;
const response=data=>({ok:true,status:200,json:async()=>data});
const context={document:{getElementById:id=>id==='locoDefaults'?root:message,createElement:tag=>new Element(tag)},window:{},Option:function(text,value){const e=new Element('option',text);e.value=value;return e;},fetch:async(path,options)=>{if(path==='/api/v1/admin/me')return response({permissions:{app_defaults:2}});if(options?.body){written=JSON.parse(options.body);return response({id:9,...written});}return response(rows);},location:{},console};
const section=title=>root.children.find(s=>s.children.some(c=>c.tag==='h3'&&c.textContent===title));
const inputs=el=>el.querySelectorAll('input'),tick=()=>new Promise(r=>setTimeout(r,0));
(async()=>{
 vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/loco-handover-defaults.js','utf8'),context);await tick();
 assert.equal(root.children.length,3);
 let category=section('Kategorie Störung');assert.equal(inputs(category)[0].parentElement.textContent,'Name Hotline');assert.equal(inputs(category)[2].maxLength,100);
 assert.equal(inputs(category)[3].disabled,true);
 category.querySelectorAll('select')[0].value='1';category.querySelectorAll('select')[0].onchange();
 category=section('Kategorie Störung');assert.equal(inputs(category)[2].value,'Bremse');assert.equal(inputs(category)[0].value,'Technik');
 let list=category.querySelectorAll('select')[1];assert.equal(list.size,5);assert.deepEqual(list.children.map(o=>o.textContent),['Bitte auswählen','Vorne']);
 list.value='2';list.onchange();assert.equal(inputs(category)[3].value,'Vorne');inputs(category)[3].value='Hinten';await category.querySelectorAll('form')[1].onsubmit({preventDefault(){}});assert.equal(written.parent_id,1);assert.equal(written.expected_revision,1);
 category=section('Kategorie Störung');category.querySelectorAll('select')[0].value='3';category.querySelectorAll('select')[0].onchange();category=section('Kategorie Störung');assert.deepEqual(category.querySelectorAll('select')[1].children.map(o=>o.textContent),['Bitte auswählen','Motor']);assert.equal(inputs(category)[3].value,'');
 const pzb=section('PZB Gründe'),pick=pzb.querySelectorAll('select')[0];pick.value='5';pick.onchange();assert.equal(inputs(pzb)[0].value,'PZB Test');assert.equal(inputs(pzb)[0].maxLength,255);
 const recipients=section('Meldung an');recipients.querySelectorAll('tbody')[0].children[0].onclick();assert.equal(inputs(recipients)[0].value,'Empfänger');assert.equal(inputs(recipients)[1].value,'mail@example.com');assert.equal(inputs(recipients)[1].type,'email');
 console.log('Handover defaults UI: hotline order, field limits, selection/editing, category-scoped damage list and saved parent/revision passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
