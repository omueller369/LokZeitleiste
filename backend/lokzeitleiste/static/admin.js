const el=id=>document.getElementById(id);
let me=null;
const clock=n=>(n<0?'-':'')+Math.floor(Math.abs(n)/60)+':'+String(Math.abs(n)%60).padStart(2,'0');
async function request(path,options={}){const response=await fetch(path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...options});
 const body=await response.json().catch(()=>({}));if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'Anfrage fehlgeschlagen ('+response.status+')');return body;}
function link(box,label,href){const a=document.createElement('a');a.textContent=label;a.href=href;a.style.margin='8px';a.style.display='inline-block';box.append(a);}
async function show(){const account=await request('/api/v1/account/me');if(account.password_change_required){location.href='/account';return;}
 me=await request('/api/v1/admin/me');el('login').hidden=true;el('dashboard').hidden=false;el('logout').hidden=false;
 el('navigation').replaceChildren();link(el('navigation'),'Mein Passwort ändern','/account');
 if(me.permissions.staff)link(el('navigation'),'Verwaltungsmitarbeiter und Rechte','/admin/staff');
 el('createTfCard').hidden=me.permissions.employees<3;document.querySelector('.grid').style.gridTemplateColumns=me.permissions.employees<3?'1fr':'';
 const hasEmployees=['employees','planning','worktime','reports'].some(m=>me.permissions[m]);el('employeeCard').hidden=!hasEmployees;
 if(hasEmployees)await refresh();else el('months').textContent='Keine Mitarbeiter-Module freigegeben.';}
async function refresh(){const users=await request('/api/v1/admin/tf');el('users').replaceChildren();for(const user of users){const tr=document.createElement('tr');
 for(const text of [user.first_name+' '+user.last_name,user.personnel_number]){const td=document.createElement('td');td.textContent=text;tr.append(td);}
 let td=document.createElement('td');
 if(me.permissions.employees){const email=document.createElement('input');email.type='email';email.value=user.email||'';email.setAttribute('aria-label','E-Mail '+user.first_name);
 const state=document.querySelector('#tfForm select[name=federal_state]').cloneNode(true);state.value=user.federal_state||'';state.setAttribute('aria-label','Bundesland '+user.first_name);
 email.disabled=state.disabled=me.permissions.employees<2;td.append(email,state);
 if(me.permissions.employees>=2){const save=document.createElement('button');save.textContent='Speichern';save.onclick=async()=>{save.disabled=true;try{await request('/api/v1/admin/tf/'+user.id+'/delivery',{method:'PATCH',body:JSON.stringify({email:email.value,federal_state:state.value})});await refresh();}catch(error){alert(error.message);}finally{save.disabled=false;}};td.append(save);}
 }else td.textContent='Nicht freigegeben';tr.append(td);td=document.createElement('td');td.textContent=me.permissions.employees?user.target_hours_minutes/60+' h / '+user.vacation_days+' Tage':'—';tr.append(td);
 td=document.createElement('td');if(me.permissions.worktime||me.permissions.reports){const button=document.createElement('button');button.textContent='Monatsdaten';button.onclick=()=>months(user).catch(error=>alert(error.message));td.append(button);}
 if(me.permissions.planning)link(td,'Arbeitszeitplan','/admin/planning?tf='+user.id);
 if(me.permissions.worktime)link(td,'Arbeitszeiten korrigieren','/admin/worktime?tf='+user.id);
 if(me.permissions.employees===3){const reset=document.createElement('button');reset.textContent='Passwort zurücksetzen';reset.onclick=()=>resetDialog(user);td.append(reset);}
 tr.append(td);el('users').append(tr);}}
function renderSummary(box,data){box.querySelector('#summary')?.remove();const target=document.createElement('div');target.id='summary';const h=document.createElement('h3');h.textContent='Monatsabrechnung · '+data.status;target.append(h);
 const table=document.createElement('table');function row(values,header=false){const tr=document.createElement('tr');for(const value of values){const cell=document.createElement(header?'th':'td');cell.textContent=value;tr.append(cell);}table.append(tr);}
 row(['Datum','Art','Arbeit ohne Gast','Gastfahrt','Auffüllung','Urlaub','Krank','Gutschrift'],true);
 for(const d of data.days)row([d.date,d.type,...[d.work_without_guest,d.guest,d.topup,d.vacation,d.sick,d.credited].map(clock)]);target.append(table);
 const p=document.createElement('p');p.textContent='Plansoll: '+clock(data.target_minutes)+' h · Gutschrift: '+clock(data.totals.credited)+' h · '+(data.planning.complete?'Saldo: '+clock(data.balance_minutes)+' h':data.planning.unplanned_days+' Tage ungeplant');target.append(p);box.append(target);}
async function months(user){const list=await request('/api/v1/admin/tf/'+user.id+'/months');const box=el('months');box.replaceChildren();const h=document.createElement('h3');h.textContent='Monatsdaten · '+user.first_name+' '+user.last_name;box.append(h);
 for(const m of list){const button=document.createElement('button');button.style.margin='5px';button.textContent=m.month+'/'+m.year+' · '+m.entry_count+' Einträge';button.onclick=async()=>{try{const data=await request('/api/v1/admin/tf/'+user.id+'/months/'+m.year+'/'+m.month+'/summary');renderSummary(box,data);}catch(error){alert(error.message);}};box.append(button);}
 if(!list.length)box.append('Noch keine Monatsdaten übermittelt.');
 if(me.permissions.reports){const reports=await request('/api/v1/admin/tf/'+user.id+'/reports');const title=document.createElement('h3');title.textContent='PDF-Versand';box.append(title);
 for(const report of reports){const p=document.createElement('p');p.textContent='#'+report.id+' · '+report.status+' · '+report.recipient_email+' · Versuche: '+report.attempts+(report.last_error?' · '+report.last_error:'');box.append(p);}}
}
function resetDialog(user){const dialog=document.createElement('dialog'),form=document.createElement('form'),h=document.createElement('h2'),label=document.createElement('label'),input=document.createElement('input'),message=document.createElement('p'),save=document.createElement('button'),cancel=document.createElement('button');
 h.textContent='Passwort zurücksetzen · '+user.first_name+' '+user.last_name;label.textContent='Neues Initialpasswort (mindestens 12 Zeichen)';input.type='password';input.required=true;input.minLength=12;input.maxLength=4096;input.autocomplete='new-password';label.append(input);save.textContent='Zurücksetzen';cancel.type='button';cancel.textContent='Abbrechen';cancel.onclick=()=>dialog.close();
 form.append(h,label,message,save,cancel);dialog.append(form);document.body.append(dialog);dialog.showModal();dialog.onclose=()=>dialog.remove();
 form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{await request('/api/v1/admin/accounts/'+user.id+'/reset-password',{method:'POST',body:JSON.stringify({initial_password:input.value})});input.value='';dialog.close();alert('Initialpasswort gesetzt. Passwortwechsel beim nächsten Login erforderlich.');}catch(error){message.textContent=error.message;}finally{save.disabled=false;}};}
el('loginForm').onsubmit=async event=>{event.preventDefault();try{const result=await request('/api/v1/admin/login',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});event.target.reset();if(result.password_change_required){location.href='/account';return;}await show();}catch(error){el('loginMessage').textContent=error.message;}};
el('tfForm').onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));data.target_hours_minutes=Math.round(Number(data.target_hours)*60);delete data.target_hours;data.vacation_days=Number(data.vacation_days);data.bahncard=Number(data.bahncard);
 try{await request('/api/v1/admin/tf',{method:'POST',body:JSON.stringify(data)});event.target.reset();el('tfMessage').className='ok';el('tfMessage').textContent='Tf angelegt. Initialpasswort muss beim ersten Login geändert werden.';await refresh();}catch(error){el('tfMessage').className='error';el('tfMessage').textContent=error.message;}};
el('logout').onclick=async()=>{try{await request('/api/v1/admin/logout',{method:'POST'});location.reload();}catch(error){alert(error.message);}};
show().catch(()=>{});
