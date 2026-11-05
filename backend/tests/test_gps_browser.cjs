// Simulated browser contract test; no real GPS hardware or installed browser required.
const fs=require('fs'),vm=require('./localized-vm.cjs'),assert=require('assert');
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
const context={console,Intl,Date,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{body:new Element('body'),visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:true,addEventListener(){}},fetch:async(path,options={})=>{if(path.startsWith('/api/v1/tf/gps/nearby?'))return response({stations:[{code:'BBB',name:'Berlin Beispiel',distance_m:100}],radius_m:5000});if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;remote.reasons=body.reasons;remote.selection=body.selection;remote.stations=Object.fromEntries(Object.entries(body.stations).map(([k,code])=>[k,{code,name:'Berlin Beispiel'}]));for(const row of remote.analysis.rows){row.station=remote.stations[row.key];row.reason=remote.reasons[row.key];}return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[{key:'start',kind:'Start',start:body.points[0].t,end:body.points[0].t,lat:52,lon:13,direction:null}],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/train-journeys.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);
(async()=>{
 const field=new Element('input'),container=new Element('div');field.value='';
 const r=context.window.GpsRecorder.mount({userId:5,journeyId:'00000000-0000-4000-8000-000000000001',container,numberField:field,trainNumber:()=>field.value,readonly:()=>false,selectEnd:async()=>({code:'CCC',name:'Ziel'}),selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){},resolve:async()=>({code:'BBB'})});
 await r.readyPromise;assert.equal(r.content.hidden,true);assert.equal(r.collapseButton.textContent,'+');assert.equal(r.collapseButton.attributes['aria-expanded'],'false');r.collapseButton.onclick();assert.equal(r.content.hidden,false);assert.equal(r.collapseButton.textContent,'−');assert.equal(r.collapseButton.attributes['aria-expanded'],'true');assert.equal(r.box.hidden,true);field.value='123';r.freeze();assert.equal(r.box.hidden,false);assert.equal(r.startButton.disabled,false);
 context.window.isSecureContext=false;await assert.rejects(r.start(),/HTTPS/);context.window.isSecureContext=true;
 await r.start();await new Promise(resolve=>setTimeout(resolve,5));assert(context.window.GpsRecorder.isActive());assert.equal(field.readOnly,true);assert.equal(r.record.points.length,1);
 r.collapseButton.onclick();assert.equal(r.content.hidden,true);await r.sample();assert.equal(r.record.points.length,2);assert(context.window.GpsRecorder.isActive());r.drawMap();assert(!r.mapSvg.children.some(e=>e.tag==='image'));r.collapseButton.onclick();r.drawMap();assert(r.mapSvg.children.some(e=>e.tag==='image'));assert(r.mapSvg.children.some(e=>e.tag==='polyline'));await r.stop();assert.equal(context.window.GpsRecorder.isActive(),false);assert.equal(field.readOnly,false);assert.equal(body.ended,true);assert.equal(body.points.length,3);assert(!('actual_pause' in body));assert(tracks.get(r.key));assert.equal(r.liveInputs.length,0);assert.equal(r.record.end_station,'CCC');
 await r.erase();assert.equal(r.record,null);assert.equal(tracks.has(r.key),false);
 const chosen={start:{code:'BBB',name:'Start'},end:{code:'CCC',name:'Ziel'}},times=[];let startQuestions=0,endQuestions=0;
 r.o.selectedEndpoint=async kind=>chosen[kind];r.o.endpoint=(kind,choice)=>{chosen[kind]=choice;};r.o.journeyTime=(kind,time)=>times.push({kind,time});
 r.o.selectStart=async()=>{startQuestions++;return {code:'BBB',name:'Start'};};r.o.selectEnd=async()=>{endQuestions++;return {code:'CCC',name:'Ziel'};};
 await r.start();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(r.record.start_station,'BBB');assert.equal(r.record.end_station,'CCC');assert.equal(startQuestions+endQuestions,0);
 const first=r.record.points.at(-1).t,add=(delta,speed,accuracy=5)=>r.add({timestamp:first+delta,coords:{latitude:52,longitude:13,accuracy,speed:speed/3.6}});
 await add(5000,20,51);await add(10000,9.99);assert.equal(times.length,0);
 await add(15000,10);await add(20000,12);assert.deepEqual(times,[{kind:'start',time:first+15000}]);
 const beforeStop=Date.now();await r.stop(false);assert.equal(times[1].kind,'end');assert(times[1].time>=beforeStop);assert.equal(body.arrival_at,times[1].time);assert.equal(body.departure_applied,true);assert.equal(startQuestions+endQuestions,0);
 await r.erase();delete chosen.end;await r.start();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(startQuestions,0);assert.equal(endQuestions,1);assert.equal(r.record.end_station,'CCC');
 delete chosen.end;r.o.selectEnd=async()=>{endQuestions++;return {code:'DDD',name:'Neues Ziel'};};await r.stop(false);assert.equal(endQuestions,2);assert.equal(body.end_station,'DDD');await r.erase();
 delete chosen.start;r.o.selectStart=async()=>{startQuestions++;return null;};await r.start();assert.equal(startQuestions,1);assert.equal(endQuestions,2);assert.equal(r.record,null);assert(!context.window.GpsRecorder.isActive());
 const historical=context.window.GpsRecorder.mount({userId:5,journeyId:'history',container:new Element('div'),trainNumber:()=> '123',dutyDay:()=> '2000-01-01',readonly:()=>false,selectEnd:async()=>({code:'CCC',name:'Ziel'}),selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){}});
 await historical.readyPromise;assert.equal(historical.box.hidden,true);await historical.start();assert.equal(context.window.GpsRecorder.isActive(),false);
 remote={points:[{t:Date.parse('2000-01-01T12:00:00Z'),lat:52,lon:13,accuracy:5}],ended:true,revision:1};await historical.read();assert.equal(historical.box.hidden,false);assert.equal(historical.startButton.hidden,true);assert.equal(historical.syncButton.hidden,true);assert.equal(historical.deleteButton.hidden,true);assert.equal(historical.loadButton.hidden,false);await historical.reload();historical.o.dutyDay=()=> '2000-01-02';historical.freeze();assert.equal(historical.box.hidden,true);
 delete r.o.selectStart;const startChoice=r.chooseStart();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(r.startDialog.list.children.length,0);r.startDialog.manual.value='BBB';await r.startDialog.accept.onclick();assert.equal((await startChoice).code,'BBB'); let topic;context.window.loadTfHelp=async()=>({open:id=>topic=id});await r.help();assert.equal(topic,'gps');
 console.log('GPS browser simulation passed: secure context, button gating, fixes, local persistence, stop/sync, station selection and delete.');
})().catch(error=>{console.error(error);process.exitCode=1;});
