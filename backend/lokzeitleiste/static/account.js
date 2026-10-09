const el = id => document.getElementById(id);
let user = null;
function message(text,error=false){el('message').textContent=text;el('message').className=error?'error':'ok';}
async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});
 const body=await response.json().catch(()=>({})); if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'Anfrage fehlgeschlagen ('+response.status+')');return body;}
async function show(){user=await api('/api/v1/account/me');el('loginForm').hidden=true;el('passwordForm').hidden=false;el('logout').hidden=false;
 el('identity').textContent='Konto: '+user.username;el('mandatory').hidden=!user.password_change_required;el('back').hidden=user.password_change_required||user.role==='tf';}
async function submit(form,fn){form.querySelector('button').disabled=true;try{await fn();}catch(error){message(error.message,true);}finally{form.querySelector('button').disabled=false;}}
el('loginForm').onsubmit=event=>{event.preventDefault();submit(event.target,async()=>{
 await api('/api/v1/account/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});
 event.target.reset();await show();message('Angemeldet.');});};
el('passwordForm').onsubmit=event=>{event.preventDefault();submit(event.target,async()=>{
 const data=Object.fromEntries(new FormData(event.target));if(data.new_password!==data.confirm_password)throw Error('Passwörter stimmen nicht überein.');
 await api('/api/v1/account/password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 event.target.reset();el('passwordForm').hidden=true;el('loginForm').hidden=false;el('logout').hidden=true;el('back').hidden=user.role==='tf';
 message('Passwort geändert. Alle bisherigen Sitzungen wurden beendet. Bitte mit dem neuen Passwort anmelden.');});};
el('logout').onclick=async()=>{try{await api('/api/v1/account/logout',{method:'POST'});location.reload();}catch(error){message(error.message,true);}};
show().catch(()=>{el('loginForm').hidden=false;el('back').hidden=true;});
