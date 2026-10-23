(()=>{
const el=id=>document.getElementById(id),t=value=>window.I18n?.t(value)||value;
let rows=[],ticket=0,timer,allowed=false;
function message(value){el('vehicleMessage').textContent=t(value);}
function render(){
 el('vehicleRows').replaceChildren();el('vehicleEmpty').hidden=rows.length>0;
 for(const vehicle of rows){
  const row=document.createElement('tr'),statusCell=document.createElement('td'),statusBox=document.createElement('span'),dot=document.createElement('span');
  statusBox.className='vehicle-list-status';statusBox.setAttribute('role','img');statusBox.setAttribute('aria-label',t(vehicle.status_label));statusBox.title=t(vehicle.status_label)+(vehicle.status_note?' · '+vehicle.status_note:'');
  dot.className='vehicle-status-dot';dot.dataset.status=vehicle.status;dot.setAttribute('aria-hidden','true');statusBox.append(dot);statusCell.append(statusBox);row.append(statusCell);
  for(const value of [vehicle.vehicle_number,vehicle.name]){const cell=document.createElement('td');cell.textContent=value;cell.setAttribute('data-i18n-ignore','');row.append(cell);}
  el('vehicleRows').append(row);
 }
}
async function listing(){
 const version=++ticket,params=new URLSearchParams({q:el('vehicleSearch').value});if(el('vehicleFilter').value)params.set('status',el('vehicleFilter').value);
 rows=[];render();el('vehicleEmpty').hidden=true;message('');
 try{const response=await fetch('/api/v1/admin/loco-handover/vehicles?'+params,{credentials:'same-origin',cache:'no-store'});if(version!==ticket)return;if(response.status===401){location.href='/account';return;}const data=await response.json();if(version!==ticket)return;if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Anfrage fehlgeschlagen');rows=data;render();}catch(error){if(version===ticket)message(error.message);}
}
el('vehicleSearch').oninput=()=>{clearTimeout(timer);ticket++;timer=setTimeout(listing,250);};el('vehicleFilter').onchange=listing;el('vehicleReload').onclick=listing;
window.addEventListener('languagechange',()=>{if(allowed)render();});
(async()=>{try{const response=await fetch('/api/v1/account/me',{credentials:'same-origin',cache:'no-store'});if(response.status===401){location.href='/account';return;}if(!response.ok)throw Error('Anmeldung erforderlich');const me=await response.json();if(me.password_change_required){location.href='/account';return;}if(me.role==='tf'){location.href='/tf';return;}if(me.role!=='admin'&&!me.permissions?.loco_handover){message('Freigabe erforderlich');return;}allowed=true;el('handoverContent').hidden=false;await listing();}catch(error){message(error.message);}})();
})();
