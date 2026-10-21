(()=>{
const categories=[['landline','Festnetz'],['mobile','Mobilnetz'],['bada','Bada-Nummer'],['long_dial','Langwahl'],['local_radio','Ortsfunk/Kurzwahl']];
const el=id=>document.getElementById(id),t=value=>window.I18n?.t(value)||value;
const node=(tag,value)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;return n;};
const selectedStations=new Set();
let current=null,editing=false,dirty=false,busy=false,listVersion=0,catalogVersion=0,listTimer,catalogTimer;
function message(value){el('stationMessage').textContent=value;}
function selectionCount(){el('stationShareCount').textContent=String(selectedStations.size);}
async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});const data=await response.json().catch(()=>({}));if(response.status===401){location.href='/account';throw Error('Anmeldung erforderlich');}if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Anfrage fehlgeschlagen ('+response.status+')');return data;}
const base=id=>'/api/v1/tf/stations'+(id?'/'+id:'');
function pending(){return dirty||el('stationPlanFile').files.length>0;}
function canLeave(){return !pending()||confirm(t('Ungespeicherte Änderungen verwerfen?'));}
function modeControls(){el('stationContacts').querySelectorAll('input').forEach(input=>input.readOnly=!editing);el('stationContacts').querySelectorAll('button').forEach(button=>button.hidden=!editing);el('stationSave').hidden=!editing;el('stationCancel').hidden=!editing;el('stationEdit').hidden=editing;el('stationPlanControls').hidden=!editing;el('stationDelete').hidden=!editing;}
async function run(action){if(busy)return;busy=true;el('stationWorkspace').inert=true;message('');try{await action();}catch(error){message(error.message);}finally{busy=false;el('stationWorkspace').inert=false;}}
function addContact(group,category,data={label:'',number:''}){
 if(el('stationContacts').querySelectorAll('.station-contact-row').length>=100){message(t('Höchstens 100 Nummern pro Bahnhof.'));return;}
 const row=node('div');row.className='station-contact-row';row.dataset.category=category;
 const label=node('label',t('Bezeichnung')),name=node('input');name.value=data.label;name.required=true;name.maxLength=100;name.readOnly=!editing;label.append(name);
 const numberLabel=node('label',t('Nummer')),number=node('input');number.type='tel';number.value=data.number;number.required=true;number.maxLength=60;number.readOnly=!editing;numberLabel.append(number);
 const remove=node('button',t('Entfernen'));remove.type='button';remove.hidden=!editing;remove.onclick=()=>{row.remove();dirty=true;};
 for(const input of [name,number])input.addEventListener('input',()=>{dirty=true;});row.append(label,numberLabel,remove);group.append(row);
}
function render(data,edit=false){
 current=data;editing=edit;dirty=false;el('stationDetails').hidden=!data;el('stationPlanFile').value='';if(!data)return;
 el('stationDetailTitle').textContent=data.code+' · '+data.name;el('stationContacts').replaceChildren();
 for(const [category,title] of categories){const box=node('fieldset'),legend=node('legend',t(title)),rows=node('div'),add=node('button',t('Nummer hinzufügen'));add.type='button';add.onclick=()=>{addContact(rows,category);dirty=true;};legend.append(add);box.append(legend,rows);for(const contact of data.contacts.filter(c=>c.category===category))addContact(rows,category,contact);el('stationContacts').append(box);}
 const plan=el('stationPlanLink');plan.hidden=!data.plan;plan.href=base(data.id)+'/plan';plan.textContent=data.plan?data.plan.filename:'';
 el('stationPlanEmpty').hidden=!!data.plan;el('stationPlanDelete').hidden=!data.plan;modeControls();
 for(const row of el('stationList').querySelectorAll('button'))row.setAttribute('aria-current',String(row.dataset.id===String(data.id)));
}
async function loadList(){const version=++listVersion,q=el('stationSearch').value;try{const rows=await api(base()+'?q='+encodeURIComponent(q));if(version!==listVersion)return;el('stationList').replaceChildren();el('stationEmpty').hidden=rows.length>0;for(const station of rows){const item=node('li'),selection=node('input'),button=node('button'),code=node('strong',station.code),name=node('span',station.name);item.className='station-select-row';selection.type='checkbox';selection.className='station-share-check';selection.checked=selectedStations.has(station.id);selection.setAttribute('aria-label',t('Zum Teilen auswählen')+' '+station.code+' '+station.name);selection.onchange=()=>{if(selection.checked)selectedStations.add(station.id);else selectedStations.delete(station.id);selectionCount();};selection.dataset.id=station.id;button.type='button';button.className='station-option';button.dataset.id=station.id;button.setAttribute('data-i18n-ignore','');button.setAttribute('aria-current',String(station.id===current?.id));button.append(code,name);button.onclick=()=>{if(!busy&&canLeave())run(async()=>{const data=await api(base(station.id));render(data);el('stationPicker').hidden=true;el('stationDetails').scrollIntoView?.({behavior:'smooth',block:'nearest'});});};item.append(selection,button);el('stationList').append(item);}}catch(error){if(version===listVersion)message(error.message);}}
async function searchCatalog(){const version=++catalogVersion,q=el('stationCatalogSearch').value.trim();el('stationCatalogResults').replaceChildren();el('stationCatalogEmpty').hidden=true;if(!q)return;try{const rows=await api(base()+'/catalog?q='+encodeURIComponent(q));if(version!==catalogVersion||el('stationPicker').hidden)return;el('stationCatalogEmpty').hidden=rows.length>0;for(const station of rows){const item=node('li'),button=node('button',station.code+' · '+station.name);button.type='button';button.setAttribute('data-i18n-ignore','');button.onclick=()=>run(async()=>{if(!canLeave())return;const data=await api(base(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:station.code,contacts:[]})});render(data,true);el('stationPicker').hidden=true;el('stationSearch').value='';await loadList();});item.append(button);el('stationCatalogResults').append(item);}}catch(error){if(version===catalogVersion)message(error.message);}}
window.startStationDirectory=async()=>{
 el('stationNew').onclick=()=>{if(busy||!canLeave())return;if(current)render(current);el('stationPicker').hidden=false;el('stationCatalogSearch').value='';el('stationCatalogResults').replaceChildren();el('stationCatalogEmpty').hidden=true;el('stationCatalogSearch').focus();};
 el('stationPickerCancel').onclick=()=>{el('stationPicker').hidden=true;catalogVersion++;};
 el('stationSearch').oninput=()=>{clearTimeout(listTimer);listVersion++;listTimer=setTimeout(loadList,250);};el('stationReload').onclick=()=>{if(!busy)loadList();};
 el('stationCatalogSearch').oninput=()=>{clearTimeout(catalogTimer);catalogVersion++;catalogTimer=setTimeout(searchCatalog,250);};
 el('stationEdit').onclick=()=>{if(!busy&&current){editing=true;modeControls();}};
 el('stationCancel').onclick=()=>{if(!busy&&current&&canLeave())render(current);};
 el('stationContactForm').onsubmit=event=>{event.preventDefault();if(!current||!editing||busy||!event.target.reportValidity())return;run(async()=>{const contacts=Array.from(el('stationContacts').querySelectorAll('.station-contact-row')).map(row=>{const fields=row.querySelectorAll('input');return {category:row.dataset.category,label:fields[0].value,number:fields[1].value};});const planFile=el('stationPlanFile').files[0];const data=await api(base(current.id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:current.revision,contacts})});if(planFile){current=data;dirty=false;message(t('Kontakte gespeichert. Den gewählten Plan jetzt hochladen.'));}else{render(data);message(t('Bahnhof gespeichert.'));}});};
 el('stationPlanUpload').onclick=()=>{if(!current||!editing||busy)return;run(async()=>{if(dirty)throw Error(t('Bitte zuerst die Kontaktdaten speichern.'));const file=el('stationPlanFile').files[0];if(!file)throw Error(t('Bitte einen Bahnhofsplan wählen.'));if(file.size>10*1024*1024)throw Error(t('Dokument darf höchstens 10 MB groß sein.'));const form=new FormData();form.append('file',file);form.append('expected_revision',String(current.revision));render(await api(base(current.id)+'/plan',{method:'PUT',body:form}),true);message(t('Bahnhofsplan gespeichert.'));});};
 el('stationPlanDelete').onclick=()=>{if(!current||!editing||busy)return;run(async()=>{if(dirty)throw Error(t('Bitte zuerst die Kontaktdaten speichern.'));if(!confirm(t('Bahnhofsplan löschen?')))return;render(await api(base(current.id)+'/plan?expected_revision='+current.revision,{method:'DELETE'}),true);});};
 el('stationDelete').onclick=()=>{if(!current||busy||!confirm(t('Bahnhof mit allen Nummern und Bahnhofsplan aus Ihrer Liste löschen?')))return;run(async()=>{await api(base(current.id)+'?expected_revision='+current.revision,{method:'DELETE'});selectedStations.delete(current.id);selectionCount();render(null);await loadList();});};
 window.addEventListener('beforeunload',event=>{if(pending()){event.preventDefault();event.returnValue='';}});
 window.addEventListener('languagechange',()=>{if(current&&!dirty&&!el('stationPlanFile').files.length)render(current,editing);});
 el('stationShareSelected').onclick=()=>{if(!busy)window.StationSharing?.create(Array.from(selectedStations));};
 el('stationShareSingle').onclick=()=>{if(current&&!busy)window.StationSharing?.create([current.id]);};
 el('stationSelectVisible').onchange=()=>{for(const check of el('stationList').querySelectorAll('.station-share-check')){check.checked=el('stationSelectVisible').checked;const id=Number(check.dataset.id);if(check.checked)selectedStations.add(id);else selectedStations.delete(id);}selectionCount();};
 selectionCount();await loadList();
 await window.StationSharing?.init({run,error:message,canUse:()=>!busy&&!pending(),refresh:async()=>{render(null);await loadList();}});
};
})();
