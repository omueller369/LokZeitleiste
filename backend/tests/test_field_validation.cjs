const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('backend/lokzeitleiste/static/auth-session.js','utf8').split('/* Shared field feedback')[1];
class Field{
 constructor(name,value=''){this.name=name;this.id='';this.value=value;this.type='text';this.dataset={};this.attributes={};this.willValidate=true;this.validity={valid:true};this.labels=[];}
 getAttribute(key){return this.attributes[key]??null;}
 setAttribute(key,value){this.attributes[key]=value;}
 removeAttribute(key){delete this.attributes[key];}
 closest(){return null;}
 matches(){return true;}
}
const a=new Field('email','bad'),b=new Field('new_password','secret'),c=new Field('email','other');
const fields=[a,b,c],events={},scope={isConnected:true,querySelectorAll:()=>fields};
const document={querySelectorAll:()=>fields,addEventListener:(key,fn)=>events[key]=fn};
const window={};vm.runInNewContext('/* Shared field feedback'+source,{window,document,console,FormData});
const api=window.CtlValidation;
(async()=>{
 a.validity.valid=false;events.invalid({target:a});assert.equal(a.getAttribute('aria-invalid'),'true');
 a.validity.valid=true;a.value='valid@example.org';events.input({target:a});assert.equal(a.getAttribute('aria-invalid'),null);
 b.setAttribute('aria-invalid','true');api.mark(b);events.input({target:b});assert.equal(b.getAttribute('aria-invalid'),'true','Preserve validation owned by another module');
 b.removeAttribute('aria-invalid');
 a.value='first';c.value='second';events.click({target:{closest:()=>scope}});
 const snapshot=api.capture({body:JSON.stringify({addresses:[{email:'first'},{email:'second'}]})});
 await api.response(new Response(JSON.stringify({detail:[{loc:['body','addresses',1,'email'],msg:'Bad email'}]}),{status:422}),snapshot);
 assert.equal(c.getAttribute('aria-invalid'),'true');assert.equal(a.getAttribute('aria-invalid'),null);
 api.clear(c);
 const old=api.capture({body:JSON.stringify({new_password:'secret'})});
 b.value='newer';await api.response(new Response(JSON.stringify({detail:[{loc:['body','new_password'],msg:'Rejected'}]}),{status:422}),old);
 assert.equal(b.getAttribute('aria-invalid'),null,'Late response must not mark edited values');
 const current=api.capture({body:JSON.stringify({new_password:'newer'})});
 await api.response(new Response(JSON.stringify({detail:[{loc:['body','new_password'],msg:'Rejected'}]}),{status:422}),current);
 assert.equal(b.getAttribute('data-ctl-invalid'),'true');
 events.reset({target:scope});assert.equal(b.getAttribute('data-ctl-invalid'),null);
 const css=fs.readFileSync('backend/lokzeitleiste/static/portal-theme.css','utf8');
 assert(css.includes(':invalid,[aria-invalid=true],[data-invalid=true],[data-ctl-invalid=true]'));
 assert(css.includes('border-color:#ff8585!important'));
 console.log('Field errors: native validity, correction, module ownership, repeated rows, stale responses, reset and dark theme passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
