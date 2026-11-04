const el = id => document.getElementById(id);
let user = null;
function message(text,error=false){el('message').textContent=text;el('message').className=error?'error':'ok';}
async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});
 const body=await response.json().catch(()=>({})); if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:globalThis.CtlText.source("backend_account.text_926e66e23dec")+response.status+')');return body;}
async function show(afterLogin=false){user=await api('/api/v1/account/me');if(afterLogin&&!user.password_change_required){location.href=user.role==='tf'?'/tf':'/admin/start';return;}el('tfPortal').hidden=user.password_change_required||user.role!=='tf';el('loginForm').hidden=true;el('passwordForm').hidden=false;el('logout').hidden=false;
 el('ownWorktime').hidden=user.password_change_required||user.role!=='staff';el('identity').textContent=globalThis.CtlText.source("backend_account.text_e1f0b92aec61")+user.username;el('mandatory').hidden=!user.password_change_required;el('back').hidden=user.password_change_required||user.role==='tf';}
async function submit(form,fn){form.querySelector('button').disabled=true;try{await fn();}catch(error){message(error.message,true);}finally{form.querySelector('button').disabled=false;}}
el('loginForm').onsubmit=event=>{event.preventDefault();submit(event.target,async()=>{
 await api('/api/v1/account/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});
 event.target.reset();await show(true);message('Angemeldet.');});};
el('passwordForm').onsubmit=event=>{event.preventDefault();submit(event.target,async()=>{
 const data=Object.fromEntries(new FormData(event.target));if(data.new_password!==data.confirm_password)throw Error(globalThis.CtlText.source("backend_account.text_89780fc834cd"));
 await api('/api/v1/account/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 el('ownWorktime').hidden=true;el('tfPortal').hidden=true;event.target.reset();el('passwordForm').hidden=true;el('loginForm').hidden=false;el('logout').hidden=true;el('back').hidden=user.role==='tf';
 message(globalThis.CtlText.source("backend_account.text_6d78631ebe51"));});};
el('logout').onclick=async()=>{try{await api('/api/v1/account/logout',{method:'POST'});location.reload();}catch(error){message(error.message,true);}};
show().catch(()=>{el('loginForm').hidden=false;el('back').hidden=true;});
