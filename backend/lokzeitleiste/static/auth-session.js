/* Apply the saved appearance in the head, before page content is painted. */
(()=>{const root=document.documentElement;if(!root)return;let mode='light';try{if(localStorage.getItem('ctl.portal.theme')==='dark')mode='dark';}catch{}root.dataset.theme=mode;root.style.colorScheme=mode;
const css=document.createElement('link');css.id='portalThemeStyles';css.rel='stylesheet';css.href='/theme.css?v=20261108-validation-02619';document.head.append(css);
const script=document.createElement('script');script.src='/theme.js?v=20261108-validation-02619';document.head.append(script);})();
/* Per-tab bearer credentials keep TF and backend logins independent. */
(()=>{const native=window.fetch.bind(window);let area=location.pathname.startsWith('/tf')?'tf':location.pathname.startsWith('/admin')?'backend':new URLSearchParams(location.search).get('area')||sessionStorage.getItem('ctl.area')||'backend';sessionStorage.setItem('ctl.area',area);const key=a=>'ctl.session.'+a;
window.fetch=async(input,options={})=>{const url=new URL(typeof input==='string'?input:input.url,location.href),headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));if(url.origin===location.origin&&url.pathname.startsWith('/api/')&&!url.pathname.endsWith('/login')){headers.set('X-CTL-Area',area);const token=sessionStorage.getItem(key(area));if(token&&!headers.has(globalThis.CtlText.source("backend_auth_session.text_ca5839e38a15")))headers.set(globalThis.CtlText.source("backend_auth_session.text_ca5839e38a15"),globalThis.CtlText.source("backend_auth_session.text_35e5a9632e18")+token);}const validation=window.CtlValidation?.capture(options);const response=await native(input,{...options,headers});if(validation&&url.origin===location.origin&&url.pathname.startsWith('/api/'))await window.CtlValidation.response(response,validation);if(url.origin===location.origin&&response.ok&&options.method==='POST'){if(url.pathname.endsWith('/login')){const data=await response.clone().json();if(data.access_token){area=data.role==='tf'||url.pathname==='/api/v1/tf/login'?'tf':'backend';sessionStorage.setItem('ctl.area',area);sessionStorage.setItem(key(area),data.access_token);}}else if(url.pathname.endsWith('/logout')||url.pathname==='/api/v1/account/password'){sessionStorage.removeItem(key(area));}}return response;};
// Load the same static help on every TF page, including packaged Android pages.
let helpTask;
window.loadTfHelp=()=>{
 if(window.TfHelp)return Promise.resolve(window.TfHelp);
 if(helpTask)return helpTask;
 helpTask=new Promise((resolve,reject)=>{
  if(!document.getElementById('tfHelpStyles')){const css=document.createElement('link');css.id='tfHelpStyles';css.rel='stylesheet';css.href='/tf/help.css?v=20261108-validation-02619';document.head.append(css);}
  const load=path=>new Promise((done,fail)=>{const script=document.createElement('script');script.src=path;script.onload=done;script.onerror=()=>{script.remove();fail(Error(globalThis.CtlText.source("backend_auth_session.text_6227b32686e3")));};document.head.append(script);});
  (window.TfHelpPages?Promise.resolve():load('/tf/help-content.js?v=20261110-month-02633')).then(()=>load('/tf/help.js?v=20261108-validation-02619')).then(()=>resolve(window.TfHelp),reject);
 }).catch(error=>{helpTask=null;throw error;});return helpTask;
};
// Downloads need the same tab identity as API requests, rather than shared cookies.
function downloadName(header,fallback){const extended=header.match(/filename\*\s*=\s*(?:"([^"]+)"|([^;]+))/i);if(extended){const value=(extended[1]||extended[2]).trim(),encoded=value.match(/^UTF-8'[^']*'(.*)$/i);if(encoded){try{return decodeURIComponent(encoded[1]);}catch{}}}const plain=header.match(/filename\s*=\s*(?:"([^"]+)"|([^;]+))/i);return (plain?.[1]||plain?.[2]||fallback||globalThis.CtlText.source("backend_auth_session.text_836ae9356297")).trim();}
document.addEventListener('click',async event=>{const link=event.target.closest?.('a[href]');if(!link||event.defaultPrevented)return;const url=new URL(link.href,location.href);if(url.origin!==location.origin||!url.pathname.startsWith('/api/')||!sessionStorage.getItem(key(area)))return;event.preventDefault();try{const response=await fetch(url.href);if(!response.ok)throw Error(globalThis.CtlText.source("backend_auth_session.text_e29111b10e59"));const object=URL.createObjectURL(await response.blob()),anchor=document.createElement('a');anchor.href=object;anchor.download=link.download||downloadName(response.headers.get('Content-Disposition')||'',url.pathname.split('/').pop());anchor.click();setTimeout(()=>URL.revokeObjectURL(object),10000);}catch(error){alert(error.message);}});
document.addEventListener('DOMContentLoaded',()=>{if((location.pathname.startsWith('/tf')||location.pathname.startsWith('/admin'))&&!location.pathname.endsWith('/install')||['/documents','/my/worktime','/account'].includes(location.pathname)){const shell=document.createElement('script');shell.src='/tf/shell.js?v=20261108-validation-02619';document.head.append(shell);}if(window.NativePortal||window.AndroidPortal)return;const script=document.createElement('script');script.src='/pwa/install.js?v=20261104-rail-0263';document.head.append(script);},{once:true});
})();

/* Shared field feedback for all web and packaged Android modules. */
(()=>{
if(window.CtlValidation||!document.querySelectorAll)return;
const selector='input:not([type="hidden"]),select,textarea',owned=new WeakMap();
let actionScope=null;
const normalize=value=>String(value||'').replace(/[^a-z0-9]/gi,'').toLowerCase();
const controls=scope=>[...(scope||document).querySelectorAll(selector)];
const value=field=>field.type==='checkbox'||field.type==='radio'?String(field.checked):String(field.value??'');
const visible=field=>!field.closest('[hidden]')&&field.type!=='hidden';
function mark(field,message=''){
 if(!field||!visible(field))return;
 if(!owned.has(field))owned.set(field,{aria:field.getAttribute('aria-invalid'),value:value(field)});
 const state=owned.get(field);state.value=value(field);
 field.setAttribute('data-ctl-invalid','true');field.setAttribute('aria-invalid','true');
 if(message)field.setAttribute('data-ctl-error',String(message));
}
function clear(field){
 const state=owned.get(field);if(!state)return;
 field.removeAttribute('data-ctl-invalid');field.removeAttribute('data-ctl-error');
 if(state.aria===null)field.removeAttribute('aria-invalid');else field.setAttribute('aria-invalid',state.aria);
 owned.delete(field);
}
function validate(scope=document){
 const invalid=controls(scope).filter(field=>visible(field)&&field.willValidate&&field.validity&&!field.validity.valid);
 invalid.forEach(field=>mark(field,field.validationMessage));return invalid;
}
function fields(scope,keys){
 const wanted=keys.map(normalize);
 return controls(scope).filter(field=>{
  const names=[field.name,field.id,field.dataset.field,field.dataset.validationField,field.dataset.validationPath];
  return names.some(name=>wanted.includes(normalize(name)));
 });
}
function capture(options={}){
 let payload=options.body;
 try{if(typeof payload==='string')payload=JSON.parse(payload);}catch{payload=null;}
 if(typeof FormData!=='undefined'&&payload instanceof FormData)payload=Object.fromEntries(payload.entries());
 if(typeof payload?.payload==='string'){try{payload=JSON.parse(payload.payload);}catch{}}
 const scope=actionScope?.isConnected?actionScope:document;
 return {scope,payload,entries:controls(scope).filter(visible).map(field=>({field,value:value(field)}))};
}
function locate(snapshot,path){
 const parts=path.filter(part=>!['body','query','path'].includes(part)),key=parts.at(-1);
 let exact=fields(snapshot.scope,[parts.join('.')]);
 if(exact.length)return exact;
 let candidates=fields(snapshot.scope,[key]);
 if(!candidates.length&&normalize(key).length>=5)candidates=controls(snapshot.scope).filter(field=>normalize(field.id).endsWith(normalize(key)));
 // Forms use explicit data-validation-path for repeated nested fields.
 if(candidates.length>1){
  const input=parts.reduce((object,part)=>object?.[part],snapshot.payload);
  const matching=candidates.filter(field=>String(field.value)===String(input));
  candidates=matching.length===1?matching:[];
 }
 return candidates;
}
function messageFields(message,scope){
 const text=String(message).toLocaleLowerCase();
 return controls(scope).filter(field=>{
  const label=field.getAttribute('aria-label')||[...(field.labels||[])].map(label=>label.textContent).join(' ');
  const caption=label.trim().replace(/\s+/g,' ').replace(/[:*]\s*$/,'').toLocaleLowerCase();
  const short=caption.split('(')[0].trim();
  return short.length>=4&&text.includes(short);
 });
}
function report(message,targets){
 validate(actionScope?.isConnected?actionScope:document);
 for(const field of targets||messageFields(message,actionScope?.isConnected?actionScope:document))mark(field,message);
}
async function response(response,snapshot){
 if(response.ok||![400,401,403,409,422].includes(response.status))return;
 let data;try{data=await response.clone().json();}catch{return;}
 const errors=Array.isArray(data.detail)?data.detail:Array.isArray(data.errors)?data.errors:[];
 for(const error of errors){
  const targets=locate(snapshot,error.loc||error.path||[]);
  for(const field of targets){
   const captured=snapshot.entries.find(entry=>entry.field===field);
   if(captured&&captured.value===value(field))mark(field,error.msg||error.message);
  }
 }
 if(typeof data.detail==='string'){
  for(const field of messageFields(data.detail,snapshot.scope)){
   const captured=snapshot.entries.find(entry=>entry.field===field);
   if(captured&&captured.value===value(field))mark(field,data.detail);
  }
 }
 // Failed credentials concern the pair, while transport failures have no field.
 if(response.status===401&&snapshot.payload?.password!==undefined){
  for(const field of fields(snapshot.scope,['username','password'])){
   const captured=snapshot.entries.find(entry=>entry.field===field);
   if(captured&&captured.value===value(field))mark(field,typeof data.detail==='string'?data.detail:'');
  }
 }
 validate(snapshot.scope);
}
const showAlert=window.alert?.bind(window);
if(showAlert)window.alert=message=>{report(message);return showAlert(message);};
document.addEventListener('invalid',event=>mark(event.target,event.target.validationMessage),true);
for(const type of ['input','change'])document.addEventListener(type,event=>{
 const field=event.target;if(!field.matches?.(selector))return;
 clear(field);if(field.willValidate&&field.validity&&!field.validity.valid)mark(field,field.validationMessage);
});
document.addEventListener('reset',event=>{for(const field of controls(event.target))clear(field);},true);
for(const type of ['click','submit'])document.addEventListener(type,event=>{
 const scope=event.target.closest?.('form')||event.target.closest?.('dialog,section');
 if(scope)actionScope=scope;
},true);
window.CtlValidation={mark,clear,validate,fields,capture,response,report};
})();
