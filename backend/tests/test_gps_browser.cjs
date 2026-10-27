// Simulated browser contract test; no real GPS hardware or installed browser required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.value='';this.events={};}
 addEventListener(k,f){this.events[k]=f;}
 showModal(){this.open=true;}
 close(){this.open=false;}
 remove(){this.removed=true;}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(key,value){this.attributes[key]=value;}
 click(){}
}
const tracks=new Map();
const database={transaction(){const tx={};tx.objectStore=()=>({get(key){const request={result:tracks.get(key)};queueMicrotask(()=>tx.oncomplete());return request;},put(row){tracks.set(row.key,structuredClone(row));queueMicrotask(()=>tx.oncomplete());return {};},delete(key){tracks.delete(key);queueMicrotask(()=>tx.oncomplete());return {};}});return tx;}};
let count=0,remote=null,body=null;
const response=(data,status=200)=>({status,ok:status<400,json:async()=>structuredClone(data)});
const context={console,Intl,Date,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{body:new Element('body'),visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:true,addEventListener(){}},fetch:async(path,options={})=>{if(path.startsWith('/api/v1/tf/gps/nearby?'))return response({stations:[{code:'BBB',name:'Berlin Beispiel',distance_m:100}],radius_m:5000});if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;remote.reasons=body.reasons;return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[{key:'start',kind:'Start',start:body.points[0].t,end:body.points[0].t,lat:52,lon:13,direction:null}],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/train-journeys.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);
(async()=>{
 const field=new Element('input'),container=new Element('div');field.value='';
 const r=context.window.GpsRecorder.mount({userId:5,journeyId:'00000000-0000-4000-8000-000000000001',container,numberField:field,trainNumber:()=>field.value,readonly:()=>false,selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){},resolve:async()=>({code:'BBB'})});
 await r.readyPromise;assert.equal(r.box.hidden,true);field.value='123';r.freeze();assert.equal(r.box.hidden,false);assert.equal(r.startButton.disabled,false);
 context.window.isSecureContext=false;await assert.rejects(r.start(),/HTTPS/);context.window.isSecureContext=true;
 await r.start();await new Promise(resolve=>setTimeout(resolve,5));assert(context.window.GpsRecorder.isActive());assert.equal(field.readOnly,true);assert.equal(r.record.points.length,1);
 await r.sample();assert.equal(r.record.points.length,2);r.drawMap();assert(r.mapSvg.children.some(e=>e.tag==='image'));assert(r.mapSvg.children.some(e=>e.tag==='polyline'));await r.stop();assert.equal(context.window.GpsRecorder.isActive(),false);assert.equal(field.readOnly,false);assert.equal(body.ended,true);assert.equal(body.points.length,3);assert(!('actual_pause' in body));assert(tracks.get(r.key));assert.equal(r.stationInputs.length,1);
 const choice=r.stationInputs[0];assert.equal(choice.reason.children.length,context.window.TrainJourneyReasons.length+1);choice.reason.value='sonstiges';choice.reason.onchange();assert.equal(choice.detail.hidden,false);await assert.rejects(r.choose(),/Sonstigen Grund/);choice.detail.value='Signalstörung';choice.detail.oninput();await r.persist();r.draw();assert.equal(r.stationInputs[0].reason.value,'sonstiges');assert.equal(r.stationInputs[0].detail.value,'Signalstörung');await r.sync();assert.equal(r.stationInputs[0].detail.value,'Signalstörung');await r.choose();assert.deepEqual(body.stations,{});assert.equal(body.reasons.start.reason,'sonstiges');assert.equal(body.reasons.start.detail,'Signalstörung');assert.equal(Object.keys(r.record.reason_drafts).length,0);await r.erase();assert.equal(r.record,null);assert.equal(tracks.has(r.key),false);
 const historical=context.window.GpsRecorder.mount({userId:5,journeyId:'history',container:new Element('div'),trainNumber:()=> '123',dutyDay:()=> '2000-01-01',readonly:()=>false,selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){}});
 await historical.readyPromise;assert.equal(historical.box.hidden,true);await historical.start();assert.equal(context.window.GpsRecorder.isActive(),false);
 remote={points:[{t:Date.parse('2000-01-01T12:00:00Z'),lat:52,lon:13,accuracy:5}],ended:true,revision:1};await historical.read();assert.equal(historical.box.hidden,false);assert.equal(historical.startButton.hidden,true);assert.equal(historical.syncButton.hidden,true);assert.equal(historical.deleteButton.hidden,true);assert.equal(historical.loadButton.hidden,false);await historical.reload();historical.o.dutyDay=()=> '2000-01-02';historical.freeze();assert.equal(historical.box.hidden,true);
 delete r.o.selectStart;const startChoice=r.chooseStart();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(r.startDialog.list.children.length,2);r.startDialog.manual.value='BBB';await r.startDialog.accept.onclick();assert.equal((await startChoice).code,'BBB');r.help();const help=context.document.body.children.at(-1);assert.equal(help.open,true);help.children[0].children[1].onclick();assert.equal(help.open,false);
 console.log('GPS browser simulation passed: secure context, button gating, fixes, local persistence, stop/sync, station selection and delete.');
})().catch(error=>{console.error(error);process.exitCode=1;});
