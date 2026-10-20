(()=>{
 const t=value=>window.I18n?.t(value)||value;
 const node=(tag,label)=>{const value=document.createElement(tag);if(label!==undefined)value.textContent=label;return value;};
 const clock=minutes=>Math.floor(minutes/60)+':'+String(minutes%60).padStart(2,'0')+' h';
 const today=()=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value;};
 window.openTfOvertime=async(user,permissions)=>{
  const level=permissions.reports||0;if(!level)return;
  const dialog=node('dialog'),title=node('h2',t('Überstundenkonto')+' · '+(user.first_name||'')+' '+(user.last_name||'')),close=node('button',t('Schließen'));
  dialog.style.cssText='width:min(1050px,95vw);max-height:90vh;overflow:auto;border:1px solid #becdd7;border-radius:12px;padding:24px;box-sizing:border-box';
  close.type='button';close.onclick=()=>dialog.close();
  const controls=node('div'),periodLabel=node('label',t('Monat')),period=node('input'),refresh=node('button',t('Aktualisieren')),message=node('p'),body=node('div');
  period.type='month';period.min='2000-01';period.max='2100-12';period.value=today();period.style.width='auto';periodLabel.append(period);
  refresh.type='button';controls.style.cssText='display:flex;flex-wrap:wrap;align-items:end;gap:12px';controls.append(periodLabel,refresh,close);
  message.setAttribute('role','status');message.style.color='#a33129';
  const help=node('p',t('Je Dienstschicht zählt nur die Zeit über acht Stunden. Pausen werden nicht abgezogen; Gastfahrten außerhalb des Dienstes zählen nicht. Zuordnung nach Dienstbeginn.'));
  dialog.append(title,controls,help,message,body);document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
  let data=null,busy=false;
  const base=()=>'/api/v1/admin/tf/'+user.id+'/overtime/'+period.value.replace('-','/');
  const api=async(path,options={})=>{const response=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...options});const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:t('Anfrage fehlgeschlagen'));return result;};
  const button=(label,action)=>{const b=node('button',t(label));b.type='button';b.style.margin='6px';b.onclick=action;return b;};
  const table=(headers,rows)=>{const scroll=node('div');scroll.style.overflowX='auto';const table=node('table'),head=node('thead'),tr=node('tr'),tbody=node('tbody');for(const value of headers)tr.append(node('th',t(value)));head.append(tr);table.append(head,tbody);for(const values of rows){const row=node('tr');for(const value of values){const cell=node('td',value);cell.setAttribute('data-i18n-ignore','');row.append(cell);}tbody.append(row);}scroll.append(table);body.append(scroll);return tbody;};
  const run=async action=>{if(busy)return;busy=true;period.disabled=true;refresh.disabled=true;body.inert=true;message.textContent='';try{await action();}catch(error){message.textContent=error.message;}finally{busy=false;period.disabled=false;refresh.disabled=false;body.inert=false;}};
  const mutation=async(suffix,payload)=>{await api(base()+'/'+suffix,{method:suffix==='policy'?'PUT':'POST',body:JSON.stringify({...payload,expected_token:data.token})});await load();};
  async function load(){
   const month=period.value;if(!/^\d{4}-\d{2}$/.test(month))return;
   const values=await Promise.all([api(base()),api('/api/v1/admin/tf/'+user.id+'/overtime/'+month.slice(0,4))]);if(!dialog.isConnected||period.value!==month)return;
   data=values[0];const year=values[1];body.replaceChildren();
   const status=node('p',t(data.enabled?'Überstundenkonto aktiv':'Überstundenkonto inaktiv'));body.append(status);
   if(level>=3){
    const label=node('label'),enabled=node('input');enabled.type='checkbox';enabled.checked=data.enabled;enabled.style.width='auto';label.append(enabled,document.createTextNode(' '+t('Konto ab ausgewähltem Monat aktivieren')));
    const save=button('Aktivierung speichern',()=>run(()=>mutation('policy',{enabled:enabled.checked})));body.append(label,save);
   }
   body.append(node('p',t('Überstunden im Monat')+': '+clock(data.total_minutes)),node('p',t('Jahresüberstundenkonto')+': '+clock(data.bank_balance_minutes)+' / 40:00 h'));
   body.append(node('p',t('Guthaben bleibt beim Jahreswechsel erhalten. Die 40-Stunden-Grenze gilt für den gesamten Kontostand.')));
   if(data.stale)body.append(node('p',t('Dienstzeiten nach Abschluss geändert. Abschluss prüfen und vor erneuter Buchung wieder öffnen.')));
   const closing=data.closing?.status==='closed'?data.closing:null;
   if(closing){
    body.append(node('h3',t('Monatsabschluss')),node('p',t('Auszahlung vorgemerkt')+': '+clock(closing.payout_minutes)+' · '+t('Ins Jahreskonto')+': '+clock(closing.annual_minutes)));
    if(level>=3)body.append(button('Abschluss wieder öffnen',()=>run(async()=>{
     const reason=prompt(t('Begründung für Wiederöffnung'));if(!reason?.trim())return;
     if(!confirm(t('Die Buchung wird zurückgenommen. Bereits erfolgte Auszahlungen müssen separat korrigiert werden.')))return;
     await mutation('reopen',{reason:reason.trim()});
    })));
   }else if(data.enabled&&level>=2){
    const label=node('label',t('Verwendung beim Monatsabschluss')),mode=node('select');
    for(const [value,text] of [['payout','Zur Auszahlung vormerken'],['annual','Ins Jahreskonto, Rest zur Auszahlung']]){const option=node('option',t(text));option.value=value;mode.append(option);}label.append(mode);
    const preview=node('p'),update=()=>{const annual=mode.value==='annual'?Math.min(data.total_minutes,data.bank_available_minutes):0;preview.textContent=t('Ins Jahreskonto')+': '+clock(annual)+' · '+t('Auszahlung vorgemerkt')+': '+clock(data.total_minutes-annual);};mode.onchange=update;update();
    const finish=button('Monat abschließen',()=>run(async()=>{
     const annual=mode.value==='annual'?Math.min(data.total_minutes,data.bank_available_minutes):0;
     if(!confirm(t('Monat abschließen')+' '+data.month+'?\n'+t('Ins Jahreskonto')+': '+clock(annual)+'\n'+t('Auszahlung vorgemerkt')+': '+clock(data.total_minutes-annual)))return;
     await mutation('close',{mode:mode.value});
    }));finish.disabled=!data.can_close;
    body.append(label,preview,finish);if(!data.can_close)body.append(node('p',t('Monatsabschluss erst nach Monatsende möglich.')));
   }
   body.append(node('h3',t('Dienstschichten')));
   table(['Beginn','Ende','Art','Arbeitszeit','Überstunden'],data.rows.map(row=>[row.start_at.replace('T',' '),row.end_at.replace('T',' '),t(row.kind),clock(row.duration_minutes),clock(data.enabled?row.overtime_minutes:0)]));
   body.append(node('h3',t('Jahresübersicht')));
   const rows=table(['Monat','Status','Überstunden','Ins Jahreskonto','Auszahlung vorgemerkt'],year.months.map(m=>[m.month,t(m.stale?'Prüfen':m.closing?.status==='closed'?'Abgeschlossen':m.enabled?'Offen':'Inaktiv'),clock(m.closing?.status==='closed'?m.closing.total_minutes:m.total_minutes),clock(m.closing?.status==='closed'?m.closing.annual_minutes:0),clock(m.closing?.status==='closed'?m.closing.payout_minutes:0)]));
   Array.from(rows.rows).forEach((row,index)=>{row.tabIndex=0;row.style.cursor='pointer';const open=()=>{if(!busy){period.value=year.months[index].month;run(load);}};row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};});
   body.append(node('h3',t('Änderungsverlauf')));
   table(['Monat','Aktion','Datum','Benutzer','Details'],year.history.map(item=>{
    const before=item.snapshot.before,details=item.action==='policy'?(item.snapshot.after?t('Aktiv'):t('Inaktiv')):item.action==='reopen'?item.snapshot.reason+' · '+t('Ins Jahreskonto')+': '+clock(before.annual_minutes)+' · '+t('Auszahlung vorgemerkt')+': '+clock(before.payout_minutes):t('Ins Jahreskonto')+': '+clock(item.snapshot.annual_minutes)+' · '+t('Auszahlung vorgemerkt')+': '+clock(item.snapshot.payout_minutes);
    return [item.month,t(({policy:'Aktivierung',close:'Monatsabschluss',reopen:'Wiederöffnung'})[item.action]),item.created_at.replace('T',' ').slice(0,19)+' UTC',String(item.actor_id),details];
   }));
  }
  refresh.onclick=()=>run(load);period.onchange=()=>run(load);await run(load);
 };
})();
