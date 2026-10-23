(async()=>{
 const root=document.getElementById('locoDefaults'),t=s=>window.I18n?.t(s)||s;
 const node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=t(text);return e;};
 const base='/api/v1/admin/app-defaults/loco-handover';let rows=[],level=0,busy=false,selectedCategory=null;
 const message=document.getElementById('locoDefaultsMessage');
 async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...options}),data=await r.json().catch(()=>({}));if(r.status===401){location.href='/account';throw Error('Anmeldung erforderlich');}if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:'Bitte die Eingaben und Pflichtfelder prüfen.');return data;}
 function field(form,label,max,type='text'){const wrap=node('label',label),input=node('input');input.type=type;input.maxLength=max;input.disabled=level<2;wrap.append(input);form.append(wrap);return input;}
 function editor(section,kind,title,limit){
  const form=node('form'),label=field(form,title,limit),save=node('button','Hinzufügen'),fresh=node('button','Neu'),actions=node('div');label.required=true;save.type='submit';fresh.type='button';actions.className='actions';actions.append(save,fresh);actions.hidden=level<2;let current=null;
  const fields={label};
  function reset(){current=null;form.reset();save.textContent=t('Hinzufügen');}
  function load(row){current=row;for(const [key,input] of Object.entries(fields))input.value=row[key]||'';save.textContent=t('Speichern');}
  fresh.onclick=()=>{reset();if(kind==='category'){selectedCategory=null;draw();}};
  form.onsubmit=async event=>{event.preventDefault();if(busy||level<2||!form.reportValidity())return;if(kind==='damage'&&!selectedCategory)return;
   const data=Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value]));if(kind==='damage')data.parent_id=selectedCategory;if(current)data.expected_revision=current.revision;
   busy=true;root.querySelectorAll('button').forEach(b=>b.disabled=true);message.textContent='';
   try{const saved=await api(base+(current?'/value/'+current.id:'/'+kind),{method:current?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(kind==='category')selectedCategory=saved.id;rows=await api(base);draw();message.textContent=t('Gespeichert');}catch(error){message.textContent=t(error.message);}finally{busy=false;root.querySelectorAll('button').forEach(b=>b.disabled=false);}
  };
  section.append(form);return {form,fields,actions,load};
 }
 function picker(section,values,onchange,list=false){const label=node('label',list?'Eingrenzungen der Schadstelle':'Vorhandene Einträge'),select=node('select');if(list)select.size=5;select.append(new Option(t('Bitte auswählen'),''));for(const row of values){const option=new Option(row.label,String(row.id));option.dataset.i18nIgnore='';select.append(option);}select.onchange=()=>onchange(values.find(row=>row.id===Number(select.value))||null);label.append(select);section.append(label);return select;}
 function draw(){root.replaceChildren();
  const recipients=node('section');recipients.className='card';recipients.append(node('h3','Meldung an'));const r=editor(recipients,'recipient','Name',255);r.fields.email=field(r.form,'Emailadresse',254,'email');r.fields.email.required=true;r.form.append(r.actions);
  const wrap=node('div'),table=node('table'),head=node('tr');wrap.className='tablewrap';for(const title of ['Name','Emailadresse'])head.append(node('th',title));const thead=node('thead');thead.append(head);table.append(thead);const body=node('tbody');for(const row of rows.filter(r=>r.kind==='recipient')){const tr=node('tr'),name=node('td'),email=node('td'),button=node('button');button.type='button';button.textContent=row.label;button.dataset.i18nIgnore='';button.onclick=()=>{r.load(row);r.fields.label.focus();};name.append(button);email.textContent=row.email;email.dataset.i18nIgnore='';tr.append(name,email);tr.onclick=()=>r.load(row);body.append(tr);}table.append(body);wrap.append(table);recipients.append(wrap);root.append(recipients);
  const pzb=node('section');pzb.className='card';pzb.append(node('h3','PZB Gründe'));const p=editor(pzb,'pzb','Grund',255);p.form.append(p.actions);picker(pzb,rows.filter(r=>r.kind==='pzb'),row=>{if(row)p.load(row);});root.append(pzb);
  const category=node('section');category.className='card';category.append(node('h3','Kategorie Störung'));const c=editor(category,'category','Kategorie Störung',100);c.fields.hotline_name=field(c.form,'Name Hotline',255);c.fields.hotline_email=field(c.form,'Emailadresse',254,'email');c.form.prepend(c.fields.hotline_name.parentElement,c.fields.hotline_email.parentElement);c.form.append(c.actions);
  const categories=rows.filter(r=>r.kind==='category');const select=picker(category,categories,row=>{selectedCategory=row?.id||null;draw();});
  const current=categories.find(r=>r.id===selectedCategory);if(current){c.load(current);select.value=String(current.id);}
  if(categories.length){const damage=node('div'),d=editor(damage,'damage','Eingrenzung der Schadstelle',255);d.form.append(d.actions);if(!current){d.fields.label.disabled=true;d.actions.hidden=true;damage.append(node('p','Bitte zuerst eine vorhandene Kategorie auswählen.'));}picker(damage,rows.filter(r=>r.kind==='damage'&&r.parent_id===selectedCategory),row=>{if(row)d.load(row);},true);category.append(damage);}
  root.append(category);
 }
 try{const me=await api('/api/v1/admin/me');level=me.permissions.app_defaults||0;if(!level){root.hidden=true;return;}rows=await api(base);draw();}catch(error){message.textContent=t(error.message);}
})();
