const el = id => document.getElementById(id);
const kinds = ['Arbeitstag', 'Urlaub', 'Ruhetag', 'Ungeplant'];
const codes = {Arbeitstag: 'A', Urlaub: 'U', Ruhetag: 'R', Ungeplant: '?'};
const names = ['Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember'];
let current = null, saved = null, annual = null, importData = null, dirty = false;
let accessLevel = 0;
let view = 'calendar', activeDay = null, loadTicket = 0, busy = false;
const clock = n => Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
function message(text, error = false) {
  el('message').textContent = text;
  el('message').className = 'message ' + (error ? 'error' : 'success');
}
async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  if (!response.ok) {
    if (response.status === 401) { location.href = '/admin'; throw Error('Admin-Anmeldung erforderlich'); }
    const data = await response.json().catch(() => ({}));
    throw Error(typeof data.detail === 'string' ? data.detail : 'Anfrage fehlgeschlagen (' + response.status + ')');
  }
  return response.json();
}
const prefix = () => '/api/v1/admin/tf/' + saved.tf + '/plan/' + saved.year;
function clearPreview() { importData = null; el('preview').hidden = true; }
function switchView(next) {
  view = next;
  document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.view === view)));
  el('editor').hidden = !current || !['calendar', 'list'].includes(view);
  el('calendar').hidden = view !== 'calendar';
  el('listPanel').hidden = view !== 'list';
  el('annual').hidden = !current || view !== 'year';
  el('importer').hidden = !current || view !== 'excel';
}
function updateMetrics() {
  const counts = Object.fromEntries(kinds.map(kind => [kind, current.days.filter(day => day.kind === kind).length]));
  el('metrics').replaceChildren();
  for (const [label, value] of [['Arbeitstage', counts.Arbeitstag], ['Urlaubstage', counts.Urlaub],
      ['Ruhetage', counts.Ruhetag], ['Arbeitssoll', clock(counts.Arbeitstag * 480) + ' h'],
      ['Soll inkl. Urlaub', clock((counts.Arbeitstag + counts.Urlaub) * 480) + ' h']]) {
    const box = document.createElement('div'), strong = document.createElement('strong');
    strong.textContent = value; box.append(strong, document.createTextNode(label)); el('metrics').append(box);
  }
  el('status').textContent = (dirty ? 'Ungespeichert · ' : '') + (counts.Ungeplant ? counts.Ungeplant + ' Tage ungeplant' : 'Vollständig geplant');
}
function changeDay(day, kind, note) {
  day.kind = kind; day.note = kind === 'Ungeplant' ? '' : note;
  dirty = true; updateMetrics(); renderCalendar(); clearPreview();
  message('Ungespeicherte Änderungen. PDFs und Jahresansicht zeigen den gespeicherten Stand.');
}
function renderCalendar() {
  const grid = el('calendar'); grid.replaceChildren();
  for (const name of ['Mo','Di','Mi','Do','Fr','Sa','So']) {
    const cell = document.createElement('div'); cell.className = 'weekday'; cell.textContent = name; grid.append(cell);
  }
  const offset = (new Date(saved.year, saved.month - 1, 1).getDay() + 6) % 7;
  for (let i = 0; i < offset; i++) grid.append(document.createElement('div'));
  for (const day of current.days) {
    const button = document.createElement('button'); button.className = 'day'; button.type = 'button'; button.dataset.kind = day.kind;
    const number = document.createElement('b'); number.textContent = Number(day.date.slice(-2));
    const label = document.createElement('span'); label.textContent = day.kind;
    const hours = document.createElement('span'); hours.textContent = day.kind === 'Ungeplant' ? 'Offen' : day.kind === 'Ruhetag' ? '0:00 h' : '8:00 h';
    const note = document.createElement('small'); note.textContent = day.note;
    button.append(number, label, hours, note); button.setAttribute('aria-label', day.date + ', ' + day.kind + ', bearbeiten');
    button.disabled = accessLevel < 2;
    button.onclick = () => {
      activeDay = day; el('dayTitle').textContent = 'Tag bearbeiten · ' + day.date;
      el('dayKind').value = day.kind; el('dayNote').value = day.note;
      el('dayNote').disabled = day.kind === 'Ungeplant'; el('dayDialog').showModal();
    };
    grid.append(button);
  }
}
function renderDays() {
  const body = el('days'); body.replaceChildren();
  for (const day of current.days) {
    const row = document.createElement('tr'); row.dataset.kind = day.kind;
    const check = document.createElement('input'); check.type = 'checkbox'; check.setAttribute('aria-label', day.date + ' auswählen');
    let cell = document.createElement('td'); cell.append(check); row.append(cell);
    for (const value of [day.date, new Date(day.date + 'T12:00:00').toLocaleDateString('de-DE', {weekday: 'long'})]) {
      cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    const select = document.createElement('select'); select.setAttribute('aria-label', 'Tagesart ' + day.date);
    for (const kind of kinds) { const option = document.createElement('option'); option.textContent = kind; select.append(option); }
    select.disabled = accessLevel < 2; check.disabled = accessLevel < 2;
    select.value = day.kind; cell = document.createElement('td'); cell.append(select); row.append(cell);
    const hours = document.createElement('td'); hours.textContent = day.kind === 'Ungeplant' ? 'Offen' : day.kind === 'Ruhetag' ? '0:00' : '8:00'; row.append(hours);
    const note = document.createElement('input'); note.type = 'text'; note.maxLength = 500; note.value = day.note;
    note.disabled = accessLevel < 2 || day.kind === 'Ungeplant'; note.setAttribute('aria-label', 'Notiz ' + day.date);
    cell = document.createElement('td'); cell.append(note); row.append(cell);
    select.onchange = () => {
      changeDay(day, select.value, note.value); row.dataset.kind = day.kind; note.value = day.note;
      note.disabled = day.kind === 'Ungeplant'; hours.textContent = day.kind === 'Ungeplant' ? 'Offen' : day.kind === 'Ruhetag' ? '0:00' : '8:00';
    };
    note.oninput = () => changeDay(day, day.kind, note.value);
    body.append(row);
  }
  el('selectAll').checked = false;
}
function renderYear() {
  el('yearRows').replaceChildren();
  const table = document.createElement('table'); table.className = 'yearmatrix';
  const head = document.createElement('tr');
  for (const value of ['Monat', ...Array.from({length: 31}, (_, i) => i + 1), 'Soll h']) {
    const th = document.createElement('th'); th.textContent = value; head.append(th);
  }
  table.append(head);
  for (const month of annual.months) {
    const row = document.createElement('tr');
    for (const value of [names[month.month - 1], month.work_days, month.vacation_days, month.rest_days,
        month.unplanned_days, clock(month.work_target_minutes) + ' h', clock(month.target_minutes) + ' h']) {
      const td = document.createElement('td'); td.textContent = value; row.append(td);
    }
    el('yearRows').append(row);
    const matrixRow = document.createElement('tr'), label = document.createElement('td');
    label.textContent = names[month.month - 1]; matrixRow.append(label);
    for (let i = 0; i < 31; i++) {
      const td = document.createElement('td'), day = month.days[i];
      if (day) {
        const button = document.createElement('button'); button.textContent = codes[day.kind]; button.dataset.kind = day.kind;
        button.title = day.date + ' · ' + day.kind; button.setAttribute('aria-label', button.title);
        button.onclick = handle(() => exclusive(async () => { el('month').value = month.month; if (await load()) switchView('calendar'); }));
        td.append(button);
      }
      matrixRow.append(td);
    }
    const total = document.createElement('td'); total.textContent = clock(month.target_minutes); matrixRow.append(total); table.append(matrixRow);
  }
  el('yearMatrix').replaceChildren(table);
  el('annualSummary').textContent = 'Gespeicherter Jahresplan: ' + annual.totals.work_days + ' Arbeitstage · ' + annual.totals.vacation_days +
    ' Urlaubstage · ' + clock(annual.totals.target_minutes) + ' h Soll inkl. Urlaub · ' + annual.totals.unplanned_days + ' Tage ungeplant. A = Arbeit, U = Urlaub, R = Ruhe, ? = ungeplant.';
}
async function load(force = false) {
  if (dirty && !force && !confirm('Ungespeicherte Änderungen verwerfen?')) {
    el('tf').value = saved.tf; el('year').value = saved.year; el('month').value = saved.month; return false;
  }
  const year = Number(el('year').value), month = Number(el('month').value), tf = el('tf').value;
  if (!tf) throw Error('Zuerst einen Tf in der Verwaltung anlegen.');
  if (year < 2000 || year > 2100 || !Number.isInteger(year)) throw Error('Jahr zwischen 2000 und 2100 wählen.');
  const ticket = ++loadTicket, base = '/api/v1/admin/tf/' + tf + '/plan/' + year;
  const [data, yearData, history] = await Promise.all([api(base + '/' + month), api(base), api(base + '/history')]);
  if (ticket !== loadTicket) return false;
  saved = {tf, year, month}; current = data; annual = yearData; dirty = false; clearPreview();
  el('title').textContent = names[month - 1] + ' ' + year;
  updateMetrics(); renderDays(); renderCalendar(); renderYear(); switchView(view);
  el('monthPdf').href = base + '/' + month + '/pdf'; el('yearPdf').href = base + '/pdf'; el('template').href = base + '/template.xlsx';
  el('history').replaceChildren();
  for (const item of history) {
    const line = document.createElement('p'); line.textContent = item.date + ': ' + item.previous_kind + ' → ' + item.new_kind +
      ' · ' + (item.source === 'excel' ? 'Excel-Import' : 'Manuell') + ' · Admin #' + item.admin_id + ' · ' + item.changed_at + ' UTC'; el('history').append(line);
  }
  if (!history.length) el('history').textContent = 'Noch keine Planänderungen.';
  message('Plan geladen.'); return true;
}
const handle = fn => async () => { try { await fn(); } catch (error) { message(error.message, true); } };
async function exclusive(fn) {
  if (busy) return;
  busy = true; for (const id of ['editor','annual','importer']) el(id).inert = true;
  document.querySelectorAll('[data-view]').forEach(button => button.disabled = true);
  const ids = ['tf','year','month','load','save','inspect','confirm','bulk']; ids.forEach(id => el(id).disabled = true);
  try { await fn(); } finally { busy = false; ids.forEach(id => el(id).disabled = false);
    for (const id of ['editor','annual','importer']) el(id).inert = false;
    document.querySelectorAll('[data-view]').forEach(button => button.disabled = false); }
}
el('load').onclick = handle(() => exclusive(() => load()));
for (const id of ['tf','year','month']) el(id).onchange = handle(() => exclusive(() => load()));
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => switchView(button.dataset.view));
el('dayKind').onchange = () => { el('dayNote').disabled = el('dayKind').value === 'Ungeplant'; if (el('dayNote').disabled) el('dayNote').value = ''; };
el('closeDay').onclick = () => el('dayDialog').close();
el('dayForm').onsubmit = event => { event.preventDefault(); changeDay(activeDay, el('dayKind').value, el('dayNote').value); renderDays(); el('dayDialog').close(); };
el('selectAll').onchange = () => el('days').querySelectorAll('input[type=checkbox]').forEach(x => x.checked = el('selectAll').checked);
el('bulk').onclick = () => { for (const row of el('days').rows) if (row.querySelector('input[type=checkbox]').checked) {
  const select = row.querySelector('select'); select.value = el('bulkKind').value; select.onchange();
} };
el('save').onclick = handle(() => exclusive(async () => {
  await api(prefix() + '/' + saved.month, {method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({expected_revision: current.revision, days: current.days.map(({date,kind,note}) => ({date,kind,note}))})});
  await load(true); message('Monatsplan gespeichert.');
}));
el('inspect').onclick = handle(() => exclusive(async () => {
  if (dirty) throw Error('Bitte Monatsänderungen zuerst speichern oder den Plan neu laden.');
  const file = el('excel').files[0]; if (!file) throw Error('Bitte eine XLSX-Datei auswählen.');
  clearPreview(); const form = new FormData(); form.append('file', file);
  importData = await api(prefix() + '/import/preview', {method: 'POST', body: form}); el('importDays').replaceChildren();
  for (const day of importData.days) {
    const row = document.createElement('tr'); row.dataset.kind = day.kind;
    for (const value of [day.date, day.previous_kind, day.kind, day.note]) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    el('importDays').append(row);
  }
  el('importCount').textContent = importData.days.length + ' Tageszeilen geprüft. Nur diese Datumszeilen werden übernommen.';
  el('preview').hidden = false; message('Import geprüft. Bitte Vorschau kontrollieren.');
}));
el('confirm').onclick = handle(() => exclusive(async () => {
  if (!importData) throw Error('Zuerst Import prüfen.'); if (dirty) throw Error('Ungespeicherte Monatsänderungen vorhanden.');
  const result = await api(prefix() + '/import', {method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({days: importData.days.map(({date,kind,note}) => ({date,kind,note})), expected_revisions: importData.expected_revisions})});
  await load(true); message(result.changed_days + ' Tagesplanungen aus Excel übernommen.');
}));
el('cancel').onclick = clearPreview;
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
(async () => {
  const now = new Date(); el('year').value = now.getFullYear();
  for (let i = 0; i < 12; i++) { const option = document.createElement('option'); option.value = i + 1; option.textContent = names[i]; el('month').append(option); }
  el('month').value = now.getMonth() + 1;
  try {
    const account = await api('/api/v1/account/me');
    if (account.password_change_required) { location.href = '/account'; return; }
    accessLevel = account.permissions.planning;
    if (!accessLevel) throw Error('Keine Freigabe für das Planungsmodul.');
    if (accessLevel < 2) {
      for (const id of ['save','bulk','inspect','confirm','excel','selectAll']) el(id).hidden = true;
      document.querySelector('[data-view=excel]').hidden = true;
    }
    const users = await api('/api/v1/admin/tf');
    for (const user of users) { const option = document.createElement('option'); option.value = user.id;
      option.textContent = user.first_name + ' ' + user.last_name + ' · ' + user.personnel_number; el('tf').append(option); }
    const selected = new URLSearchParams(location.search).get('tf'); if (users.some(u => String(u.id) === selected)) el('tf').value = selected;
    if (users.length) await exclusive(() => load()); else message('Zuerst einen Tf in der Verwaltung anlegen.');
  } catch (error) { message(error.message, true); }
})();
