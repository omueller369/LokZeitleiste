(()=>{
const el=id=>document.getElementById(id),t=value=>window.I18n?.t(value)||value;
let rows=[],ticket=0,detailTicket=0,current=null,timer,allowed=false;
function message(value){el('vehicleMessage').textContent=t(value);}
function render(){
 el('vehicleRows').replaceChildren();el('vehicleEmpty').hidden=rows.length>0;
 for(const vehicle of rows){
  const row=document.createElement('tr'),statusCell=document.createElement('td'),statusBox=document.createElement('span'),dot=document.createElement('span');
  statusBox.className='vehicle-list-status';statusBox.setAttribute('role','img');statusBox.setAttribute('aria-label',t(vehicle.status_label));statusBox.title=t(vehicle.status_label)+(vehicle.status_note?' · '+vehicle.status_note:'');
  dot.className='vehicle-status-dot';dot.dataset.status=vehicle.status;dot.setAttribute('aria-hidden','true');statusBox.append(dot);statusCell.append(statusBox);row.append(statusCell);
  const numberCell=document.createElement('td'),choose=document.createElement('button');choose.type='button';choose.className='handover-select';choose.textContent=vehicle.vehicle_number;choose.setAttribute('data-i18n-ignore','');choose.setAttribute('aria-label',t('Ansehen')+' · '+vehicle.vehicle_number);numberCell.append(choose);row.append(numberCell);const nameCell=document.createElement('td');nameCell.textContent=vehicle.name;nameCell.setAttribute('data-i18n-ignore','');row.append(nameCell);row.onclick=()=>selectVehicle(vehicle.id);if(current?.id===vehicle.id)row.setAttribute('aria-selected','true');
  el('vehicleRows').append(row);
 }
}
function renderDetails(){
 if(!current)return;el('handoverTitle').textContent=t('Triebfahrzeug')+' · '+current.vehicle_number;
 el('handoverStatus').textContent=t(current.status_label);el('handoverStatus').dataset.status=current.status;
 const note=current.status!=='ready';el('handoverNoteLabel').hidden=el('handoverNoteBox').hidden=!note;el('handoverNoteLabel').textContent=t(current.status==='limited'?'Einschränkung':'Grund');el('handoverNote').textContent=note?current.status_note:'';el('handoverNote').dataset.status=current.status;
 el('handoverName').textContent=current.name;el('handoverNumber').textContent=current.vehicle_number;el('handoverSeries').textContent=current.series;el('handoverDetails').hidden=false;
}
async function selectVehicle(id){
 const version=++detailTicket;current=null;el('handoverDetails').hidden=true;message('');render();
 try{const response=await fetch('/api/v1/admin/loco-handover/vehicles/'+id,{credentials:'same-origin',cache:'no-store'});if(version!==detailTicket)return;if(response.status===401){location.href='/account';return;}const data=await response.json();if(version!==detailTicket)return;if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Anfrage fehlgeschlagen');current=data;renderDetails();render();el('handoverDetails').scrollIntoView?.({behavior:'smooth',block:'start'});el('handoverTitle').focus({preventScroll:true});}catch(error){if(version===detailTicket)message(error.message);}
}
el('handoverClose').onclick=()=>{detailTicket++;const id=current?.id;current=null;el('handoverDetails').hidden=true;render();const index=rows.findIndex(row=>row.id===id);el('vehicleRows').children[index]?.querySelector('button')?.focus();};
async function listing(){
 detailTicket++;current=null;el('handoverDetails').hidden=true;
 const version=++ticket,params=new URLSearchParams({q:el('vehicleSearch').value});if(el('vehicleFilter').value)params.set('status',el('vehicleFilter').value);
 rows=[];render();el('vehicleEmpty').hidden=true;message('');
 try{const response=await fetch('/api/v1/admin/loco-handover/vehicles?'+params,{credentials:'same-origin',cache:'no-store'});if(version!==ticket)return;if(response.status===401){location.href='/account';return;}const data=await response.json();if(version!==ticket)return;if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Anfrage fehlgeschlagen');rows=data;render();}catch(error){if(version===ticket)message(error.message);}
}
el('vehicleSearch').oninput=()=>{clearTimeout(timer);ticket++;timer=setTimeout(listing,250);};el('vehicleFilter').onchange=listing;el('vehicleReload').onclick=listing;
window.addEventListener('languagechange',()=>{if(allowed){render();renderDetails();}});
(async()=>{try{const response=await fetch('/api/v1/account/me',{credentials:'same-origin',cache:'no-store'});if(response.status===401){location.href='/account';return;}if(!response.ok)throw Error('Anmeldung erforderlich');const me=await response.json();if(me.password_change_required){location.href='/account';return;}if(me.role==='tf'){location.href='/tf';return;}if(me.role!=='admin'&&!me.permissions?.loco_handover){message('Freigabe erforderlich');return;}allowed=true;el('handoverContent').hidden=false;await listing();}catch(error){message(error.message);}})();
})();
