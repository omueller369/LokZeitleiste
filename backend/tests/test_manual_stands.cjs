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
let now=1793530800000;class Clock extends Date{constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}}
const context={console,Intl,Date:Clock,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{body:new Element('body'),visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:false,addEventListener(){}},fetch:async(path,options={})=>{if(path.startsWith('/api/v1/tf/gps/nearby?'))return response({stations:[{code:'BBB',name:'Berlin Beispiel',distance_m:100}],radius_m:5000});if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;remote.reasons=body.reasons;remote.selection=body.selection;remote.stations=Object.fromEntries(Object.entries(body.stations).map(([k,code])=>[k,{code,name:'Berlin Beispiel'}]));for(const row of remote.analysis.rows){row.station=remote.stations[row.key];row.reason=remote.reasons[row.key];}return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/train-journeys.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);

(async()=>{
 let imports=[],readonly=false;
 const options={userId:17,journeyId:'manual',container:new Element('div'),trainNumber:()=> '123',readonly:()=>readonly,stations(){},resolve:async()=>({code:'BBB',name:'Berlin Beispiel'}),importStops:async rows=>{imports.push(...rows);return true;}};
 const r=context.window.GpsRecorder.mount(options);await r.readyPromise;
 assert.equal(r.manualButton.textContent,'Start Stand');assert.equal(r.manualDuration.hidden,true);
 await r.toggleManual();assert.equal(count,0);assert.equal(r.manualButton.textContent,'Ende Stand');assert.equal(r.manualButton.attributes['aria-pressed'],'true');assert.equal(r.manualDuration.tag,'strong');assert.equal(r.manualDuration.hidden,false);assert(r.startButton.disabled);assert(context.window.GpsRecorder.isActive());
 const start=now;now+=125000;r.updateManual();assert(r.manualDuration.textContent.includes('2,1'));assert.equal(r.record.points.length,0);assert.equal(r.liveInputs.length,0);
 await r.start();assert.equal(count,0);assert.equal(r.record.points.length,0);
 // A reload recreates the controller; the stored timestamp resumes the timer.
 r.clearManual();const restored=context.window.GpsRecorder.mount(options);await restored.readyPromise;
 assert.equal(restored.manualButton.textContent,'Ende Stand');assert.equal(restored.manualRunning().start,start);assert(restored.manualDuration.textContent.includes('2,1'));
 const send=context.fetch;let release;context.fetch=(path,options)=>options?.method==='PUT'?new Promise(resolve=>{release=()=>send(path,options).then(resolve);}):send(path,options);const saving=restored.checkpoint();await new Promise(resolve=>setTimeout(resolve,5));
 now+=5000;await restored.toggleManual();release();await saving;context.fetch=send;assert.equal(body.points.length,0);assert.equal(body.manual_stops[0].start,start);assert.equal(body.manual_stops[0].end,null);assert.equal(restored.record.manual_stops[0].end,now);assert.equal(restored.record.dirty,true);assert.equal(restored.manualButton.textContent,'Start Stand');assert.equal(restored.manualDuration.hidden,true);assert.equal(restored.liveInputs.length,1);assert.equal(restored.liveInputs[0].row.start,start);assert.equal(restored.liveInputs[0].row.end,now);assert.equal(context.window.GpsRecorder.isActive(),false);
 const row=restored.liveInputs[0];row.station.value='BBB';row.station.oninput();row.detail.value='Warten auf Zug';row.detail.oninput();await row.take.onclick();assert.equal(imports.length,1);assert.equal(imports[0].key,'manual-'+start);assert.equal(imports[0].reason.reason,'sonstiges');assert.equal(imports[0].reason.detail,'Warten auf Zug');assert.equal(restored.liveInputs.length,0);
 await restored.sync();assert.equal(body.points.length,0);assert.equal(body.manual_stops[0].end,now);assert.equal(body.stop_edits['manual-'+start].imported,true);
 readonly=true;await restored.toggleManual();assert.equal(restored.manualRunning(),undefined);readonly=false;
 restored.record.points=[{t:now,lat:52,lon:13,accuracy:5,speed:0}];restored.record.ended=false;restored.freeze();assert(restored.manualButton.disabled);await assert.rejects(restored.toggleManual(),/laufende/);
 await restored.discard();assert.equal(tracks.has(restored.key),false);assert.equal(context.window.GpsRecorder.isActive(),false);
 // Time-only input uses the recorded date across midnight, with no visible seconds.
 const overnightStart=Date.parse('2026-11-01T23:57:48+01:00'),overnightEnd=Date.parse('2026-11-02T00:07:25+01:00'),overnightKey='manual-'+overnightStart;
 restored.record={train_number:'123',points:[],ended:true,detection_version:3,revision:0,manual_stops:[{key:overnightKey,start:overnightStart,end:overnightEnd}]};restored.draw();const overnight=restored.liveInputs[0];assert.equal(overnight.tr.children[1].children[0].textContent,'23:57');assert.equal(overnight.end.value,'00:07');overnight.station.value='BBB';overnight.station.oninput();assert.equal(restored.record.stop_edits[overnightKey].end,overnightEnd);overnight.end.value='00:12';overnight.end.oninput();assert.equal(restored.record.stop_edits[overnightKey].end,Date.parse('2026-11-02T00:12:00+01:00'));overnight.row.end=Date.parse('2026-11-03T00:20:00+01:00');overnight.station.oninput();assert.equal(restored.record.stop_edits[overnightKey].end,Date.parse('2026-11-02T00:12:00+01:00'));
 await overnight.remove.onclick();assert.equal(restored.liveInputs.length,0);assert.equal(restored.record.stop_edits[overnightKey].deleted,true);assert.equal(restored.record.manual_stops[0].end,overnightEnd);await restored.sync();assert.equal(body.stop_edits[overnightKey].deleted,true);restored.draw();assert.equal(restored.liveInputs.length,0);await restored.discard();
 const css=fs.readFileSync('backend/lokzeitleiste/static/work-report.css','utf8');assert(css.includes('.gps-box .gps-stand-toggle{background:#167b32'));assert(css.includes('[aria-pressed="true"]{background:#ba1424'));assert(css.includes('.gps-box .gps-stand-duration{color:#b00020;font-weight:800'));
 console.log('Manual stands: no GPS/HTTPS dependency, persisted start, live minutes, reload recovery, end/list/import, GPS exclusion, read-only, sync and discard: PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
