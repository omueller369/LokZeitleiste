const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const {join}=require('node:path');
const vm=require('node:vm');
const context={window:{}};
vm.runInNewContext(readFileSync(join(__dirname,'../lokzeitleiste/static/train-journeys.js'),'utf8'),context);
const stamp=context.window.ReportTableTime;
test('day duties show clocks, including guest trips outside duty',()=>{
  const start='2026-10-12T09:00',end='2026-10-12T17:00';
  assert.equal(stamp(start,start,end),'09:00');
  assert.equal(stamp(end,start,end,start),'17:00');
  assert.equal(stamp('2026-10-12T07:00',start,end),'07:00');
  assert.equal(stamp('',start,end),'');
});
test('overnight duties label date changes and resume clocks afterwards',()=>{
  const start='2026-10-12T21:00',end='2026-10-13T09:00';
  assert.equal(stamp(start,start,end),'21:00');
  assert.equal(stamp('2026-10-13T00:05',start,end,'2026-10-12T23:55'),'13.10.2026 · 00:05');
  assert.equal(stamp('2026-10-13T00:10',start,end,'2026-10-13T00:05'),'00:10');
  assert.equal(stamp('2026-10-13T00:15',start,end,'2026-10-13T00:10'),'00:15');
});
test('event editor uses current types and renders date changes across rows',()=>{
  class Element{
    constructor(tag){this.tagName=tag;this.children=[];this.value='';this.dataset={};this.attributes={};this.classList={add(){},toggle(){}};}
    append(...nodes){for(const node of nodes){node.parentElement=this;this.children.push(node);}}
    setAttribute(name,value){this.attributes[name]=value;}
    addEventListener(){}
    replaceChildren(){this.children=[];}
    reset(){}
    before(){}
    focus(){}
    get options(){return this.children;}
  }
  context.document={createElement:tag=>new Element(tag)};
  context.window.addEventListener=()=>{};
  const bounds={start:'2026-10-12T21:00',end:'2026-10-13T09:00'};let id=0;
  const editor=new context.window.TrainJourneyEditor({container:new Element('div'),button:new Element('button'),readonly:()=>false,bounds:()=>bounds,minute:v=>Date.parse(v+'Z')/60000,uuid:()=>String(++id),clock:n=>String(n),stations(){},changed(){}});
  editor.restore([{id:'train',train_number:'123',start_station:'BHF',end_station:'LL',start_at:bounds.start,end_at:bounds.end,events:[{id:'1',reason:'Pause',cause:'CTL Logistics DE',station:'',start_at:'2026-10-12T23:55',end_at:'2026-10-13T00:10'},{id:'2',reason:'V1',cause:'DB InfraGo',station:'LL',start_at:'2026-10-13T00:15',end_at:'2026-10-13T00:30'}]}]);
  const item=editor.items[0],fields=item.eventFields;
  assert.deepEqual(Array.from(fields.cause.options,o=>o.value),['','CTL','DB InfraGo','Dritte Stelle','sonstiges']);
  assert.equal(fields.cause.parentElement.children[0].textContent,'Art');
  const rows=item.rows.children.map(row=>row.children.map(cell=>cell.textContent));
  assert.equal(rows[0][0],'CTL');assert.equal(rows[0][1],'Pause');
  assert.equal(rows[0][4],'13.10.2026 · 00:10');
  assert.equal(rows[1][3],'00:15');assert.equal(rows[1][4],'00:30');
  item.ctlPause.onclick();assert.equal(fields.cause.value,'CTL');assert.equal(fields.reason.value,'Pause');assert.equal(fields.station.required,false);
});
