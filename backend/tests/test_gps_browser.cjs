// Simulated browser contract test; no real GPS hardware or installed browser required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.value='';}
 append(...items){this.children.push(...items);}
 replaceChildren(){this.children=[];}
 setAttribute(key,value){this.attributes[key]=value;}
 click(){}
}
const tracks=new Map();
const database={transaction(){const tx={};tx.objectStore=()=>({get(key){const request={result:tracks.get(key)};queueMicrotask(()=>tx.oncomplete());return request;},put(row){tracks.set(row.key,structuredClone(row));queueMicrotask(()=>tx.oncomplete());return {};},delete(key){tracks.delete(key);queueMicrotask(()=>tx.oncomplete());return {};}});return tx;}};
let count=0,remote=null,body=null;
const response=(data,status=200)=>({status,ok:status<400,json:async()=>structuredClone(data)});
const context={console,Intl,Date,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:true,addEventListener(){}},fetch:async(path,options={})=>{if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[{key:'start',kind:'Start',start:body.points[0].t,end:body.points[0].t,lat:52,lon:13,direction:null}],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);
(async()=>{
 const field=new Element('input'),container=new Element('div');field.value='';
 const r=context.window.GpsRecorder.mount({userId:5,journeyId:'00000000-0000-4000-8000-000000000001',container,numberField:field,trainNumber:()=>field.value,readonly:()=>false,stations(){},resolve:async()=>({code:'BBB'})});
 await r.readyPromise;assert.equal(r.box.hidden,true);field.value='123';r.freeze();assert.equal(r.box.hidden,false);assert.equal(r.startButton.disabled,false);
 context.window.isSecureContext=false;await assert.rejects(r.start(),/HTTPS/);context.window.isSecureContext=true;
 await r.start();await new Promise(resolve=>setTimeout(resolve,5));assert(context.window.GpsRecorder.isActive());assert.equal(field.readOnly,true);assert.equal(r.record.points.length,1);
 await r.sample();assert.equal(r.record.points.length,2);await r.stop();assert.equal(context.window.GpsRecorder.isActive(),false);assert.equal(field.readOnly,false);assert.equal(body.ended,true);assert.equal(body.points.length,3);assert(!('actual_pause' in body));assert(tracks.get(r.key));assert.equal(r.stationInputs.length,1);
 await r.choose();assert.deepEqual(body.stations,{});await r.erase();assert.equal(r.record,null);assert.equal(tracks.has(r.key),false);
 console.log('GPS browser simulation passed: secure context, button gating, fixes, local persistence, stop/sync, station selection and delete.');
})().catch(error=>{console.error(error);process.exitCode=1;});
