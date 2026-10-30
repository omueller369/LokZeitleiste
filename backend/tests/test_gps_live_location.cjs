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
const context={console,Intl,Date,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{body:new Element('body'),visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:true,addEventListener(){}},fetch:async(path,options={})=>{if(path.startsWith('/api/v1/tf/gps/nearby?'))return response({stations:[{code:'BBB',name:'Berlin Beispiel',distance_m:100}],radius_m:5000});if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;remote.reasons=body.reasons;remote.selection=body.selection;remote.stations=Object.fromEntries(Object.entries(body.stations).map(([k,code])=>[k,{code,name:'Berlin Beispiel'}]));for(const row of remote.analysis.rows){row.station=remote.stations[row.key];row.reason=remote.reasons[row.key];}return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[{key:'start',kind:'Start',start:body.points[0].t,end:body.points[0].t,lat:52,lon:13,direction:null}],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/train-journeys.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);

(async()=>{
 const container=new Element('div');
 const recorder=context.window.GpsRecorder.mount({userId:5,journeyId:'live-location',container,trainNumber:()=> '123',readonly:()=>false,selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){},resolve:async()=>({code:'BBB',name:'Berlin Beispiel'})});
 await recorder.readyPromise;await recorder.start();await new Promise(resolve=>setTimeout(resolve,5));
 const base=recorder.record.points[0].t,p=t=>({t:base+t,lat:52,lon:13,accuracy:5,speed:0});
 recorder.record.points=Array.from({length:61},(_,i)=>p(i*5000));
 const originalFetch=context.fetch;let lookups=0;
 context.fetch=async(path,options)=>path.startsWith('/api/v1/tf/gps/nearby?')?(lookups++,response({stations:[]})):originalFetch(path,options);
 await recorder.checkLiveStop();assert.equal(lookups,0);assert(!recorder.locationDialog);
 recorder.record.points.push(p(305000));const waiting=recorder.checkLiveStop();await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(lookups,1);assert(recorder.locationDialog);const count=recorder.record.points.length;
 recorder.locationDialog.manual.value='Freier Ortsname';await recorder.locationDialog.place.onclick();await waiting;
 assert.equal(recorder.record.points.length,count);assert.equal(recorder.record.locations[String(base)].name,'Freier Ortsname');assert.equal(recorder.record.locations[String(base)].code,'');
 assert.equal(tracks.get(recorder.key).value.locations[String(base)].name,'Freier Ortsname');await recorder.checkLiveStop();assert.equal(lookups,1);assert(!recorder.locationDialog);
 await recorder.sync();assert.equal(body.locations[String(base)].name,'Freier Ortsname');
 recorder.record.points.push({...p(310000),speed:10});
 for(let t=315000;t<=620000;t+=5000)recorder.record.points.push(p(t));
 const later=recorder.checkLiveStop();await new Promise(resolve=>setTimeout(resolve,5));assert(recorder.locationDialog);recorder.locationDialog.later.onclick();await later;
 await recorder.checkLiveStop();assert(!recorder.locationDialog);assert.equal(lookups,2);
 recorder.record.points.push({...p(625000),speed:10});for(let t=630000;t<=935000;t+=5000)recorder.record.points.push(p(t));
 const departed=recorder.checkLiveStop();await new Promise(resolve=>setTimeout(resolve,5));assert(recorder.locationDialog);recorder.record.points.push({...p(940000),speed:10});await recorder.checkLiveStop();await departed;assert(!recorder.locationDialog);
 assert.equal(context.window.GpsRecorder.liveStop([p(0),p(305000)]),null);
 assert.equal(context.window.GpsRecorder.liveStop(Array.from({length:63},(_,i)=>({...p(i*5000),accuracy:51}))),null);
 recorder.clear();console.log('GPS live prompt: strict five minutes, free text, persisted choices, no repeated question, departure cancellation and gaps: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
