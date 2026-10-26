const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class E{constructor(){this.value='';this.style={};this.maxLength=120;}addEventListener(){}focus(){}select(){}setAttribute(){}scrollIntoView(){}}
const nodes={},el=id=>nodes[id]??=new E(),window={addEventListener(){}};
let source=fs.readFileSync('backend/lokzeitleiste/static/vehicles.js','utf8');source=source.slice(0,source.indexOf('(async()=>{try{const me='))+'window.test={render,setLevel(v){level=v;}};})();';
vm.runInNewContext(source,{document:{getElementById:el},window,confirm:()=>true,console,Set});window.test.setLevel(3);
const original={id:7,revision:3,vehicle_number:'92 81 1234 567-8',retired:true,status:'limited',status_note:'Defekt',name:'Alt',series:'185',length_m:18.95,weight_kg:84500,axle_count:4,brake_shoe:'K',brake_g:101,brake_r:120,brake_p:110,spring_brake:40,spring_unit:'kN',leasing_company_id:9,next_revision:'2027-01-01',mileage:1234,notes:'Alt'};
window.test.render(original,true);el('vehicleCopy').onclick();
for(const id of ['vehicleNumber3','vehicleNumber4','vehicleNumber5','vehicleName','vehicleRevisionDate','vehicleMileage','vehicleNotes','vehicleStatusNote'])assert.equal(el(id).value,'',id);
assert.equal(el('vehicleNumber1').value,'92');assert.equal(el('vehicleNumber2').value,'81');assert.equal(el('vehicleStatus').value,'ready');assert.equal(el('vehicleSeries').value,'185');assert.equal(el('vehicleBrakeG').value,101);assert.equal(el('vehicleLeasing').value,9);assert.equal(el('vehicleRetire').hidden,true);assert.equal(el('vehicleRetiredBadge').hidden,true);assert.equal(el('vehicleFields').disabled,false);assert.equal(original.name,'Alt');assert.equal(el('vehicleLength').value,18.95);assert.equal(el('vehicleWeight').value,'84.5');assert.equal(el('vehicleAxles').value,4);assert.equal(el('vehicleBrakeShoe').value,'K');
assert(!fs.readFileSync('backend/lokzeitleiste/static/vehicles.html','utf8').includes('vehiclePower'));
console.log('Vehicle copy: new editable draft, preserved common fields, cleared requested fields and retirement flag.');
