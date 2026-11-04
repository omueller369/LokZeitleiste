function endDate(entry){if(entry.end_date)return entry.end_date;const d=new Date(entry.date+'T12:00:00');if(entry.end<=entry.start)d.setDate(d.getDate()+1);return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
const el = id => document.getElementById(id);
const clock = n => (n < 0 ? '-' : '') + Math.floor(Math.abs(n) / 60) + ':' + String(Math.abs(n) % 60).padStart(2, '0');
const names = [globalThis.CtlText.source("backend_worktime.text_e3e144a75b27"),globalThis.CtlText.source("backend_worktime.text_742d257d7283"),globalThis.CtlText.source("backend_worktime.text_86ac4d676251"),globalThis.CtlText.source("backend_worktime.text_4afe6ea150d5"),globalThis.CtlText.source("backend_worktime.text_d77b6bd0886e"),globalThis.CtlText.source("backend_worktime.text_130d0a280e7e"),globalThis.CtlText.source("backend_worktime.text_161f3271aeb4"),globalThis.CtlText.source("backend_worktime.text_a66d8970e569"),globalThis.CtlText.source("backend_worktime.text_cd559ea0abca"),globalThis.CtlText.source("backend_worktime.text_4e1056bfe86b"),globalThis.CtlText.source("backend_worktime.text_9de6fe1d7265"),globalThis.CtlText.source("backend_worktime.text_4bd7dd175722")];
let accessLevel = 0, manualForm = null;
let selected = null, data = null, editing = null, busy = false, dirty = false;
function message(text, error = false) { el('message').textContent = text; el('message').className = error ? 'error' : 'success';
  if (el('editDialog').open) el('editMessage').textContent = error ? text : ''; }
async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  if (!response.ok) {
    if (response.status === 401) { location.href = '/admin'; throw Error(globalThis.CtlText.source("backend_worktime.text_935382ae5851")); }
    const body = await response.json().catch(() => ({}));
    throw Error(typeof body.detail === 'string' ? body.detail : globalThis.CtlText.source("backend_worktime.text_926e66e23dec") + response.status + ')');
  }
  return response.json();
}
const prefix = () => '/api/v1/admin/tf/' + selected.tf + '/worktime';
function row(body, values) { const tr = document.createElement('tr'); for (const value of values) {
  const td = document.createElement('td'); td.textContent = value; tr.append(td);
} body.append(tr); return tr; }
function render() {
  el('submitEdit').textContent=data.role==='tf'?globalThis.CtlText.source("backend_worktime.text_01a56c916c95"):globalThis.CtlText.source("backend_worktime.text_94d9b2aae457");el('notificationNote').textContent=data.role==='tf'?globalThis.CtlText.source("backend_worktime.text_21d68819f049"):globalThis.CtlText.source("backend_worktime.text_c9f223d18f12");
  el('content').hidden = false; el('title').textContent = names[selected.month - 1] + ' ' + selected.year;
  el('metrics').replaceChildren();
  for (const [label, value] of [[globalThis.CtlText.source("backend_worktime.text_6d076e092638"), data.month.totals.work_without_guest + data.month.totals.guest],
      [globalThis.CtlText.source("backend_worktime.text_fa3f3eb687ec"), data.month.totals.credited], [globalThis.CtlText.source("backend_worktime.text_823becc01b72"), data.month.target_minutes]]) {
    const box = document.createElement('div'), strong = document.createElement('strong');
    strong.textContent = value==null?'—':clock(value) + ' h'; box.append(strong, document.createTextNode(label)); el('metrics').append(box);
  }
  el('planning').textContent = !data.month.planning ? globalThis.CtlText.source("backend_worktime.text_9643088e978b") : data.month.planning.complete ? globalThis.CtlText.source("backend_worktime.text_c3fa0e63c306") + clock(data.month.balance_minutes) + ' h' :
    data.month.planning.unplanned_days + globalThis.CtlText.source("backend_worktime.text_ce6b745aedde");
  for (const id of ['entries','days','weeks']) el(id).replaceChildren();
  el('empty').hidden = data.entries.length > 0;
  for (const entry of data.entries) {
    entry.editable=[globalThis.CtlText.source("backend_worktime.text_52c5d4a0445b"),globalThis.CtlText.source("backend_worktime.text_f31b8681bfca"),globalThis.CtlText.source("backend_worktime.text_a88b0d6dfef3")].includes(entry.kind)&&!entry.locked;
    const tr = row(el('entries'), [entry.date, entry.kind+(entry.locked?globalThis.CtlText.source("backend_worktime.text_8bb6ad99cbeb"):'')]);
    const inputs = [];
    for (const field of ['start','end','end_date']) {
      const td = document.createElement('td'), input = document.createElement('input');
      input.type = field==='end_date'?'date':'time'; input.step = field==='end_date'?'1':'60'; input.value = field==='end_date'?endDate(entry):entry[field];if(field==='end_date')input.min=entry.date; input.disabled = accessLevel < 2 || !entry.editable;
      input.setAttribute('aria-label', (field === 'start' ? globalThis.CtlText.source("backend_worktime.text_0f6dba7af022") : field==='end_date'?globalThis.CtlText.source("backend_worktime.text_04ff2d0045ac"):globalThis.CtlText.source("backend_worktime.text_574b19674395")) + entry.date);
      input.oninput = () => { dirty = true;
        for (const other of el('entries').rows) if (other !== tr) other.querySelectorAll('input,button').forEach(control => control.disabled = true);
      }; inputs.push(input); td.append(input); tr.append(td);
    }
    for (const value of [entry.pause + globalThis.CtlText.source("backend_worktime.text_2e75737a6b58"), entry.guest + globalThis.CtlText.source("backend_worktime.text_2e75737a6b58")]) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
    const td = document.createElement('td');
    if (accessLevel >= 2 && entry.editable) {
      const button = document.createElement('button'); button.textContent = globalThis.CtlText.source("backend_worktime.text_a1ca13575987");
      button.onclick = () => {
        if (!inputs[0].value || !inputs[1].value||!inputs[2].value) { message(globalThis.CtlText.source("backend_worktime.text_042c3ad732f4"), true); return; }
        if (inputs[0].value === entry.start && inputs[1].value === entry.end&&inputs[2].value===endDate(entry)) { message(globalThis.CtlText.source("backend_worktime.text_dcf11d0f1bca")); return; }
        editing = {entry, start: inputs[0].value, end: inputs[1].value,end_date:inputs[2].value};
        el('comparison').textContent = entry.date + ' · ' + entry.kind + ': Beginn ' + entry.start + ' → ' + editing.start +
          globalThis.CtlText.source("backend_worktime.text_e4e8e850d125") + entry.end + ' → ' + editing.end+globalThis.CtlText.source("backend_worktime.text_4f10719c3f49")+endDate(entry)+' → '+editing.end_date;
        el('reason').value = ''; el('editMessage').textContent = ''; el('editDialog').showModal();
      }; td.append(button);
    } else td.textContent = globalThis.CtlText.source("backend_worktime.text_a82151bdb761");
    recordLockButton(td,entry,accessLevel,()=>load(true));tr.append(td);
  }
  for (const d of data.days) row(el('days'), [d.date,d.type,...[d.work,d.credited,d.topup,d.night,d.sunday,d.holiday].map(clock)]);
  for (const w of data.weeks) row(el('weeks'), ['KW ' + w.week + '/' + w.iso_year,w.start,w.end,clock(w.totals.work),clock(w.totals.credited)]);
}
async function history() {
  const changes = data.role==='tf'?await api(prefix() + '/changes/history'):[]; el('history').replaceChildren();
  for (const c of changes) {
    const box = document.createElement('div'); box.className = 'history';
    for (const text of [c.date + globalThis.CtlText.source("backend_worktime.text_d0e0faaee11b") + c.previous_start + ' → ' + c.new_start + globalThis.CtlText.source("backend_worktime.text_e4e8e850d125") + c.previous_end + ' → ' + c.new_end,
        globalThis.CtlText.source("backend_worktime.text_9c779a6d5a2e")+(c.end_date_change||globalThis.CtlText.source("backend_worktime.text_adc1b8f3c384")), globalThis.CtlText.source("backend_worktime.text_8446867dbbc4") + c.reason, globalThis.CtlText.source("backend_worktime.text_3ee581183dbf") + c.admin_id + ' · ' + c.created_at + globalThis.CtlText.source("backend_worktime.text_de92d152d782"),
        globalThis.CtlText.source("backend_worktime.text_560185323bd6") + ({pending:'vorgemerkt',sent:'versendet',failed:globalThis.CtlText.source("backend_worktime.text_e650a8f75edf")}[c.email_status] || c.email_status) +
          ' · ' + c.recipient_email + globalThis.CtlText.source("backend_worktime.text_0cbd67dd0c1f") + c.attempts + (c.last_error ? ' · ' + c.last_error : '')]) {
      const p = document.createElement('p'); p.textContent = text; box.append(p);
    }
    if (accessLevel >= 2 && c.email_status === 'failed') {
      const button = document.createElement('button'); button.textContent = globalThis.CtlText.source("backend_worktime.text_c53af66563cf");
      button.onclick = action(() => exclusive(async () => { await api(prefix() + '/changes/' + c.id + '/retry', {method:'POST'});
        await history(); message(globalThis.CtlText.source("backend_worktime.text_13627ed53d53")); })); box.append(button);
    }
    el('history').append(box);
  }
  const audits=await api('/api/v1/admin/worktime/users/'+selected.tf+'/audit');
  for(const item of audits){const p=document.createElement('p');p.textContent=({'manual_created':globalThis.CtlText.source("backend_worktime.text_05dc77040983"),'manual_updated':globalThis.CtlText.source("backend_worktime.text_72c89f093f77"),'locked':globalThis.CtlText.source("backend_worktime.text_45f96e916050"),'unlocked':globalThis.CtlText.source("backend_worktime.text_1f29b0671506")}[item.action]||item.action)+globalThis.CtlText.source("backend_worktime.text_7bf28a5ed789")+item.entry_id+' · '+item.reason+globalThis.CtlText.source("backend_worktime.text_5953820b78b0")+item.actor_id+' · '+item.created_at+globalThis.CtlText.source("backend_worktime.text_de92d152d782");el('history').append(p);}
  if (!changes.length&&!audits.length) el('history').textContent = globalThis.CtlText.source("backend_worktime.text_1b9031026550");
}
async function load(force = false) {
  if (dirty && !force && !confirm(globalThis.CtlText.source("backend_worktime.text_045d9db46531"))) {
    el('tf').value = selected.tf; el('year').value = selected.year; el('month').value = selected.month; return;
  }
  const next = {tf:el('tf').value,year:Number(el('year').value),month:Number(el('month').value)};
  if (!next.tf || !Number.isInteger(next.year) || next.year < 2000 || next.year > 2100) throw Error(globalThis.CtlText.source("backend_worktime.text_3e1e53e8a99d"));
  const result = await api('/api/v1/admin/worktime/users/' + next.tf + '/months/' + next.year + '/' + next.month);
  if(dirty)manualForm?.resetEntry();selected = next; data = result; dirty = false; render(); await history(); message(globalThis.CtlText.source("backend_worktime.text_6464de110988"));
}
const action = fn => async () => { try { await fn(); } catch (error) { message(error.message, true); } };
async function exclusive(fn) {
  if (busy) return; busy = true; el('content').inert = true;
  for (const id of ['tf','year','month','load','submitEdit','cancelEdit']) el(id).disabled = true;
  try { await fn(); } finally { busy = false; el('content').inert = false;
    for (const id of ['tf','year','month','load','submitEdit','cancelEdit']) el(id).disabled = false; }
}
for (const id of ['tf','year','month']) el(id).onchange = action(() => exclusive(() => load()));
el('load').onclick = action(() => exclusive(() => load()));
el('refreshHistory').onclick = action(() => exclusive(history));
el('cancelEdit').onclick = () => el('editDialog').close();
el('editForm').onsubmit = event => { event.preventDefault(); action(() => exclusive(async () => {
  const result = await api(data.role==='tf'?prefix() + '/entries/' + editing.entry.id:'/api/v1/admin/worktime/entries/'+editing.entry.id, {method:'PATCH',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({start:editing.start,end:editing.end,end_date:editing.end_date,expected_updated_at:editing.entry.updated_at,reason:el('reason').value})});
  el('editDialog').close(); dirty = false; await load(true);
  message(result.changed&&data.role==='staff'?globalThis.CtlText.source("backend_worktime.text_d682e69d99c2"):result.changed ? globalThis.CtlText.source("backend_worktime.text_9f526c5eed70") : globalThis.CtlText.source("backend_worktime.text_dcf11d0f1bca"));
}))(); };
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
(async () => {
  const now = new Date(); el('year').value = now.getFullYear();
  for (let i = 0; i < 12; i++) { const option = document.createElement('option'); option.value = i + 1; option.textContent = names[i]; el('month').append(option); }
  el('month').value = now.getMonth() + 1;
  try {
    const account = await api('/api/v1/account/me');
    if (account.password_change_required) { location.href = '/account'; return; }
    accessLevel = account.permissions.worktime;
    if (!accessLevel) throw Error(globalThis.CtlText.source("backend_worktime.text_e3068228eaf6"));
    el('manualCard').hidden=accessLevel<2;
    manualForm=attachEntryForm(el('manualForm'),()=>'/api/v1/admin/worktime/users/'+selected.tf+'/entries',async()=>{dirty=false;await load(true);},()=>dirty=true);
    const users = await api('/api/v1/admin/worktime/users');
    for (const user of users) { const option = document.createElement('option'); option.value = user.id;
      option.textContent = (user.role==='staff'?globalThis.CtlText.source("backend_worktime.text_1edbb8d0444f"):'Tf · ')+user.first_name + ' ' + user.last_name + ' · ' + user.personnel_number; el('tf').append(option); }
    const tf = new URLSearchParams(location.search).get('tf'); if (users.some(u => String(u.id) === tf)) el('tf').value = tf;
    if (users.length) await exclusive(() => load()); else message(globalThis.CtlText.source("backend_worktime.text_58e723bf4b22"));
  } catch (error) { message(error.message, true); }
})();
