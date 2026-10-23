const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag='div'){this.tag=tag;this.children=[];this.attributes={};this.dataset={};this.hidden=false;this.value='';this.textContent='';}
 append(...items){this.children.push(...items);}
 replaceChildren(){this.children=[];}
 setAttribute(key,value){this.attributes[key]=value;}
 querySelector(tag){for(const child of this.children){if(child.tag===tag)return child;const found=child.querySelector(tag);if(found)return found;}return null;}
 focus(){focused=this;}
 scrollIntoView(){}
}
let focused=null,delays=new Map(),events={};
const ids=['vehicleRows','vehicleEmpty','vehicleMessage','vehicleSearch','vehicleFilter','vehicleReload','handoverContent','handoverDetails','handoverTitle','handoverStatus','handoverNoteLabel','handoverNoteBox','handoverNote','handoverName','handoverNumber','handoverSeries','handoverClose'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));elements.handoverDetails.hidden=true;
const vehicles=[{id:1,status:'limited',status_label:'Eingeschränkt einsatzbereit',status_note:'Nur Rangieren',vehicle_number:'00 01 0002 003-4',name:'<img src=x onerror=alert(1)>',series:'185'},{id:2,status:'ready',status_label:'Einsatzbereit',status_note:'',vehicle_number:'91 80 6185 001-2',name:'Lok 2',series:'186'}];
const reply=data=>({ok:true,status:200,json:async()=>data});
const context={document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},window:{addEventListener:(event,fn)=>events[event]=fn},location:{},URLSearchParams,setTimeout,clearTimeout,console,fetch:async(path)=>{
 if(path==='/api/v1/account/me')return reply({role:'staff',permissions:{loco_handover:1}});
 const match=/\/vehicles\/(\d+)$/.exec(path);if(match){const id=Number(match[1]);if(delays.has(id))return delays.get(id);return reply({...vehicles.find(v=>v.id===id)});}return reply(vehicles);
}};
const tick=()=>new Promise(r=>setTimeout(r,0));
(async()=>{
 vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/loco-handover.js','utf8'),context);await tick();
 assert.equal(elements.vehicleRows.children.length,2);assert.equal(elements.vehicleRows.children[0].children.length,3);
 await elements.vehicleRows.children[0].onclick();assert.equal(elements.handoverDetails.hidden,false);assert.equal(elements.handoverName.textContent,vehicles[0].name);assert.equal(elements.handoverName.children.length,0);assert.equal(elements.handoverNumber.textContent,'00 01 0002 003-4');assert.equal(elements.handoverNoteBox.hidden,false);assert.equal(elements.handoverNote.dataset.status,'limited');assert.equal(focused,elements.handoverTitle);
 await elements.vehicleRows.children[1].onclick();assert.equal(elements.handoverNoteBox.hidden,true);assert.equal(elements.handoverNote.textContent,'');assert.equal(elements.handoverStatus.dataset.status,'ready');
 let resolveOld;delays.set(1,new Promise(resolve=>resolveOld=resolve));const older=elements.vehicleRows.children[0].onclick();await elements.vehicleRows.children[1].onclick();resolveOld(reply(vehicles[0]));await older;assert.equal(elements.handoverNumber.textContent,vehicles[1].vehicle_number);
 elements.handoverClose.onclick();assert(elements.handoverDetails.hidden);assert.equal(focused,elements.vehicleRows.children[1].querySelector('button'));
 console.log('Handover UI: three columns, row selection, conditional status note, safe text, leading zeros, latest selection wins and focus restoration passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
