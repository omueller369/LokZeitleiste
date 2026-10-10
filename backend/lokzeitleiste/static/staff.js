const el=id=>document.getElementById(id);
let me=null,modules=[],users=[],current=null,resetTarget=null,dirty=false,busy=false,selectedPhoto=null;
function message(text,error=false){el('message').textContent=text;el('message').className=error?'error':'ok';el('formMessage').textContent=error?text:'';}
async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});const body=await response.json().catch(()=>({}));
 if(!response.ok){if(response.status===401)location.href='/admin';throw Error(typeof body.detail==='string'?body.detail:'Anfrage fehlgeschlagen ('+response.status+')');}return body;}
function manageable(user){return me.role==='admin'||(user.id!==me.id&&Object.entries(user.permissions).every(([m,v])=>v<=me.permissions[m]));}
async function refresh(){users=await api('/api/v1/admin/staff');el('users').replaceChildren();for(const user of users){const tr=document.createElement('tr');
 const photo=document.createElement('td');profilePhoto(photo,'staff',user.id,me.permissions.staff>=2&&(user.id===me.id||manageable(user)),user.has_photo,refresh);tr.append(photo);
 for(const value of [user.first_name+' '+user.last_name,user.username,user.cost_center,user.password_change_required?'Erforderlich':'Abgeschlossen']){const td=document.createElement('td');td.textContent=value;tr.append(td);}
 const td=document.createElement('td'),open=document.createElement('button');open.textContent=me.permissions.staff>=2&&manageable(user)?'Bearbeiten':'Ansehen';open.onclick=()=>edit(user);td.append(open);
 if(me.permissions.staff===3&&manageable(user)){const reset=document.createElement('button');reset.textContent='Passwort zurücksetzen';reset.style.margin='6px';reset.onclick=()=>{resetTarget=user;el('resetName').textContent=user.username;el('resetPassword').value='';el('resetMessage').textContent='';el('resetDialog').showModal();};td.append(reset);}tr.append(td);el('users').append(tr);}}
function addAddress(data={}){if(el('addresses').children.length>=10){message('Höchstens zehn Adressen.',true);return;}const box=document.createElement('div');box.className='address grid';
 for(const [key,label,max] of [['street','Straße',200],['house_number','Hausnummer',30],['postal_code','Postleitzahl (PLZ)',20],['city','Ort',120]]){const wrap=document.createElement('label');wrap.textContent=label;const input=document.createElement('input');input.dataset.field=key;input.required=true;input.maxLength=max;input.value=data[key]||'';input.oninput=()=>dirty=true;wrap.append(input);box.append(wrap);}
 const remove=document.createElement('button');remove.type='button';remove.textContent='Adresse entfernen';remove.onclick=()=>{if(el('addresses').children.length===1){message('Mindestens eine Adresse erforderlich.',true);return;}box.remove();dirty=true;};box.append(remove);el('addresses').append(box);}
function discard(){return !dirty||confirm('Ungespeicherte Änderungen verwerfen?');}
function edit(user=null){if(!discard())return;current=user;dirty=false;const form=el('staffForm');form.reset();el('editor').hidden=false;el('editorTitle').textContent=user?'Konto · '+user.username:'Verwaltungsmitarbeiter anlegen';
 selectedPhoto?.close();selectedPhoto=photoSelection(el('staffPhotoSelection'),user?'/api/v1/admin/staff/'+user.id+'/photo':null,!!user?.has_photo,()=>dirty=true);
 const writable=me.permissions.staff>=2&&(!user||manageable(user));
 for(const key of ['first_name','last_name','username','nationality','birth_date','cost_center'])form.elements[key].value=user?.[key]||'';
 form.elements.username.disabled=!!user||!writable;form.elements.initial_password.required=!user;el('initial').hidden=!!user;
 el('addresses').replaceChildren();for(const address of user?.addresses||[{}])addAddress(address);
 el('permissions').replaceChildren();for(const module of modules){const tr=document.createElement('tr');tr.dataset.module=module.id;const td=document.createElement('td');td.textContent=module.label;tr.append(td);
 const level=user?.permissions[module.id]||0;for(let n=1;n<=3;n++){const cell=document.createElement('td'),input=document.createElement('input');input.type='checkbox';input.dataset.level=n;input.checked=level>=n;
 input.setAttribute('aria-label',module.label+' · '+['','Lesen','Lesen und Schreiben','Administration'][n]);input.disabled=me.permissions.staff<3||n>module.maximum_level||!writable;
 input.onchange=()=>{const next=input.checked?n:n-1;tr.querySelectorAll('input').forEach(c=>c.checked=Number(c.dataset.level)<=next);dirty=true;};cell.append(input);tr.append(cell);}el('permissions').append(tr);}
 for(const input of form.querySelectorAll('input:not([type=checkbox])')){if(input.name==='username')continue;input.disabled=!writable;}
 for(const button of el('addresses').querySelectorAll('button'))button.disabled=!writable;
 el('addAddress').hidden=!writable;el('save').hidden=!writable;el('formMessage').textContent='';}
el('new').onclick=()=>edit();el('addAddress').onclick=()=>{addAddress();dirty=true;};el('cancel').onclick=()=>{if(discard()){dirty=false;el('editor').hidden=true;}};
el('staffForm').oninput=()=>dirty=true;
el('staffForm').onsubmit=async event=>{event.preventDefault();if(busy)return;busy=true;el('save').disabled=true;el('editor').inert=true;el('users').closest('section').inert=true;el('new').disabled=true;try{
 const data=Object.fromEntries(new FormData(event.target));data.photo_base64=await selectedPhoto.value();delete data.username;if(!current)data.username=event.target.elements.username.value;
 if(current)delete data.initial_password;
 data.addresses=[...el('addresses').children].map(box=>Object.fromEntries([...box.querySelectorAll('input')].map(input=>[input.dataset.field,input.value])));
 data.permissions=Object.fromEntries([...el('permissions').rows].map(tr=>[tr.dataset.module,Math.max(0,...[...tr.querySelectorAll('input:checked')].map(c=>Number(c.dataset.level)))]));
 await api('/api/v1/admin/staff'+(current?'/'+current.id:''),{method:current?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
 event.target.elements.initial_password.value='';dirty=false;el('editor').hidden=true;await refresh();message(current?'Stammdaten und Freigaben gespeichert.':'Verwaltungsmitarbeiter angelegt. Initialpasswort bitte persönlich übergeben.');
 }catch(error){message(error.message,true);}finally{busy=false;el('save').disabled=false;el('editor').inert=false;el('users').closest('section').inert=false;el('new').disabled=false;}};
el('closeReset').onclick=()=>el('resetDialog').close();
el('resetForm').onsubmit=async event=>{event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{
 await api('/api/v1/admin/accounts/'+resetTarget.id+'/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({initial_password:el('resetPassword').value})});
 el('resetPassword').value='';el('resetDialog').close();await refresh();message('Initialpasswort gesetzt. Passwortwechsel beim nächsten Login erforderlich.');
 }catch(error){el('resetMessage').textContent=error.message;}finally{button.disabled=false;}};
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
(async()=>{try{const account=await api('/api/v1/account/me');if(account.password_change_required){location.href='/account';return;}me=await api('/api/v1/admin/me');modules=await api('/api/v1/admin/modules');el('new').hidden=me.permissions.staff!==3;await refresh();if(location.pathname==='/admin/staff/new'){if(me.permissions.staff===3)edit();else message('Keine Freigabe zum Anlegen.',true);}else{const id=new URLSearchParams(location.search).get('id');const user=users.find(u=>String(u.id)===id);if(user)edit(user);}}catch(error){message(error.message,true);}})();
