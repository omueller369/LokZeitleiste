(()=>{
 const t=value=>window.I18n?.t(value)||value;
 const node=(tag,label)=>{const value=document.createElement(tag);if(label!==undefined)value.textContent=label;return value;};
 const clock=minutes=>Math.floor(minutes/60)+':'+String(minutes%60).padStart(2,'0')+' h';
 const today=()=>{const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit'}).formatToParts(new Date());return parts.find(p=>p.type==='year').value+'-'+parts.find(p=>p.type==='month').value;};
 window.openTfOvertime=async(user,permissions)=>{
  const level=permissions.reports||0;if(!level)return;
  const dialog=node('dialog'),title=node('h2',t(globalThis.CtlText.source("backend_overtime_ui.text_2ee74e5f154f"))+' · '+(user.first_name||'')+' '+(user.last_name||'')),close=node('button',t(globalThis.CtlText.source("backend_overtime_ui.text_b808f6e97075")));
  dialog.style.cssText='width:min(1050px,95vw);max-height:90vh;overflow:auto;border:1px solid #becdd7;border-radius:12px;padding:24px;box-sizing:border-box';
  close.type='button';close.onclick=()=>dialog.close();
  const controls=node('div'),periodLabel=node('label',t(globalThis.CtlText.source("backend_overtime_ui.text_2933070469a2"))),period=node('input'),refresh=node('button',t(globalThis.CtlText.source("backend_overtime_ui.text_96bf0098166f"))),message=node('p'),body=node('div');
  period.type='month';period.min='2000-01';period.max='2100-12';period.value=today();period.style.width='auto';periodLabel.append(period);
  refresh.type='button';controls.style.cssText='display:flex;flex-wrap:wrap;align-items:end;gap:12px';controls.append(periodLabel,refresh,close);
  message.setAttribute('role','status');message.style.color='#a33129';
  const help=node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_a03c8b99bc49")));
  dialog.append(title,controls,help,message,body);document.body.append(dialog);dialog.onclose=()=>dialog.remove();dialog.showModal();
  let data=null,busy=false;
  const base=()=>'/api/v1/admin/tf/'+user.id+'/overtime/'+period.value.replace('-','/');
  const api=async(path,options={})=>{const response=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...options});const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:t(globalThis.CtlText.source("backend_overtime_ui.text_4d48da0a8b67")));return result;};
  const button=(label,action)=>{const b=node('button',t(label));b.type='button';b.style.margin='6px';b.onclick=action;return b;};
  const table=(headers,rows)=>{const scroll=node('div');scroll.style.overflowX='auto';const table=node('table'),head=node('thead'),tr=node('tr'),tbody=node('tbody');for(const value of headers)tr.append(node('th',t(value)));head.append(tr);table.append(head,tbody);for(const values of rows){const row=node('tr');for(const value of values){const cell=node('td',value);cell.setAttribute('data-i18n-ignore','');row.append(cell);}tbody.append(row);}scroll.append(table);body.append(scroll);return tbody;};
  const run=async action=>{if(busy)return;busy=true;period.disabled=true;refresh.disabled=true;body.inert=true;message.textContent='';try{await action();}catch(error){message.textContent=error.message;}finally{busy=false;period.disabled=false;refresh.disabled=false;body.inert=false;}};
  const mutation=async(suffix,payload)=>{await api(base()+'/'+suffix,{method:suffix==='policy'?'PUT':'POST',body:JSON.stringify({...payload,expected_token:data.token})});await load();};
  async function load(){
   const month=period.value;if(!/^\d{4}-\d{2}$/.test(month))return;
   const values=await Promise.all([api(base()),api('/api/v1/admin/tf/'+user.id+'/overtime/'+month.slice(0,4))]);if(!dialog.isConnected||period.value!==month)return;
   data=values[0];const year=values[1];body.replaceChildren();
   const status=node('p',t(data.enabled?globalThis.CtlText.source("backend_overtime_ui.text_f0cd91bc08fe"):globalThis.CtlText.source("backend_overtime_ui.text_20fdd14890dd")));body.append(status);
   if(level>=3){
    const label=node('label'),enabled=node('input');enabled.type='checkbox';enabled.checked=data.enabled;enabled.style.width='auto';label.append(enabled,document.createTextNode(' '+t(globalThis.CtlText.source("backend_overtime_ui.text_6f53b45a1f72"))));
    const save=button(globalThis.CtlText.source("backend_overtime_ui.text_e7efc317ad09"),()=>run(()=>mutation('policy',{enabled:enabled.checked})));body.append(label,save);
   }
   body.append(node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_24a29f44a444"))+': '+clock(data.total_minutes)),node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_6385c5d64871"))+': '+clock(data.bank_balance_minutes)+' / 40:00 h'));
   body.append(node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_d42c19a3cfd9"))));
   if(data.stale)body.append(node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_c0e250d7048f"))));
   const closing=data.closing?.status==='closed'?data.closing:null;
   if(closing){
    body.append(node('h3',t(globalThis.CtlText.source("backend_overtime_ui.text_6fa18a3a64ca"))),node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a"))+': '+clock(closing.payout_minutes)+' · '+t(globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"))+': '+clock(closing.annual_minutes)));
    if(level>=3)body.append(button(globalThis.CtlText.source("backend_overtime_ui.text_677e35634d12"),()=>run(async()=>{
     const reason=prompt(t(globalThis.CtlText.source("backend_overtime_ui.text_e6c743f19ab8")));if(!reason?.trim())return;
     if(!confirm(t(globalThis.CtlText.source("backend_overtime_ui.text_e45729eef52b"))))return;
     await mutation('reopen',{reason:reason.trim()});
    })));
   }else if(data.enabled&&level>=2){
    const label=node('label',t(globalThis.CtlText.source("backend_overtime_ui.text_fe2896e58446"))),mode=node('select');
    for(const [value,text] of [['payout',globalThis.CtlText.source("backend_overtime_ui.text_b34c2046a396")],['annual',globalThis.CtlText.source("backend_overtime_ui.text_47bed3954eac")]]){const option=node('option',t(text));option.value=value;mode.append(option);}label.append(mode);
    const preview=node('p'),update=()=>{const annual=mode.value==='annual'?Math.min(data.total_minutes,data.bank_available_minutes):0;preview.textContent=t(globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"))+': '+clock(annual)+' · '+t(globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a"))+': '+clock(data.total_minutes-annual);};mode.onchange=update;update();
    const finish=button(globalThis.CtlText.source("backend_overtime_ui.text_a644124f71e6"),()=>run(async()=>{
     const annual=mode.value==='annual'?Math.min(data.total_minutes,data.bank_available_minutes):0;
     if(!confirm(t(globalThis.CtlText.source("backend_overtime_ui.text_a644124f71e6"))+' '+data.month+'?\n'+t(globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"))+': '+clock(annual)+'\n'+t(globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a"))+': '+clock(data.total_minutes-annual)))return;
     await mutation('close',{mode:mode.value});
    }));finish.disabled=!data.can_close;
    body.append(label,preview,finish);if(!data.can_close)body.append(node('p',t(globalThis.CtlText.source("backend_overtime_ui.text_8c01ed2e16ed"))));
   }
   body.append(node('h3',t(globalThis.CtlText.source("backend_overtime_ui.text_0d8ab260b84d"))));
   table([globalThis.CtlText.source("backend_overtime_ui.text_0d95fd6a769f"),globalThis.CtlText.source("backend_overtime_ui.text_2ddcd606c872"),globalThis.CtlText.source("backend_overtime_ui.text_75df3579c730"),globalThis.CtlText.source("backend_overtime_ui.text_b574d367e922"),globalThis.CtlText.source("backend_overtime_ui.text_32666af335b9")],data.rows.map(row=>[row.start_at.replace('T',' '),row.end_at.replace('T',' '),t(row.kind),clock(row.duration_minutes),clock(data.enabled?row.overtime_minutes:0)]));
   body.append(node('h3',t(globalThis.CtlText.source("backend_overtime_ui.text_87683817da28"))));
   const rows=table([globalThis.CtlText.source("backend_overtime_ui.text_2933070469a2"),globalThis.CtlText.source("backend_overtime_ui.text_920e413c7d41"),globalThis.CtlText.source("backend_overtime_ui.text_32666af335b9"),globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"),globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a")],year.months.map(m=>[m.month,t(m.stale?globalThis.CtlText.source("backend_overtime_ui.text_a1ca13575987"):m.closing?.status==='closed'?globalThis.CtlText.source("backend_overtime_ui.text_38ee859a969e"):m.enabled?globalThis.CtlText.source("backend_overtime_ui.text_64509e1af49c"):globalThis.CtlText.source("backend_overtime_ui.text_bf7c9171cb49")),clock(m.closing?.status==='closed'?m.closing.total_minutes:m.total_minutes),clock(m.closing?.status==='closed'?m.closing.annual_minutes:0),clock(m.closing?.status==='closed'?m.closing.payout_minutes:0)]));
   Array.from(rows.rows).forEach((row,index)=>{row.tabIndex=0;row.style.cursor='pointer';const open=()=>{if(!busy){period.value=year.months[index].month;run(load);}};row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};});
   body.append(node('h3',t(globalThis.CtlText.source("backend_overtime_ui.text_f8720778ac3c"))));
   table([globalThis.CtlText.source("backend_overtime_ui.text_2933070469a2"),globalThis.CtlText.source("backend_overtime_ui.text_a4ad259e71cb"),globalThis.CtlText.source("backend_overtime_ui.text_9135882d323c"),globalThis.CtlText.source("backend_overtime_ui.text_80033f8258eb"),globalThis.CtlText.source("backend_overtime_ui.text_45989de49fb7")],year.history.map(item=>{
    const before=item.snapshot.before,details=item.action==='policy'?(item.snapshot.after?t(globalThis.CtlText.source("backend_overtime_ui.text_8163454f378f")):t(globalThis.CtlText.source("backend_overtime_ui.text_bf7c9171cb49"))):item.action==='reopen'?item.snapshot.reason+' · '+t(globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"))+': '+clock(before.annual_minutes)+' · '+t(globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a"))+': '+clock(before.payout_minutes):t(globalThis.CtlText.source("backend_overtime_ui.text_f21484df2cb9"))+': '+clock(item.snapshot.annual_minutes)+' · '+t(globalThis.CtlText.source("backend_overtime_ui.text_760cc329134a"))+': '+clock(item.snapshot.payout_minutes);
    return [item.month,t(({policy:globalThis.CtlText.source("backend_overtime_ui.text_90ba1acfb80b"),close:globalThis.CtlText.source("backend_overtime_ui.text_6fa18a3a64ca"),reopen:globalThis.CtlText.source("backend_overtime_ui.text_ea83fc68f934")})[item.action]),item.created_at.replace('T',' ').slice(0,19)+globalThis.CtlText.source("backend_overtime_ui.text_de92d152d782"),String(item.actor_id),details];
   }));
  }
  refresh.onclick=()=>run(load);period.onchange=()=>run(load);await run(load);
 };
})();
