(()=>{
const element=id=>document.getElementById(id),translate=value=>window.I18n?.t(value)||value;
const node=(tag,value)=>{const result=document.createElement(tag);if(value!==undefined)result.textContent=value;return result;};
let accessLevel=0;
const shiftLabels={standard:'Streckendienst',border_day:'Grenzdienst Tag',border_night:'Grenzdienst Nacht'};
function dayCode(day){return day.kind==='Arbeitstag'&&day.shift==='border_day'?'GT':day.kind==='Arbeitstag'&&day.shift==='border_night'?'GN':({Arbeitstag:'A',Urlaub:'U',Ruhetag:'R',Ungeplant:'?'})[day.kind];}
function planColor(node,day){window.PlanColors.apply(node,day);}
async function api(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});if(response.status===401){location.href='/account?area=backend';throw Error('Anmeldung erforderlich');}const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Anfrage fehlgeschlagen ('+response.status+')');return data;}
let mode='month',snapshot=null,ticket=0,pending=false,review=null,anchor=null;
const selected=new Map(),visible=new Map();
const key=(id,date)=>id+':'+date;
function locale(){return window.I18n?.locale||'de-DE';}
function monthName(year,month){return new Intl.DateTimeFormat(locale(),{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(year,month-1,1)));}
function say(s){element('overviewMessage').textContent=translate(s);}
function invalidate(){review=null;element('overviewReview').hidden=true;element('overviewAgree').checked=false;element('overviewApply').disabled=true;}
function controls(){
 const allowed=accessLevel>=2;
 element('overviewTools').hidden=!allowed;element('overviewHelp').hidden=!allowed;element('overviewTools').disabled=pending;
 for(const id of ['overviewYear','overviewMonth','overviewMonthView','overviewYearView','overviewReload'])element(id).disabled=pending;
 element('overviewPreview').disabled=pending||!selected.size;
 element('overviewApply').disabled=pending||!review||!element('overviewAgree').checked;
 element('overviewCancel').disabled=pending;element('overviewAgree').disabled=pending;
 element('overviewCount').textContent=translate('Ausgewählte Felder')+': '+selected.size+' · '+translate('TF gesamt')+': '+new Set([...selected.values()].map(item=>item.user.id)).size;
 for(const [id,item]of visible){const cell=item.cell;if(allowed){cell.setAttribute('aria-pressed',String(selected.has(id)));cell.setAttribute('aria-disabled',String(pending));}}
}
function select(items,toggle=true){if(pending||accessLevel<2)return;const remove=toggle&&items.every(item=>selected.has(key(item.user.id,item.day.date)));if(!remove&&new Set([...selected.keys(),...items.map(item=>key(item.user.id,item.day.date))]).size>10000){say('Maximal 10000 Felder pro Änderung.');return;}invalidate();for(const item of items){const id=key(item.user.id,item.day.date);if(remove)selected.delete(id);else selected.set(id,item);}controls();}
function pick(item,event){if(pending)return;if(event.shiftKey&&anchor){select([...visible.values()].filter(other=>other.row>=Math.min(anchor.row,item.row)&&other.row<=Math.max(anchor.row,item.row)&&other.column>=Math.min(anchor.column,item.column)&&other.column<=Math.max(anchor.column,item.column)),false);}else select([item]);anchor=item;}
function render(){
 if(!snapshot)return;
 const {year,month,rows,view}=snapshot;
 element('overviewTitle').textContent=view==='year'?String(year):monthName(year,month);
 element('overviewGrid').replaceChildren();visible.clear();
 if(!rows.length){say('Keine TF vorhanden.');controls();return;}
 const months=view==='year'?Array.from({length:12},(_,i)=>i+1):[month];
 const table=node('table');table.className='overview-matrix';
 table.append(node('caption',translate('Ruhetagsplan aller TF')+' · '+element('overviewTitle').textContent));
 const head=node('thead'),monthRow=node('tr'),dayRow=node('tr'),nameHeader=node('th',translate('Triebfahrzeugführer'));nameHeader.rowSpan=2;nameHeader.scope='col';nameHeader.className='overview-name';monthRow.append(nameHeader);
 for(const m of months){const days=new Date(Date.UTC(year,m,0)).getUTCDate(),header=node('th',monthName(year,m));header.colSpan=days;header.scope='colgroup';header.setAttribute('data-i18n-ignore','');monthRow.append(header);
 for(let d=1;d<=days;d++){const date=new Date(Date.UTC(year,m-1,d)),label=node('th',String(d));label.scope='col';label.title=new Intl.DateTimeFormat(locale(),{dateStyle:'full',timeZone:'UTC'}).format(date);if([0,6].includes(date.getUTCDay()))label.className='overview-weekend';dayRow.append(label);}}
 head.append(monthRow,dayRow);table.append(head);const body=node('tbody');
 for(let index=0;index<rows.length;index++){const {user,plans}=rows[index],row=node('tr'),name=node('th');name.scope='row';name.className='overview-name';const caption=String(index+1)+'. '+user.first_name+' '+user.last_name;
 if(accessLevel>=2){const button=node('button',caption);button.type='button';button.className='secondary';button.title=translate('Alle sichtbaren Felder auswählen');button.setAttribute('data-i18n-ignore','');button.onclick=()=>select([...visible.values()].filter(item=>item.user.id===user.id));name.append(button);}else{name.textContent=caption;name.setAttribute('data-i18n-ignore','');}row.append(name);let column=0;
 for(const m of months){const plan=plans.find(plan=>plan.month===m);for(const day of plan.days){const cell=node('td',dayCode(day)),id=key(user.id,day.date),item={user,plan,day,row:index,column:column++,cell};visible.set(id,item);if(selected.has(id))selected.set(id,item);cell.dataset.kind=day.kind;cell.dataset.holiday=String(day.is_holiday);cell.setAttribute('data-i18n-ignore','');planColor(cell,day);const weekday=new Date(day.date+'T00:00:00Z').getUTCDay();if([0,6].includes(weekday))cell.className='overview-weekend';const title=day.date+' · '+user.first_name+' '+user.last_name+' · '+translate(day.kind)+(day.is_holiday?' · '+translate(day.holiday_name):'')+(day.kind==='Arbeitstag'?' · '+translate(shiftLabels[day.shift]||'Streckendienst'):'');cell.title=title;cell.setAttribute('aria-label',title);
 if(accessLevel>=2){cell.tabIndex=0;cell.setAttribute('role','button');cell.onclick=event=>pick(item,event);cell.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();pick(item,event);}};}row.append(cell);}}
 body.append(row);}
 table.append(body);element('overviewGrid').append(table);say(translate('TF gesamt')+': '+rows.length);controls();
}
async function load(next,initialUsers=null,force=false){
 if(pending)return;
 if(!force&&selected.size&&!confirm(translate('Auswahl verwerfen?'))){if(snapshot){element('overviewYear').value=snapshot.year;element('overviewMonth').value=snapshot.month;}return;}
 mode=next;selected.clear();anchor=null;invalidate();const currentTicket=++ticket,year=Number(element('overviewYear').value),month=Number(element('overviewMonth').value);
 snapshot=null;visible.clear();element('overviewGrid').replaceChildren();element('overviewTitle').textContent='';controls();
 element('overviewMonthView').setAttribute('aria-pressed',String(mode==='month'));element('overviewYearView').setAttribute('aria-pressed',String(mode==='year'));
 if(!Number.isInteger(year)||year<2000||year>2100||month<1||month>12){say('Bitte einen gültigen Zeitraum wählen.');return;}
 say('Gesamtübersicht wird geladen…');element('overviewGrid').setAttribute('aria-busy','true');
 try{
 const users=(initialUsers||await api('/api/v1/admin/tf')).slice().sort((a,b)=>a.last_name.localeCompare(b.last_name,locale())||a.first_name.localeCompare(b.first_name,locale())||a.id-b.id),rows=new Array(users.length);let index=0;
 async function worker(){while(index<users.length&&currentTicket===ticket){const position=index++,user=users[position];const result=await api('/api/v1/admin/tf/'+user.id+'/plan/'+year+(next==='month'?'/'+month:''));rows[position]={user,plans:next==='month'?[result]:result.months};}}
 await Promise.all(Array.from({length:Math.min(4,users.length)},worker));
 if(currentTicket!==ticket)return;snapshot={year,month,view:next,rows};render();
 }catch(error){if(currentTicket===ticket){ticket++;snapshot=null;element('overviewGrid').replaceChildren();say(error.message);element('overviewGrid').setAttribute('aria-busy','false');}}
 finally{if(currentTicket===ticket)element('overviewGrid').setAttribute('aria-busy','false');controls();}
}
function request(){
 const groups=new Map();for(const item of selected.values()){
  const id=item.user.id+':'+snapshot.year;let group=groups.get(id);if(!group){group={tf_id:item.user.id,year:snapshot.year,days:[],expected_revisions:{}};groups.set(id,group);}
  group.expected_revisions[item.plan.month]=item.plan.revision;group.days.push({date:item.day.date,kind:element('overviewKind').value,shift:element('overviewKind').value==='Arbeitstag'?(element('overviewShift').value||null):null,note:element('overviewReplaceNote').checked?element('overviewNote').value:item.day.note});
 }return {groups:[...groups.values()]};
}
function describe(day){return translate(day.kind)+(day.kind==='Arbeitstag'?' · '+translate(shiftLabels[day.shift]):'')+' · '+Math.floor(day.target_minutes/60)+':'+String(day.target_minutes%60).padStart(2,'0')+' h'+(day.note?'\n'+translate('Notiz')+': '+day.note:'');}
async function preview(){
 if(pending||!selected.size)return;invalidate();pending=true;controls();
 try{const body=request(),result=await api('/api/v1/admin/planning/collective/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!result.changes.length){say('Keine Änderungen vorhanden.');return;}
 review={body,result};element('overviewReviewRows').replaceChildren();for(const change of result.changes){const row=node('tr');for(const value of [change.name,change.date,describe(change.before),describe(change.after)]){const cell=node('td',value);cell.setAttribute('data-i18n-ignore','');row.append(cell);}element('overviewReviewRows').append(row);}element('overviewReview').hidden=false;element('overviewReview').scrollIntoView({behavior:'smooth',block:'nearest'});say('Änderungsliste prüfen und bestätigen.');
 }catch(error){say(error.message);}finally{pending=false;controls();}
}
async function apply(){
 if(pending||!review||!element('overviewAgree').checked)return;pending=true;controls();let saved;
 try{saved=await api('/api/v1/admin/planning/collective/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...review.body,confirmation:review.result.confirmation,confirmed:true})});}
 catch(error){invalidate();say(error.message);return;}finally{pending=false;controls();}
 selected.clear();invalidate();await load(mode,null,true);say(translate('Planänderungen gespeichert.')+' '+translate('Ausgewählte Felder')+': '+saved.changed_days);
}
window.refreshPlanningOverview=()=>load(mode);
function start(users){
 element('collectiveOverview').hidden=false;const now=new Intl.DateTimeFormat('en-CA',{year:'numeric',month:'2-digit',timeZone:'Europe/Berlin'}).formatToParts(new Date());element('overviewYear').value=now.find(part=>part.type==='year').value;
 for(let m=1;m<=12;m++){const option=node('option',new Intl.DateTimeFormat(locale(),{month:'long',timeZone:'UTC'}).format(new Date(Date.UTC(2026,m-1,1))));option.value=String(m);element('overviewMonth').append(option);}element('overviewMonth').value=String(Number(now.find(part=>part.type==='month').value));
 element('overviewMonthView').onclick=()=>load('month');element('overviewYearView').onclick=()=>load('year');element('overviewReload').onclick=()=>load(mode);element('overviewYear').onchange=()=>load(mode);element('overviewMonth').onchange=()=>load(mode);
 element('overviewSelectAll').onclick=()=>select([...visible.values()],false);element('overviewClear').onclick=()=>{if(!pending){selected.clear();anchor=null;invalidate();controls();}};
 for(const id of ['overviewKind','overviewShift','overviewReplaceNote','overviewNote'])element(id).addEventListener('input',()=>{invalidate();element('overviewNote').disabled=!element('overviewReplaceNote').checked;element('overviewShift').disabled=element('overviewKind').value!=='Arbeitstag';controls();});
 element('overviewShift').disabled=true;element('overviewPreview').onclick=preview;element('overviewApply').onclick=apply;element('overviewCancel').onclick=invalidate;element('overviewAgree').onchange=controls;
 window.addEventListener('languagechange',()=>{invalidate();for(const option of element('overviewMonth').children)option.textContent=new Intl.DateTimeFormat(locale(),{month:'long',timeZone:'UTC'}).format(new Date(Date.UTC(2026,Number(option.value)-1,1)));render();});load('month',users);
}
(async()=>{try{const account=await api('/api/v1/account/me');if(account.password_change_required){location.href='/account';return;}accessLevel=account.permissions?.planning||0;if(!accessLevel)throw Error('Keine Freigabe für das Planungsmodul.');start(await api('/api/v1/admin/tf'));}catch(error){element('overviewAccessMessage').textContent=translate(error.message);}})();
})();
