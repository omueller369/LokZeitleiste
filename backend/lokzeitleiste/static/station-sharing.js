(()=>{
const el=id=>document.getElementById(id),t=value=>window.I18n?.t(value)||value;
const categories={landline:'Festnetz',mobile:'Mobilnetz',bada:'Bada-Nummer',long_dial:'Langwahl',local_radio:'Ortsfunk/Kurzwahl'};
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const date=value=>new Date(value.slice(0,19)+'Z').toLocaleString(window.I18n?.locale||'de-DE',{timeZone:'Europe/Berlin'});
let options,token='',preview=null;
async function api(path,settings={}){const response=await fetch(path,{credentials:'same-origin',...settings}),data=await response.json().catch(()=>({}));if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:t('Anfrage fehlgeschlagen'));return data;}
const path=()=>'/api/v1/tf/station-shares/'+encodeURIComponent(token);
function canUse(){if(!options.canUse()){options.error(t('Bitte zuerst speichern oder die Bearbeitung abbrechen.'));return false;}return true;}
async function mine(){const rows=await api('/api/v1/tf/station-shares');el('stationOwnShares').replaceChildren();for(const share of rows){const row=node('li'),caption=node('span',share.codes.join(', ')+' · '+date(share.expires_at)+' · '+t(share.active?'Aktiv':share.revoked?'Widerrufen':'Abgelaufen'));caption.setAttribute('data-i18n-ignore','');row.append(caption);if(share.active){const revoke=node('button',t('Widerrufen'));revoke.type='button';revoke.onclick=()=>options.run(async()=>{if(!confirm(t('Freigabe widerrufen? Bereits importierte Kopien bleiben erhalten.')))return;await api('/api/v1/tf/station-shares/mine/'+share.id,{method:'DELETE'});await mine();});row.append(revoke);}el('stationOwnShares').append(row);}}
function renderPreview(){
 el('stationSharePreview').hidden=!preview;if(!preview)return;el('stationImportAll').checked=true;
 el('stationShareSender').textContent=preview.sender+' · '+date(preview.expires_at);el('stationSharedItems').replaceChildren();
 for(const item of preview.items){const row=node('li'),label=node('label'),check=node('input'),caption=node('span',item.code+' · '+item.name+(item.expected_revision?' · '+t('Bereits in eigener Liste'):''));check.type='checkbox';check.checked=true;check.value=String(item.id);check.className='station-import-check';caption.setAttribute('data-i18n-ignore','');label.append(check,caption);row.append(label);
 const detail=node('details'),summary=node('summary',t('Rufnummern anzeigen'));detail.append(summary);const list=node('ul');for(const contact of item.contacts){const entry=node('li',t(categories[contact.category])+': '+contact.label+' · '+contact.number);entry.setAttribute('data-i18n-ignore','');list.append(entry);}detail.append(list);
 if(item.plan){const plan=node('a',item.plan.filename);plan.href=path()+'/items/'+item.id+'/plan';plan.setAttribute('data-i18n-ignore','');detail.append(plan);}row.append(detail);el('stationSharedItems').append(row);}
}
function readToken(value){const trimmed=value.trim();if(/^[A-Za-z0-9_-]{43}$/.test(trimmed))return trimmed;try{const url=new URL(trimmed);if(url.origin===location.origin){const code=url.searchParams.get('share')||'';if(/^[A-Za-z0-9_-]{43}$/.test(code))return code;}}catch(error){}throw Error(t('Bitte einen gültigen Freigabecode oder Link dieser Software eingeben.'));}
async function loadPreview(){const next=readToken(el('stationShareCode').value);const data=await api('/api/v1/tf/station-shares/'+encodeURIComponent(next));token=next;preview=data;renderPreview();}
window.StationSharing={
 init:async settings=>{options=settings;
  el('stationShareLoad').onclick=()=>{if(canUse())options.run(loadPreview);};
  el('stationShareImport').onclick=()=>{if(!preview||!canUse())return;options.run(async()=>{const selected=new Set(Array.from(el('stationSharedItems').querySelectorAll('.station-import-check')).filter(check=>check.checked).map(check=>Number(check.value)));if(!selected.size)throw Error(t('Bitte mindestens einen Bahnhof auswählen.'));const items=preview.items.filter(item=>selected.has(item.id)).map(item=>({id:item.id,expected_revision:item.expected_revision}));
   const result=await api(path()+'/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items,mode:el('stationImportMode').value,include_plans:el('stationImportPlans').checked})});await options.refresh();preview=await api(path());renderPreview();options.error(t('Import abgeschlossen.')+' '+t('Neu')+': '+result.created+' · '+t('Ergänzt')+': '+result.extended+' · '+t('Unverändert')+': '+result.unchanged+' · '+t('Übersprungen')+': '+result.skipped+' · '+t('Pläne übernommen')+': '+result.plans_added);});};
  el('stationImportAll').onchange=()=>el('stationSharedItems').querySelectorAll('.station-import-check').forEach(check=>check.checked=el('stationImportAll').checked);
  el('stationCopyShare').onclick=async()=>{const input=el('stationShareLink');try{if(!navigator.clipboard)throw Error();await navigator.clipboard.writeText(input.value);}catch(error){input.focus();input.select();input.setSelectionRange(0,input.value.length);options.error(t('Link ist markiert und kann kopiert werden.'));}};
  el('stationSharesReload').onclick=()=>options.run(mine);
  const inbound=new URLSearchParams(location.search).get('share');if(inbound){el('stationShareCode').value=inbound;const clean=new URL(location.href);clean.searchParams.delete('share');history.replaceState(null,'',clean.pathname+clean.search+clean.hash);await options.run(loadPreview);}
  await options.run(mine);
 },
 create:ids=>{if(!canUse())return;if(!ids.length){options.error(t('Bitte mindestens einen Bahnhof auswählen.'));return;}if(ids.length>50){options.error(t('Höchstens 50 Bahnhöfe pro Freigabe.'));return;}options.run(async()=>{const share=await api('/api/v1/tf/station-shares',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({station_ids:ids,include_plans:el('stationSharePlans').checked})});el('stationShareLink').value=location.origin+'/tf/bahnhoefe?share='+encodeURIComponent(share.token);el('stationShareCreated').hidden=false;el('stationShareExpiry').textContent=t('Gültig bis')+': '+date(share.expires_at);el('stationShareCreated').scrollIntoView?.({behavior:'smooth',block:'nearest'});await mine();});}
};
})();
