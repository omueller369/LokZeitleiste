(()=>{
const el=id=>document.getElementById(id),t=value=>window.I18n?.t(value)||value;
const categories={landline:'Festnetz',mobile:'Mobilnetz',bada:'Bada-Nummer',long_dial:'Langwahl',local_radio:'Ortsfunk/Kurzwahl'};
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const date=value=>new Date(value.slice(0,19)+'Z').toLocaleString(window.I18n?.locale||'de-DE',{timeZone:'Europe/Berlin'});
let options,deliveryId=null,preview=null,own=[],selected=[];
async function api(path,settings={}){const response=await fetch(path,{credentials:'same-origin',...settings}),data=await response.json().catch(()=>({}));if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:t('Anfrage fehlgeschlagen'));return data;}
const path=()=>'/api/v1/tf/station-inbox/'+deliveryId;
function canUse(){if(!options.canUse()){options.error(t('Bitte zuerst speichern oder die Bearbeitung abbrechen.'));return false;}return true;}
async function inbox(){const rows=await api('/api/v1/tf/station-inbox');el('stationInbox').replaceChildren();el('stationInboxEmpty').hidden=rows.length>0;for(const item of rows){const row=node('li'),caption=node('span',item.sender+' · '+date(item.created_at)+' · '+item.codes.join(', '));caption.setAttribute('data-i18n-ignore','');row.append(caption);const open=node('button',t('Ansehen')),remove=node('button',t('Zusendung löschen'));open.type=remove.type='button';open.onclick=()=>{if(canUse())options.run(()=>load(item.id));};remove.onclick=()=>{if(canUse())options.run(async()=>{if(!confirm(t('Zusendung aus der Zwischenablage löschen? Bereits übernommene Einträge bleiben erhalten.')))return;await api('/api/v1/tf/station-inbox/'+item.id,{method:'DELETE'});if(deliveryId===item.id){preview=null;deliveryId=null;renderPreview();}await inbox();});};row.append(open,remove);el('stationInbox').append(row);}}
function renderPreview(){
 el('stationSharePreview').hidden=!preview;if(!preview)return;el('stationImportAll').checked=true;
 el('stationShareSender').textContent=preview.sender+' · '+date(preview.created_at);el('stationSharedItems').replaceChildren();
 for(const item of preview.items){const row=node('li'),label=node('label'),check=node('input'),caption=node('span',item.code+' · '+item.name);check.type='checkbox';check.checked=true;check.value=String(item.id);check.className='station-import-check';caption.setAttribute('data-i18n-ignore','');label.append(check,caption);row.append(label);
 const targetLabel=node('label',t('Ziel in meiner Bahnhofsliste')),target=node('select');target.className='station-import-target';target.dataset.item=String(item.id);
 const match=own.find(station=>station.code===item.code);if(!match){const option=node('option',t('Neuer Bahnhofseintrag')+' · '+item.code);option.value='';option.setAttribute('data-i18n-ignore','');target.append(option);}
 for(const station of own){const option=node('option',station.code+' · '+station.name);option.value=String(station.id);option.setAttribute('data-i18n-ignore','');target.append(option);}target.value=match?String(match.id):'';targetLabel.append(target);row.append(targetLabel);
 const detail=node('details'),summary=node('summary',t('Rufnummern anzeigen'));detail.append(summary);const list=node('ul');for(const contact of item.contacts){const entry=node('li',t(categories[contact.category])+': '+contact.label+' · '+contact.number);entry.setAttribute('data-i18n-ignore','');list.append(entry);}detail.append(list);
 if(item.plan){const plan=node('a',item.plan.filename);plan.href=path()+'/items/'+item.id+'/plan';plan.setAttribute('data-i18n-ignore','');detail.append(plan);}row.append(detail);el('stationSharedItems').append(row);}
}
async function load(id){const [data,stations]=await Promise.all([api('/api/v1/tf/station-inbox/'+id),api('/api/v1/tf/stations')]);deliveryId=id;preview=data;own=stations;renderPreview();}
window.StationSharing={
 init:async settings=>{options=settings;
  el('stationSendCancel').onclick=()=>{el('stationSendBox').hidden=true;selected=[];};
  el('stationSendConfirm').onclick=()=>{if(!canUse())return;options.run(async()=>{const recipient=Number(el('stationRecipient').value);if(!recipient)throw Error(t('Bitte einen TF auswählen.'));await api('/api/v1/tf/station-shares',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({station_ids:selected,recipient_id:recipient,include_plans:el('stationSharePlans').checked})});el('stationSendBox').hidden=true;selected=[];options.error(t('Bahnhöfe wurden in die Zwischenablage des TF gesendet.'));});};
  el('stationShareImport').onclick=()=>{if(!preview||!canUse())return;options.run(async()=>{const checks=Array.from(el('stationSharedItems').querySelectorAll('.station-import-check')).filter(check=>check.checked);if(!checks.length)throw Error(t('Bitte mindestens einen Bahnhof auswählen.'));const targets=Array.from(el('stationSharedItems').querySelectorAll('.station-import-target'));
   const items=checks.map(check=>{const targetId=Number(targets.find(target=>target.dataset.item===check.value).value)||null;const station=own.find(station=>station.id===targetId);return {id:Number(check.value),target_station_id:targetId,expected_revision:station?.revision||0};});
   const result=await api(path()+'/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items,mode:el('stationImportMode').value,include_plans:el('stationImportPlans').checked})});await options.refresh();await load(deliveryId);options.error(t('Import abgeschlossen.')+' '+t('Neu')+': '+result.created+' · '+t('Ergänzt')+': '+result.extended+' · '+t('Unverändert')+': '+result.unchanged+' · '+t('Übersprungen')+': '+result.skipped);});};
  el('stationImportAll').onchange=()=>el('stationSharedItems').querySelectorAll('.station-import-check').forEach(check=>check.checked=el('stationImportAll').checked);
  el('stationInboxReload').onclick=()=>{if(canUse())options.run(inbox);};
  await options.run(inbox);
 },
 create:ids=>{if(!canUse())return;if(!ids.length){options.error(t('Bitte mindestens einen Bahnhof auswählen.'));return;}if(ids.length>50){options.error(t('Höchstens 50 Bahnhöfe pro Freigabe.'));return;}options.run(async()=>{const recipients=await api('/api/v1/tf/station-recipients');selected=ids.slice();el('stationRecipient').replaceChildren();const blank=node('option',t('Bitte einen TF auswählen.'));blank.value='';el('stationRecipient').append(blank);for(const recipient of recipients){const option=node('option',recipient.label);option.value=String(recipient.id);option.setAttribute('data-i18n-ignore','');el('stationRecipient').append(option);}el('stationRecipient').value='';el('stationSendCount').textContent=String(ids.length);el('stationSendBox').hidden=false;el('stationSendBox').scrollIntoView?.({behavior:'smooth',block:'nearest'});});}
};
})();
