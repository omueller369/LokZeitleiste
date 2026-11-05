const fs=require('node:fs'),vm=require('./localized-vm.cjs'),assert=require('node:assert/strict');
class E{constructor(){this.value='';this.checked=false;this.dataset={};this.children=[];this.classList={toggle(){}};}querySelectorAll(){return [];}append(...items){this.children.push(...items);}}
const nodes={},el=id=>nodes[id]??=new E(),window={};
const code=fs.readFileSync('backend/lokzeitleiste/static/work-report.js','utf8').split('// Keep collapse buttons')[0].replace(/\}\)\(\);\s*$/,`window.dutyTest={changeDutyKind,prefillDutyHours,keepDefaultDutyDate,realTotals:totals,mergeLocal,validateKind,setup(options={}){state={kind:'Sonstige Erfassung',legacy_pause:0,...options};trips=[];pending=[];key='test';plans={};trainEditor={items:[],draft:()=>[],dutyChanged(){window.boundsChanged=(window.boundsChanged||0)+1;}};totals=freeze=loadPlan=refreshGuestDefaults=storeDraft=kindControls=()=>{};},state:()=>state,addTrain(){trainEditor.items.push({});},setPending(rows){pending=rows;}};})();`);
vm.runInNewContext(code,{window,document:{getElementById:el},localStorage:{getItem:()=>null,setItem(){}},Date,Intl,console});
const api=window.dutyTest;
for(const kind of ['Sonstige Erfassung','Krank','Rufbereitschaft','Bereitschaft','Ausfallschicht']){
 api.setup();el('dutyStart').value='2026-10-24T21:00';el('dutyEnd').value='2026-10-25T05:00';api.changeDutyKind(kind);
 assert.equal(api.state().kind,kind);assert.equal(el('dutyStart').value,'2026-10-24T08:00');assert.equal(el('dutyEnd').value,'2026-10-24T16:00');
 assert.equal(api.keepDefaultDutyDate('2026-10-24T08:00','2026-10-25T08:00'),true);assert.equal(el('dutyEnd').value,'2026-10-25T16:00');el('dutyStart').value='2026-10-25T08:00';api.realTotals();assert.equal(el('requiredPause').textContent,kind==='Sonstige Erfassung'?'0:30':'0:00');assert.equal(el('netDuration').textContent,'8:00');
}
api.setup();el('dutyStart').value='2026-10-24T21:00';el('dutyEnd').value='2026-10-25T05:00';api.changeDutyKind('Urlaub');assert.equal(el('dutyEnd').value,'2026-10-25T05:00');
api.setup({saved_id:17});api.changeDutyKind('Bereitschaft');assert.equal(api.state().kind,'Sonstige Erfassung');assert.equal(el('dutyStart').value,'2026-10-24T21:00');
api.setup({kind:'Krank'});el('dutyStart').value='2026-10-24T08:00';el('dutyEnd').value='2026-10-24T16:00';assert.doesNotThrow(()=>api.validateKind());
api.setPending([{client_id:'sick',kind:'Krank',start_at:'2026-10-24T08:00',end_at:'2026-10-24T16:00',actual_pause:0,trips:[],train_journeys:[]}]);
const month=api.mergeLocal({reports:[],days:[],work_minutes:0,pause_minutes:0,guest_minutes:0},'2026-10');assert.equal(month.work_minutes,480);assert.equal(month.reports[0].credited_minutes,480);
console.log('Special duties: explicit selection presets 08:00–16:00 on selected date, 8:00 credit, saved reports protected, sick credit without plan and local month totals passed.');
