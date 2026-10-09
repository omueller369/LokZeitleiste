const el = id => document.getElementById(id);
const clock = n => (n < 0 ? '-' : '') + Math.floor(Math.abs(n) / 60) + ':' + String(Math.abs(n) % 60).padStart(2, '0');
const names = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
let selected = null, data = null, editing = null, busy = false, dirty = false;
function message(text, error = false) { el('message').textContent = text; el('message').className = error ? 'error' : 'success';
  if (el('editDialog').open) el('editMessage').textContent = error ? text : ''; }
async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  if (!response.ok) {
    if (response.status === 401) { location.href = '/admin'; throw Error('Admin-Anmeldung erforderlich'); }
    const body = await response.json().catch(() => ({}));
    throw Error(typeof body.detail === 'string' ? body.detail : 'Anfrage fehlgeschlagen (' + response.status + ')');
  }
  return response.json();
}
const prefix = () => '/api/v1/admin/tf/' + selected.tf + '/worktime';
function row(body, values) { const tr = document.createElement('tr'); for (const value of values) {
  const td = document.createElement('td'); td.textContent = value; tr.append(td);
} body.append(tr); return tr; }
function render() {
  el('content').hidden = false; el('title').textContent = names[selected.month - 1] + ' ' + selected.year;
  el('metrics').replaceChildren();
  for (const [label, value] of [['Monatsarbeitszeit', data.month.totals.work_without_guest + data.month.totals.guest],
      ['Monatsgutschrift', data.month.totals.credited], ['Plansoll inkl. Urlaub', data.month.target_minutes]]) {
    const box = document.createElement('div'), strong = document.createElement('strong');
    strong.textContent = clock(value) + ' h'; box.append(strong, document.createTextNode(label)); el('metrics').append(box);
  }
  el('planning').textContent = data.month.planning.complete ? 'Saldo: ' + clock(data.month.balance_minutes) + ' h' :
    data.month.planning.unplanned_days + ' Tage ungeplant; Saldo wird erst bei vollständigem Plan berechnet.';
  for (const id of ['entries','days','weeks']) el(id).replaceChildren();
  el('empty').hidden = data.entries.length > 0;
  for (const entry of data.entries) {
    const tr = row(el('entries'), [entry.date, entry.kind]);
    const inputs = [];
    for (const field of ['start','end']) {
      const td = document.createElement('td'), input = document.createElement('input');
      input.type = 'time'; input.step = '60'; input.value = entry[field]; input.disabled = !entry.editable;
      input.setAttribute('aria-label', (field === 'start' ? 'Arbeitsbeginn ' : 'Arbeitsende ') + entry.date);
      input.oninput = () => { dirty = true;
        for (const other of el('entries').rows) if (other !== tr) other.querySelectorAll('input,button').forEach(control => control.disabled = true);
      }; inputs.push(input); td.append(input); tr.append(td);
    }
    for (const value of [entry.pause + ' min', entry.guest + ' min']) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
    const td = document.createElement('td');
    if (entry.editable) {
      const button = document.createElement('button'); button.textContent = 'Prüfen';
      button.onclick = () => {
        if (!inputs[0].value || !inputs[1].value) { message('Beginn und Ende eingeben.', true); return; }
        if (inputs[0].value === entry.start && inputs[1].value === entry.end) { message('Zeiten unverändert.'); return; }
        editing = {entry, start: inputs[0].value, end: inputs[1].value};
        el('comparison').textContent = entry.date + ' · ' + entry.kind + ': Beginn ' + entry.start + ' → ' + editing.start +
          '; Ende ' + entry.end + ' → ' + editing.end;
        el('reason').value = ''; el('editMessage').textContent = ''; el('editDialog').showModal();
      }; td.append(button);
    } else td.textContent = 'Keine Zeitkorrektur';
    tr.append(td);
  }
  for (const d of data.days) row(el('days'), [d.date,d.type,...[d.work,d.credited,d.topup,d.night,d.sunday,d.holiday].map(clock)]);
  for (const w of data.weeks) row(el('weeks'), ['KW ' + w.week + '/' + w.iso_year,w.start,w.end,clock(w.totals.work),clock(w.totals.credited)]);
}
async function history() {
  const changes = await api(prefix() + '/changes/history'); el('history').replaceChildren();
  for (const c of changes) {
    const box = document.createElement('div'); box.className = 'history';
    for (const text of [c.date + ' · Beginn ' + c.previous_start + ' → ' + c.new_start + '; Ende ' + c.previous_end + ' → ' + c.new_end,
        'Grund: ' + c.reason, 'Admin #' + c.admin_id + ' · ' + c.created_at + ' UTC',
        'E-Mail: ' + ({pending:'vorgemerkt',sent:'versendet',failed:'fehlgeschlagen'}[c.email_status] || c.email_status) +
          ' · ' + c.recipient_email + ' · Versuche: ' + c.attempts + (c.last_error ? ' · ' + c.last_error : '')]) {
      const p = document.createElement('p'); p.textContent = text; box.append(p);
    }
    if (c.email_status === 'failed') {
      const button = document.createElement('button'); button.textContent = 'E-Mail erneut senden';
      button.onclick = action(() => exclusive(async () => { await api(prefix() + '/changes/' + c.id + '/retry', {method:'POST'});
        await history(); message('Benachrichtigung erneut vorgemerkt.'); })); box.append(button);
    }
    el('history').append(box);
  }
  if (!changes.length) el('history').textContent = 'Noch keine Arbeitszeitkorrekturen.';
}
async function load(force = false) {
  if (dirty && !force && !confirm('Ungespeicherte Zeiteingaben verwerfen?')) {
    el('tf').value = selected.tf; el('year').value = selected.year; el('month').value = selected.month; return;
  }
  const next = {tf:el('tf').value,year:Number(el('year').value),month:Number(el('month').value)};
  if (!next.tf || !Number.isInteger(next.year) || next.year < 2000 || next.year > 2100) throw Error('Mitarbeiter und gültiges Jahr wählen.');
  const result = await api('/api/v1/admin/tf/' + next.tf + '/worktime/months/' + next.year + '/' + next.month);
  selected = next; data = result; dirty = false; render(); await history(); message('Arbeitszeiten geladen.');
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
  const result = await api(prefix() + '/entries/' + editing.entry.id, {method:'PATCH',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({start:editing.start,end:editing.end,expected_updated_at:editing.entry.updated_at,reason:el('reason').value})});
  el('editDialog').close(); dirty = false; await load(true);
  message(result.changed ? 'Arbeitszeit gespeichert und neu berechnet. E-Mail vorgemerkt; Versandstatus siehe Verlauf.' : 'Zeiten unverändert.');
}))(); };
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
(async () => {
  const now = new Date(); el('year').value = now.getFullYear();
  for (let i = 0; i < 12; i++) { const option = document.createElement('option'); option.value = i + 1; option.textContent = names[i]; el('month').append(option); }
  el('month').value = now.getMonth() + 1;
  try {
    const users = await api('/api/v1/admin/tf');
    for (const user of users) { const option = document.createElement('option'); option.value = user.id;
      option.textContent = user.first_name + ' ' + user.last_name + ' · ' + user.personnel_number; el('tf').append(option); }
    const tf = new URLSearchParams(location.search).get('tf'); if (users.some(u => String(u.id) === tf)) el('tf').value = tf;
    if (users.length) await exclusive(() => load()); else message('Zuerst einen Mitarbeiter anlegen.');
  } catch (error) { message(error.message, true); }
})();
