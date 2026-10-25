const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),window={};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/plan-colors.js','utf8'),{window,Date});
const p=window.PlanColors;
for(const [date,kind,expected]of [['2026-10-05','Arbeitstag','#f5f5f5'],['2026-10-03','Arbeitstag','#eedc82'],['2026-10-04','Ruhetag','#66cdaa'],['2026-10-05','Ruhetag','#66cdaa'],['2026-10-04','Urlaub','#ff7256']]){const node={style:{},dataset:{}};p.apply(node,{date,kind});assert.equal(node.style.backgroundColor,expected);assert.equal(node.style.backgroundImage,'none');}
const node={style:{},dataset:{}};p.apply(node,{date:'2026-10-03',kind:'Urlaub',is_holiday:true});assert(node.style.backgroundImage.includes('#ffe4e1'));assert(node.style.backgroundImage.includes('#ff7256'));p.apply(node,{date:'2026-10-03',kind:'Arbeitstag',is_holiday:true});assert(node.style.backgroundImage.includes('#eedc82'));p.apply(node,{date:'2026-10-03',kind:'Ungeplant',is_holiday:true});assert.equal(node.style.backgroundColor,'#ffe4e1');assert.equal(node.style.backgroundImage,'none');
p.apply(node,{date:'2026-10-03',kind:'Ruhetag',is_holiday:true});assert(node.style.backgroundImage.includes('#66cdaa'));assert(node.style.backgroundImage.includes('#ffe4e1'));
for(const file of ['planning.html','tf-hours.html','tf-portal.html'])assert(fs.readFileSync('backend/lokzeitleiste/static/'+file,'utf8').includes('/plan-colors.js?v=20261025-2'));
console.log('Shared plan palette, weekend/leave precedence, diagonal holidays and consumer loading passed.');
