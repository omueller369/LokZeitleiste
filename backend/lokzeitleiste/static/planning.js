const el = id => document.getElementById(id);
const kinds = [globalThis.CtlText.source("backend_planning.text_eb8f579b6931"), globalThis.CtlText.source("backend_planning.text_35d3a889824d"), globalThis.CtlText.source("backend_planning.text_e79aa42d7d18"), globalThis.CtlText.source("backend_planning.text_52e37a639da5")];
const codes = {Arbeitstag: 'A', Urlaub: 'U', Ruhetag: 'R', Ungeplant: '?'};
function planColor(node,day){node.dataset.status=day.kind;window.PlanColors.apply(node,day);}
const shiftLabels={standard:globalThis.CtlText.source("backend_planning.text_77d64b3ca8ca"),border_day:globalThis.CtlText.source("backend_planning.text_6c9b9f7f7346"),border_night:globalThis.CtlText.source("backend_planning.text_04b9a3e19613")};
function dayCode(day){return day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")&&day.shift==='border_day'?'GT':day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")&&day.shift==='border_night'?'GN':codes[day.kind];}
function dutyLabel(day){return day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")&&day.shift!=='standard'?shiftLabels[day.shift]+' · '+(day.shift==='border_day'?'09:00–21:00':globalThis.CtlText.source("backend_planning.text_a0e778398815")):'';}
function updateDuty(day){day.shift=day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?(day.shift||'standard'):'standard';day.planned_minutes=day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?(day.shift==='standard'?480:720):day.kind===globalThis.CtlText.source("backend_planning.text_35d3a889824d")?480:0;day.target_minutes=day.is_holiday?0:day.planned_minutes;}
function shiftOptions(select){select.replaceChildren();for(const [value,label]of Object.entries(shiftLabels)){const o=document.createElement('option');o.value=value;o.textContent=label;o.disabled=value!=='standard'&&annual?.driver_type==='route';select.append(o);}}
function planLabel(day){return day.is_holiday?globalThis.CtlText.source("backend_planning.text_0221159ab095")+day.holiday_name+(day.kind!==globalThis.CtlText.source("backend_planning.text_52e37a639da5")?' · '+day.kind:''):day.kind;}
const names = [globalThis.CtlText.source("backend_planning.text_e3e144a75b27"),globalThis.CtlText.source("backend_planning.text_742d257d7283"),globalThis.CtlText.source("backend_planning.text_86ac4d676251"),globalThis.CtlText.source("backend_planning.text_4afe6ea150d5"),globalThis.CtlText.source("backend_planning.text_d77b6bd0886e"),globalThis.CtlText.source("backend_planning.text_130d0a280e7e"),globalThis.CtlText.source("backend_planning.text_161f3271aeb4"),globalThis.CtlText.source("backend_planning.text_a66d8970e569"),globalThis.CtlText.source("backend_planning.text_cd559ea0abca"),globalThis.CtlText.source("backend_planning.text_4e1056bfe86b"),globalThis.CtlText.source("backend_planning.text_9de6fe1d7265"),globalThis.CtlText.source("backend_planning.text_4bd7dd175722")];
let current = null, saved = null, annual = null, importData = null, dirty = false;
let accessLevel = 0;
const selection=new Set(), previewSelection=new Set();let originals=new Map();
function scopeDays(){return view==='excel'?(importData?.days||[]):view==='year'?(annual?.months.flatMap(m=>m.days)||[]):(current?.days||[]);}
function selectedSet(){return view==='excel'?previewSelection:selection;}
function selectionStatus(){el('selectionEdit').disabled=busy||accessLevel<2||!selectedSet().size;el('selectionCount').textContent=selectedSet().size+globalThis.CtlText.source("backend_planning.text_09b1601c4271");el('selectAll').checked=scopeDays().length>0&&scopeDays().every(d=>selectedSet().has(d.date));}
function toggleDate(date){const set=selectedSet();set.has(date)?set.delete(date):set.add(date);renderCalendar();renderDays();renderYear();renderPreview();selectionStatus();}
function changedDays(){return annual.months.flatMap(m=>m.days).filter(d=>JSON.stringify([d.kind,d.note,d.shift||'standard'])!==originals.get(d.date));}
function syncDraft(){dirty=changedDays().length>0;updateMetrics();renderYear();selectionStatus();}
function renderPreview(){if(!importData)return;el('importDays').replaceChildren();for(const day of importData.days){const tr=document.createElement('tr');tr.dataset.kind=day.is_holiday?globalThis.CtlText.source("backend_planning.text_ecda07db6e0b"):day.kind;planColor(tr,day);const td=document.createElement('td'),check=document.createElement('input');check.type='checkbox';check.checked=previewSelection.has(day.date);check.setAttribute('aria-label',day.date+globalThis.CtlText.source("backend_planning.text_77b8aa5c0d7e"));check.onchange=()=>toggleDate(day.date);td.append(check);tr.append(td);for(const v of [day.date,day.previous_kind,day.is_holiday?globalThis.CtlText.source("backend_planning.text_0221159ab095")+day.holiday_name+globalThis.CtlText.source("backend_planning.text_c48f93e249d3")+day.kind+')':day.kind,day.note]){const c=document.createElement('td');c.textContent=v;tr.append(c);}el('importDays').append(tr);}}
let activeSelection=null;
let view = 'calendar', activeDay = null, loadTicket = 0, busy = false;
const clock = n => Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
function message(text, error = false) {
  el('message').textContent = text;
  el('message').className = 'message ' + (error ? 'error' : 'success');
}
async function api(path, options = {}) {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  if (!response.ok) {
    if (response.status === 401) { location.href = '/admin'; throw Error(globalThis.CtlText.source("backend_planning.text_935382ae5851")); }
    const data = await response.json().catch(() => ({}));
    throw Error(typeof data.detail === 'string' ? data.detail : globalThis.CtlText.source("backend_planning.text_926e66e23dec") + response.status + ')');
  }
  return response.json();
}
const prefix = () => '/api/v1/admin/tf/' + saved.tf + '/plan/' + saved.year;
function clearPreview() { previewSelection.clear();importData = null; el('preview').hidden = true;if(current)selectionStatus(); }
function switchView(next) {
  view = next;selectionStatus();el('selectionTools').hidden=!current||accessLevel<2;
  document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.view === view)));
  el('editor').hidden = !current || !['calendar', 'list'].includes(view);
  el('calendar').hidden = view !== 'calendar';
  el('listPanel').hidden = view !== 'list';
  el('annual').hidden = !current || view !== 'year';
  el('importer').hidden = !current || view !== 'excel';
}
function updateMetrics() {
  const counts = Object.fromEntries(kinds.map(kind => [kind, current.days.filter(day => day.kind === kind&&!day.is_holiday).length]));
  el('metrics').replaceChildren();
  for (const [label, value] of [[globalThis.CtlText.source("backend_planning.text_8a6685681a4f"), counts.Arbeitstag], [globalThis.CtlText.source("backend_planning.text_be197acfa59b"), counts.Urlaub],
      [globalThis.CtlText.source("backend_planning.text_3c1bdf2670ef"), counts.Ruhetag], [globalThis.CtlText.source("backend_planning.text_98deca758e26"), current.days.filter(d=>d.is_holiday).length], [globalThis.CtlText.source("backend_planning.text_06e66d1ebcb5"), clock(current.days.filter(d=>d.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")).reduce((n,d)=>n+d.target_minutes,0)) + ' h'],
      [globalThis.CtlText.source("backend_planning.text_38d7ebf3d44e"), clock(current.days.reduce((n,d)=>n+d.target_minutes,0)) + ' h']]) {
    const box = document.createElement('div'), strong = document.createElement('strong');
    strong.textContent = value; box.append(strong, document.createTextNode(label)); el('metrics').append(box);
  }
  el('status').textContent = (dirty ? globalThis.CtlText.source("backend_planning.text_56d2fae99993") : '') + (counts.Ungeplant ? counts.Ungeplant + globalThis.CtlText.source("backend_planning.text_14d7de3daf4e") : globalThis.CtlText.source("backend_planning.text_e6cc4ef5ee85"));
}
function changeDay(day, kind, note,shift=null) {
  day.shift=kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?(shift||(day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?day.shift:annual.driver_type==='border'?'border_day':'standard')):'standard';
  day.kind = kind; day.note = kind === globalThis.CtlText.source("backend_planning.text_52e37a639da5") ? '' : note;
  updateDuty(day);syncDraft(); renderCalendar(); clearPreview();
  message(globalThis.CtlText.source("backend_planning.text_4a01fdf44665"));
}
function openPlanDay(day){if(accessLevel<2)return;activeSelection=null;activeDay=day;el('dayTitle').textContent=globalThis.CtlText.source("backend_planning.text_3a5c3352f756")+day.date;el('dayKind').value=day.kind;el('dayNote').value=day.note;el('dayNote').disabled=day.kind===globalThis.CtlText.source("backend_planning.text_52e37a639da5");el('dayDialog').showModal();}
function openSelectedDays(){if(busy||accessLevel<2||!selectedSet().size){message(globalThis.CtlText.source("backend_planning.text_fc6b2cb552de"),true);return;}activeSelection=new Set(selectedSet());activeDay=scopeDays().find(day=>activeSelection.has(day.date));el('dayTitle').textContent=(window.I18n?.t(globalThis.CtlText.source("backend_planning.text_4cefe864bb0a"))||globalThis.CtlText.source("backend_planning.text_4cefe864bb0a"))+' · '+activeSelection.size;el('dayKind').value=el('bulkKind').value;el('dayNote').value=el('bulkNote').value;el('dayNote').disabled=el('dayKind').value===globalThis.CtlText.source("backend_planning.text_52e37a639da5");el('dayDialog').showModal();}
function applySelectedDays(dates,kind,note){if(busy||accessLevel<2)return;const days=view==='excel'?(importData?.days||[]):(annual?.months.flatMap(m=>m.days)||[]);for(const day of days){if(!dates.has(day.date))continue;day.shift=kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?(day.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")?day.shift:annual.driver_type==='border'?'border_day':'standard'):'standard';day.kind=kind;day.note=kind===globalThis.CtlText.source("backend_planning.text_52e37a639da5")?'':note.trim();updateDuty(day);}if(view==='excel'){renderPreview();selectionStatus();}else{syncDraft();renderCalendar();renderDays();}message(view==='excel'?globalThis.CtlText.source("backend_planning.text_a3d112f39be2"):globalThis.CtlText.source("backend_planning.text_475786bc778e"));}
function reviewPlanChanges(review){return new Promise(resolve=>{const dialog=el('planReviewDialog');el('planReviewRows').replaceChildren();const describe=d=>d.kind+globalThis.CtlText.source("backend_planning.text_7db092ffcf73")+clock(d.target_minutes)+' h'+(d.note?globalThis.CtlText.source("backend_planning.text_262a99d0c5ab")+d.note:'');for(const change of review.changes){const row=document.createElement('tr');for(const value of [change.name,change.date,describe(change.before),describe(change.after)]){const cell=document.createElement('td');cell.textContent=value;cell.dataset.i18nIgnore='';row.append(cell);}el('planReviewRows').append(row);}el('planReviewAgree').checked=false;el('planReviewSave').disabled=true;const finish=value=>{dialog.close();resolve(value);};el('planReviewAgree').onchange=()=>el('planReviewSave').disabled=!el('planReviewAgree').checked;el('planReviewSave').onclick=()=>{if(el('planReviewAgree').checked)finish(true);};el('planReviewCancel').onclick=()=>finish(false);dialog.oncancel=event=>{event.preventDefault();finish(false);};dialog.showModal();});}
async function saveConfirmed(days,revisions){const body={groups:[{tf_id:Number(saved.tf),year:saved.year,days,expected_revisions:revisions}]};const review=await api('/api/v1/admin/planning/collective/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!review.changes.length){message(globalThis.CtlText.source("backend_planning.text_8f1b85381d9a"));return false;}if(!await reviewPlanChanges(review))return false;await api('/api/v1/admin/planning/collective/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...body,confirmation:review.confirmation,confirmed:true})});return true;}
function renderCalendar() {
  const grid = el('calendar'); grid.replaceChildren();
  for (const name of [globalThis.CtlText.source("backend_planning.text_d23e867e38e8"),globalThis.CtlText.source("backend_planning.text_16ab72874809"),globalThis.CtlText.source("backend_planning.text_d8f33a13ae6e"),globalThis.CtlText.source("backend_planning.text_30094e0bec00"),globalThis.CtlText.source("backend_planning.text_eed8f901692d"),globalThis.CtlText.source("backend_planning.text_a951efc79deb"),globalThis.CtlText.source("backend_planning.text_fb1df1a24e3f")]) {
    const cell = document.createElement('div'); cell.className = 'weekday'; cell.textContent = name; grid.append(cell);
  }
  const offset = (new Date(saved.year, saved.month - 1, 1).getDay() + 6) % 7;
  for (let i = 0; i < offset; i++) grid.append(document.createElement('div'));
  for (const day of current.days) {
    const button = document.createElement('button'); button.className = 'day'; button.type = 'button'; button.dataset.kind = day.is_holiday?globalThis.CtlText.source("backend_planning.text_ecda07db6e0b"):day.kind;planColor(button,day);
    const number = document.createElement('b'); number.textContent = Number(day.date.slice(-2));
    const label = document.createElement('span'); label.textContent = planLabel(day);
    const hours = document.createElement('span'); hours.textContent = day.kind===globalThis.CtlText.source("backend_planning.text_52e37a639da5")&&!day.is_holiday?globalThis.CtlText.source("backend_planning.text_64509e1af49c"):clock(day.target_minutes)+' h';
    const note = document.createElement('small'); note.dataset.i18nIgnore='true'; note.textContent = day.note;
    const duty=document.createElement('small');duty.textContent=dutyLabel(day);button.append(number, label, hours,duty, note); button.setAttribute('aria-label', day.date + ', ' + (day.is_holiday?planLabel(day)+globalThis.CtlText.source("backend_planning.text_cb7be30b9bd9"):day.kind) + globalThis.CtlText.source("backend_planning.text_a9eda283c0af"));
    button.disabled = accessLevel < 2;
    button.classList.toggle('selected-day',selection.has(day.date));button.setAttribute('aria-pressed',String(selection.has(day.date)));
    button.onclick = () => {
      if(el('selectionMode').checked){toggleDate(day.date);return;}
      openPlanDay(day);
    };
    grid.append(button);
  }
}
function renderDays() {
  const body = el('days'); body.replaceChildren();
  for (const day of current.days) {
    const row = document.createElement('tr'); row.dataset.kind = day.is_holiday?globalThis.CtlText.source("backend_planning.text_ecda07db6e0b"):day.kind;planColor(row,day);
    const check = document.createElement('input'); check.type = 'checkbox'; check.setAttribute('aria-label', day.date + globalThis.CtlText.source("backend_planning.text_77b8aa5c0d7e"));
    check.checked=selection.has(day.date);check.onchange=()=>toggleDate(day.date);
    let cell = document.createElement('td'); cell.append(check); row.append(cell);
    for (const value of [day.date, new Date(day.date + 'T12:00:00').toLocaleDateString('de-DE', {weekday: 'long'})]) {
      cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    const select = document.createElement('select'); select.setAttribute('aria-label', globalThis.CtlText.source("backend_planning.text_13311e5257fd") + day.date);
    for (const kind of kinds) { const option = document.createElement('option'); option.value=kind;option.textContent = kind; select.append(option); }
    select.disabled = accessLevel < 2; check.disabled = accessLevel < 2;
    select.value = day.kind; cell = document.createElement('td'); cell.append(select);if(day.is_holiday){const badge=document.createElement('span');badge.textContent=planLabel(day);badge.className='holiday-label';cell.append(badge);}row.append(cell);
    const hours=document.createElement('td');hours.textContent=clock(day.target_minutes);row.append(hours);const worked=document.createElement('td');worked.textContent=clock(day.performed_minutes||0);row.append(worked);
    const note = document.createElement('input'); note.type = 'text';note.setAttribute('list','planningNoteChoices'); note.maxLength = 500; note.value = day.note;
    note.disabled = accessLevel < 2 || day.kind === globalThis.CtlText.source("backend_planning.text_52e37a639da5"); note.setAttribute('aria-label', globalThis.CtlText.source("backend_planning.text_df7efab02cb2") + day.date);
    cell = document.createElement('td'); cell.append(note); row.append(cell);
    select.onchange = () => {
      changeDay(day, select.value, note.value); row.dataset.kind = day.is_holiday?globalThis.CtlText.source("backend_planning.text_ecda07db6e0b"):day.kind;planColor(row,day);if(day.is_holiday)row.querySelector('.holiday-label').textContent=planLabel(day); note.value = day.note;
      note.disabled = day.kind === globalThis.CtlText.source("backend_planning.text_52e37a639da5");hours.textContent=clock(day.target_minutes);
    };
    note.oninput = () => changeDay(day, day.kind, note.value);
    body.append(row);
  }
  selectionStatus();
}
function renderYear() {
  el('yearRows').replaceChildren();
  const table = document.createElement('table'); table.className = 'yearmatrix';
  const head = document.createElement('tr');
  for (const value of [globalThis.CtlText.source("backend_planning.text_2933070469a2"), ...Array.from({length: 31}, (_, i) => i+1), globalThis.CtlText.source("backend_planning.text_6e96b1407290")]) {
    const th = document.createElement('th'); th.textContent = value; head.append(th);
  }
  table.append(head);
  for (const month of annual.months) {
    for(const [field,kind] of [['work_days',globalThis.CtlText.source("backend_planning.text_eb8f579b6931")],['vacation_days',globalThis.CtlText.source("backend_planning.text_35d3a889824d")],['rest_days',globalThis.CtlText.source("backend_planning.text_e79aa42d7d18")],['unplanned_days',globalThis.CtlText.source("backend_planning.text_52e37a639da5")]])month[field]=month.days.filter(d=>d.kind===kind&&!d.is_holiday).length;month.holiday_days=month.days.filter(d=>d.is_holiday).length;month.work_target_minutes=month.days.filter(d=>d.kind===globalThis.CtlText.source("backend_planning.text_eb8f579b6931")).reduce((n,d)=>n+d.target_minutes,0);month.target_minutes=month.days.reduce((n,d)=>n+d.target_minutes,0);
    const row = document.createElement('tr');
    for (const value of [names[month.month - 1], month.work_days, month.vacation_days, month.rest_days,
        month.unplanned_days, clock(month.work_target_minutes) + ' h', clock(month.target_minutes) + ' h']) {
      const td = document.createElement('td'); td.textContent = value; row.append(td);
    }
    el('yearRows').append(row);
    const matrixRow = document.createElement('tr'), label = document.createElement('td');
    label.textContent = names[month.month - 1]; matrixRow.append(label);
    for (const day of window.PlanColors.yearSlots(month)) {
      const td = document.createElement('td');
      if (day) {
        const button = document.createElement('button'); for(const value of [day.is_holiday?'F'+(day.kind!==globalThis.CtlText.source("backend_planning.text_52e37a639da5")?'/'+dayCode(day):''):dayCode(day),window.PlanColors.weekdayInitial(day.date)]){const line=document.createElement('span');line.textContent=value;line.setAttribute('data-i18n-ignore','');button.append(line);} const note=document.createElement('span');note.className='year-note';note.textContent=day.note||'\u00a0';note.setAttribute('data-i18n-ignore','');button.append(note);button.dataset.kind = day.is_holiday?globalThis.CtlText.source("backend_planning.text_ecda07db6e0b"):day.kind;planColor(button,day);
        button.title = day.date + ' · ' + (day.is_holiday?planLabel(day)+' · 0:00 h':day.kind); button.title+=(day.note?' · '+day.note:'');button.setAttribute('aria-label', button.title);
        button.classList.toggle('selected-day',selection.has(day.date));button.setAttribute('aria-pressed',String(selection.has(day.date)));
        button.onclick = handle(() => exclusive(async () => { if(accessLevel>=2&&el('selectionMode').checked){toggleDate(day.date);return;}openPlanDay(day); }));
        td.append(button);
      }
      matrixRow.append(td);
    }
    const total = document.createElement('td'); total.textContent = clock(month.target_minutes); matrixRow.append(total); table.append(matrixRow);
  }
  el('yearMatrix').replaceChildren(table);
  for(const field of ['holiday_days','work_days','vacation_days','rest_days','unplanned_days','target_minutes'])annual.totals[field]=annual.months.reduce((n,m)=>n+m[field],0);
  el('annualSummary').textContent = (dirty?globalThis.CtlText.source("backend_planning.text_7e2d9a217a5c"):globalThis.CtlText.source("backend_planning.text_562bc6895f84")) + annual.totals.work_days + globalThis.CtlText.source("backend_planning.text_b579d32bb2a2") + annual.totals.vacation_days +
    globalThis.CtlText.source("backend_planning.text_5438ba9da9b3") + clock(annual.totals.target_minutes) + globalThis.CtlText.source("backend_planning.text_50437271c974") + annual.totals.unplanned_days + globalThis.CtlText.source("backend_planning.text_8f6df1c98fea")+annual.totals.holiday_days+' Feiertage Berlin mit 0 h Soll. A = Arbeit, U = Urlaub, R = Ruhe, F = Feiertag, ? = ungeplant.';
}
async function load(force = false) {
  const sameYear=saved&&saved.tf===el('tf').value&&saved.year===Number(el('year').value);
  if (dirty && !force && !sameYear && !confirm(globalThis.CtlText.source("backend_planning.text_2630c0233c43"))) {
    el('tf').value = saved.tf; el('year').value = saved.year; el('month').value = saved.month; return false;
  }
  const year = Number(el('year').value), month = Number(el('month').value), tf = el('tf').value;
  if (!tf) throw Error(globalThis.CtlText.source("backend_planning.text_71a05275e3ba"));
  if (year < 2000 || year > 2100 || !Number.isInteger(year)) throw Error(globalThis.CtlText.source("backend_planning.text_ba5dcf4f3961"));
  if(sameYear&&!force){saved.month=month;current=annual.months[month-1];el('title').textContent=names[month-1]+' '+year;updateMetrics();renderDays();renderCalendar();renderYear();switchView(view);return true;}
  const ticket = ++loadTicket, base = '/api/v1/admin/tf/' + tf + '/plan/' + year;
  const [data, yearData, history] = await Promise.all([api(base + '/' + month), api(base), api(base + '/history')]);
  if (ticket !== loadTicket) return false;
  saved = {tf, year, month}; annual = yearData;current=annual.months[month-1];dirty = false;selection.clear();originals=new Map(annual.months.flatMap(m=>m.days).map(d=>[d.date,JSON.stringify([d.kind,d.note,d.shift||'standard'])]));clearPreview();
  el('title').textContent = names[month - 1] + ' ' + year;
  updateMetrics(); renderDays(); renderCalendar(); renderYear(); switchView(view);
  el('yearPdf').href = base + '/pdf'; el('template').href = base + '/template.xlsx';
  el('history').replaceChildren();
  for (const item of history) {
    const line = document.createElement('p'); line.textContent = item.date + ': ' + item.previous_kind+' · '+shiftLabels[item.previous_shift||'standard'] + ' → ' + item.new_kind+' · '+shiftLabels[item.new_shift||'standard'] +
      ' · ' + (item.source === 'excel' ? globalThis.CtlText.source("backend_planning.text_a318baaaf60e") : item.source === 'shift'?globalThis.CtlText.source("backend_planning.text_dedbf4528cee"):globalThis.CtlText.source("backend_planning.text_961cacaa6e41")) + globalThis.CtlText.source("backend_planning.text_d3dd571c7e70") + item.admin_id + ' · ' + item.changed_at + globalThis.CtlText.source("backend_planning.text_de92d152d782"); el('history').append(line);
  }
  if (!history.length) el('history').textContent = globalThis.CtlText.source("backend_planning.text_eba4e06e1165");
  message(globalThis.CtlText.source("backend_planning.text_26b9c7ab4e8c")); return true;
}
const handle = fn => async () => { try { await fn(); } catch (error) { message(error.message, true); } };
async function exclusive(fn) {
  if (busy) return;
  busy = true; for (const id of ['editor','annual','importer']) el(id).inert = true;
  document.querySelectorAll('[data-view]').forEach(button => button.disabled = true);
  const ids = ['tf','year','month','load','save','inspect','confirm','bulk','selectionEdit']; ids.forEach(id => el(id).disabled = true);
  try { await fn(); } finally { busy = false; ids.forEach(id => el(id).disabled = false);
    for (const id of ['editor','annual','importer']) el(id).inert = false;
    document.querySelectorAll('[data-view]').forEach(button => button.disabled = false);selectionStatus(); }
}
el('load').onclick = handle(() => exclusive(async()=>{if(dirty&&!confirm(globalThis.CtlText.source("backend_planning.text_2630c0233c43")))return;await load(true);}));
for (const id of ['tf','year','month']) el(id).onchange = handle(() => exclusive(() => load()));
document.querySelectorAll('[data-view]').forEach(button => button.onclick = () => switchView(button.dataset.view));
el('dayKind').onchange=()=>{el('dayNote').disabled=el('dayKind').value===globalThis.CtlText.source("backend_planning.text_52e37a639da5");if(el('dayNote').disabled)el('dayNote').value='';};
el('closeDay').onclick = () => {activeSelection=null;el('dayDialog').close();};
el('selectionEdit').onclick=openSelectedDays;
el('dayForm').onsubmit = event => { event.preventDefault(); if(activeSelection){applySelectedDays(activeSelection,el('dayKind').value,el('dayNote').value);activeSelection=null;}else{changeDay(activeDay, el('dayKind').value, el('dayNote').value);renderDays();} el('dayDialog').close(); };
el('selectAll').onchange=()=>{for(const d of scopeDays())el('selectAll').checked?selectedSet().add(d.date):selectedSet().delete(d.date);renderCalendar();renderDays();renderYear();renderPreview();selectionStatus();};
el('clearSelection').onclick=()=>{selectedSet().clear();renderCalendar();renderDays();renderYear();renderPreview();selectionStatus();};
el('bulk').onclick=()=>{if(!selectedSet().size){message(globalThis.CtlText.source("backend_planning.text_fc6b2cb552de"),true);return;}applySelectedDays(new Set(selectedSet()),el('bulkKind').value,el('bulkNote').value);};
el('save').onclick=handle(()=>exclusive(async()=>{const days=changedDays();if(!days.length){message(globalThis.CtlText.source("backend_planning.text_8f1b85381d9a"));return;}const months=new Set(days.map(d=>Number(d.date.slice(5,7))));if(!await saveConfirmed(days.map(({date,kind,note,shift})=>({date,kind,note,shift})),Object.fromEntries([...months].map(m=>[m,annual.months[m-1].revision]))))return;await load(true);message(globalThis.CtlText.source("backend_planning.text_9f1efe953941"));}));
el('inspect').onclick = handle(() => exclusive(async () => {
  if (dirty) throw Error(globalThis.CtlText.source("backend_planning.text_5d77062fe4f0"));
  const file = el('excel').files[0]; if (!file) throw Error(globalThis.CtlText.source("backend_planning.text_0ecce02e2ecc"));
  clearPreview(); const form = new FormData(); form.append('file', file);
  importData = await api(prefix() + '/import/preview', {method: 'POST', body: form}); el('importDays').replaceChildren();
  renderPreview();selectionStatus();
  el('importCount').textContent = importData.days.length + globalThis.CtlText.source("backend_planning.text_8cbf1904636b");
  el('preview').hidden = false; message(globalThis.CtlText.source("backend_planning.text_332a7846c58a"));
}));
el('confirm').onclick = handle(() => exclusive(async () => {
  if (!importData) throw Error(globalThis.CtlText.source("backend_planning.text_a8a0a2904a6a")); if (dirty) throw Error(globalThis.CtlText.source("backend_planning.text_631ee4af7c1f"));
  if(!await saveConfirmed(importData.days.map(({date,kind,note,shift})=>({date,kind,note,shift})),importData.expected_revisions))return;
  await load(true);message(globalThis.CtlText.source("backend_planning.text_9f1efe953941"));
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
    accessLevel = new URLSearchParams(location.search).get('readonly')==='1'?Math.min(1,account.permissions.planning):account.permissions.planning;
    if (!accessLevel) throw Error(globalThis.CtlText.source("backend_planning.text_1aac7697634a"));
    if (accessLevel < 2) {
      for (const id of ['save','bulk','inspect','confirm','excel','selectAll','selectionTools']) el(id).hidden = true;
      document.querySelector('[data-view=excel]').hidden = true;
    }
    if(new URLSearchParams(location.search).get('readonly')==='1'){document.querySelector('h1').textContent=globalThis.CtlText.source("backend_planning.text_e5ad45a9b86b");document.querySelector('nav.tabs').hidden=true;el('editor').querySelector('p.muted').hidden=true;}
    const users = await api('/api/v1/admin/tf');
    for (const user of users) { const option = document.createElement('option'); option.value = user.id;
      option.textContent = user.first_name + ' ' + user.last_name + ' · ' + user.personnel_number; el('tf').append(option); }
    const selected = new URLSearchParams(location.search).get('tf'); if (users.some(u => String(u.id) === selected)) el('tf').value = selected;
    if (users.length) await exclusive(() => load()); else message(globalThis.CtlText.source("backend_planning.text_71a05275e3ba"));
  } catch (error) { message(error.message, true); }
})();

