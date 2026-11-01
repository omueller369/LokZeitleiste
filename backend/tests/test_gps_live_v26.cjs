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
 let imports=[],stationQueries=0;const initialFetch=context.fetch;
 context.fetch=async(path,options)=>{if(path.includes('/nearby'))stationQueries++;return initialFetch(path,options);};
 const r=context.window.GpsRecorder.mount({userId:7,journeyId:'live-v26',container:new Element('div'),trainNumber:()=> '123',readonly:()=>false,selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),selectEnd:async()=>({code:'CCC',name:'Ziel'}),stations(){},resolve:async()=>({code:'BBB',name:'Berlin Beispiel'}),importStops:async rows=>{imports.push(...rows);return true;}});
 await r.readyPromise;await r.start();await new Promise(resolve=>setTimeout(resolve,5));
 const base=r.record.points[0].t,point=(delta,speed=0,accuracy=5)=>({t:base+delta,lat:52,lon:13,accuracy,speed});
 r.record.points=Array.from({length:48},(_,i)=>point(i*5000));r.draw();assert.equal(r.liveInputs.length,0);
 r.record.points.push(point(240000));r.draw();assert.equal(r.liveInputs.length,1);assert.equal(r.liveInputs[0].end.value,'');
 const row=r.liveInputs[0];row.station.value='BBB';row.station.oninput();row.detail.value='Warten auf Personal';row.detail.oninput();assert.equal(row.reason.value,'sonstiges');
 row.end.value=context.window.GpsRecorder.berlinInput(base+240000).slice(11,16);row.end.oninput();await row.take.onclick();
 assert.equal(imports.length,1);assert.equal(imports[0].end,base+240000);assert.equal(imports[0].station.code,'BBB');assert.equal(imports[0].reason.detail,'Warten auf Personal');assert.equal(r.liveInputs.length,0);
 assert(r.record.stop_edits['live-'+base].imported);assert.equal(r.record.points.length,49);r.draw();assert.equal(r.liveInputs.length,0);
 r.record.points.push({...point(245000,10),lon:13.002});for(let i=250000;i<=555000;i+=5000)r.record.points.push(point(i));r.draw();assert.equal(r.liveInputs.length,1);assert.equal(r.liveInputs[0].end.value,'');
 r.record.points.push({...point(560000,10),lon:13.002});r.draw();assert.equal(r.liveInputs[0].end.value,context.window.GpsRecorder.berlinInput(base+555000).slice(11,16));
 delete r.o.selectStart;const manualStart=r.chooseStart();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(r.startDialog.list.children.length,0);r.startDialog.manual.value='BBB';await r.startDialog.accept.onclick();assert.equal((await manualStart).name,'Berlin Beispiel');assert.equal(stationQueries,0);let warnings=0;context.window.ReportFeedback={error(){warnings++;}};context.navigator.onLine=false;r.fail('Failed to fetch');r.fail('Internetverbindung unterbrochen');assert.equal(warnings,0);context.navigator.onLine=true;
 const oldPoints=structuredClone(r.record.points);r.record.points=[point(0),point(60000)];r.drawMap();assert(r.mapSvg.children.some(e=>e.tag==='line'&&e.attributes['stroke-dasharray']==='6 4'));assert.deepEqual(r.record.points,[point(0),point(60000)]);let exported;context.window.AndroidPortal={saveBlob:async(name,blob)=>{exported=blob;}};r.export();await new Promise(resolve=>setTimeout(resolve,5));assert((await exported.text()).includes('<lzt:estimated>true</lzt:estimated>'));delete context.window.AndroidPortal;
 assert.equal(context.window.GpsRecorder.liveStops([point(0),point(305000)]).length,0);
 assert.equal(context.window.GpsRecorder.liveStops(Array.from({length:63},(_,i)=>point(i*5000,0,51))).length,0);
 assert.equal(context.window.GpsRecorder.berlinTime('2026-03-29T02:30:00'),null);
 const winter=base+240000;assert.equal(context.window.GpsRecorder.berlinTime(context.window.GpsRecorder.berlinInput(winter)),winter);
 r.record.points=oldPoints;const liveRecord=r.record;let finishRequest;context.fetch=async(path,options)=>options?.method==='PUT'?new Promise(resolve=>{finishRequest=()=>resolve(response({...JSON.parse(options.body),revision:7}));}):initialFetch(path,options);
 const checkpoint=r.checkpoint();await new Promise(resolve=>setTimeout(resolve,5));await r.add({timestamp:base+630000,coords:{latitude:52,longitude:13,accuracy:5,speed:10}});finishRequest();await checkpoint;assert.strictEqual(r.record,liveRecord);assert.equal(r.record.points.at(-1).t,base+630000);assert.equal(r.record.revision,7);assert.equal(r.record.dirty,true);
 await r.discard();assert.equal(context.window.GpsRecorder.isActive(),false);assert.equal(tracks.has(r.key),false);
 console.log('GPS 0.26: live list, manual end, custom reason, transfer/remove, measured-point preservation, gap bridge, no automatic station lookup, no network warning and concurrent checkpoint: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
