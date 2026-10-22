(async()=>{
const el=id=>document.getElementById(id),t=s=>window.I18n?.t(s)||s,node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=t(text);return e;};
let level=0,rows=[],busy=false;
function message(s){el('defaultsMessage').textContent=t(s);}
async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...options}),data=await r.json().catch(()=>({}));if(r.status===401){location.href='/account';throw Error('Anmeldung erforderlich');}if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Bitte die Eingaben und Pflichtfelder prüfen.');return data;}
async function reload(){rows=await api('/api/v1/admin/app-defaults');draw();}
async function run(fn){if(busy)return;busy=true;el('defaultsSections').querySelectorAll('button,input').forEach(e=>e.disabled=true);try{message('');await fn();await reload();}catch(error){message(error.message);}finally{busy=false;el('defaultsSections').querySelectorAll('button,input').forEach(e=>e.disabled=false);}}
function draw(){el('defaultsSections').replaceChildren();for(const [category,title] of [['reason','Standzeit Grund'],['cause','Zugfahrt Art']]){
 const section=node('section');section.className='card';section.append(node('h2',title));
 const form=node('form'),name=node('input'),active=node('input'),label=node('label','Bezeichnung'),enabled=node('label','Als Auswahl verfügbar'),save=node('button','Hinzufügen'),cancel=node('button','Abbrechen');name.type='text';name.maxLength=200;name.required=true;active.type='checkbox';active.checked=true;label.append(name);enabled.prepend(active);save.type='submit';cancel.type='button';cancel.hidden=true;let current=null;
 function reset(){current=null;form.reset();active.checked=true;save.textContent=t('Hinzufügen');cancel.hidden=true;}
 cancel.onclick=reset;form.append(label,enabled,save,cancel);form.hidden=level<2;form.onsubmit=event=>{event.preventDefault();if(level<2||!form.reportValidity())return;run(()=>api('/api/v1/admin/app-defaults/'+(current?'value/'+current.id:category),{method:current?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:name.value,active:active.checked,...(current?{expected_revision:current.revision}:{})})}));};section.append(form);
 const wrap=node('div'),table=node('table'),head=node('thead'),tr=node('tr');wrap.className='tablewrap';for(const title of ['Bezeichnung','Als Auswahl verfügbar','Verwendet','Aktionen'])tr.append(node('th',title));head.append(tr);table.append(head);const body=node('tbody');
 for(const value of rows.filter(row=>row.category===category)){
 const row=node('tr');row.dataset.inactive=String(!value.active);row.append(node('td',value.label),node('td',value.active?'Ja':'Nein'),node('td',value.used?'Ja':'Nein'));row.children[0].setAttribute('data-i18n-ignore','');const actions=node('td');actions.className='actions';
 if(level>=2){const edit=node('button','Bearbeiten');edit.type='button';edit.onclick=()=>{current=value;name.value=value.label;active.checked=value.active;save.textContent=t('Speichern');cancel.hidden=false;name.focus();};actions.append(edit);}
 if(level>=3&&!value.used){const remove=node('button','Löschen');remove.type='button';remove.onclick=()=>{if(confirm(t('Eintrag entfernen?')))run(()=>api('/api/v1/admin/app-defaults/value/'+value.id+'?expected_revision='+value.revision,{method:'DELETE'}));};actions.append(remove);}
 if(level>=2&&value.active){const deactivate=node('button','Deaktivieren');deactivate.type='button';deactivate.onclick=()=>run(()=>api('/api/v1/admin/app-defaults/value/'+value.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({label:value.label,active:false,expected_revision:value.revision})}));actions.append(deactivate);}
 row.append(actions);body.append(row);
 }table.append(body);wrap.append(table);section.append(wrap);el('defaultsSections').append(section);
}}
try{const me=await api('/api/v1/admin/me');level=me.permissions.app_defaults||0;if(!level)throw Error('Keine ausreichende Freigabe für dieses Modul.');await reload();}catch(error){message(error.message);}
})();
