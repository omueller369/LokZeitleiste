// Simulated browser contract test; no real GPS hardware or installed browser required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.value='';this.events={};}
 addEventListener(k,f){this.events[k]=f;}
 append(...items){this.children.push(...items);}
 replaceChildren(){this.children=[];}
 setAttribute(key,value){this.attributes[key]=value;}
 querySelector(tag){return this.children.find(child=>child.tag===tag)||null;}
 click(){}
}
const tracks=new Map();
const database={transaction(){const tx={};tx.objectStore=()=>({get(key){const request={result:tracks.get(key)};queueMicrotask(()=>tx.oncomplete());return request;},put(row){tracks.set(row.key,structuredClone(row));queueMicrotask(()=>tx.oncomplete());return {};},delete(key){tracks.delete(key);queueMicrotask(()=>tx.oncomplete());return {};}});return tx;}};
let count=0,remote=null,body=null;
const response=(data,status=200)=>({status,ok:status<400,json:async()=>structuredClone(data)});
const context={console,Intl,Date,Number,Math,Promise,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){},URL,Blob,confirm:()=>true,indexedDB:{open(){const request={result:database};queueMicrotask(()=>request.onsuccess());return request;}},document:{visibilityState:'visible',createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t),addEventListener(){}},navigator:{onLine:true,geolocation:{getCurrentPosition(resolve){resolve({timestamp:1792627200000+(count++)*5000,coords:{latitude:52,longitude:13,accuracy:5,speed:0}});}}},window:{isSecureContext:true,addEventListener(){}},fetch:async(path,options={})=>{if(options.method==='PUT'){body=JSON.parse(options.body);if(path.endsWith('/stations')){remote.revision++;remote.reasons=body.reasons;return response(remote);}remote={...body,revision:(remote?.revision||0)+1,analysis:{rows:[{key:'start',kind:'Start',start:body.points[0].t,end:body.points[0].t,lat:52,lon:13,direction:null}],gaps:[]}};return response(remote);}if(options.method==='POST')return response(remote);if(options.method==='DELETE'){remote=null;return response({ok:true});}return remote?response(remote):response({},404);}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/train-journeys.js','utf8'),context);
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/gps.js','utf8'),context);

let nativeRunning=false,nativePoints=[],opened=[];context.window.openActiveGpsReport=id=>opened.push(id);
context.window.AndroidPortal={gps:async(method,values)=>{if(method==='start'){nativeRunning=true;if(values.reset)nativePoints=[];return {};}if(method==='stop'){nativeRunning=false;return {};}if(method==='erase'){nativePoints=[];return {};}return {running:nativeRunning,points:nativePoints.filter(point=>point.t>values.after).slice(0,1000)};}};
(async()=>{
 const field=new Element('input'),container=new Element('div');field.value='123';
 const options={userId:5,journeyId:'00000000-0000-4000-8000-000000000001',container,numberField:field,trainNumber:()=>field.value,readonly:()=>false,selectEnd:async()=>({code:'CCC',name:'Ziel'}),selectStart:async()=>({code:'BBB',name:'Berlin Beispiel'}),stations(){},resolve:async()=>({code:'BBB'})};
 context.window.isSecureContext=false;let recorder=context.window.GpsRecorder.mount(options);await recorder.readyPromise;await recorder.start();assert(nativeRunning);assert(context.window.GpsRecorder.isActive());
 nativePoints.push({t:1792627200000,lat:52,lon:13,accuracy:5,speed:0});await recorder.nativeRead();assert.equal(recorder.record.points.length,1);
 recorder.clear();assert(nativeRunning);nativePoints.push({t:1792627205000,lat:52,lon:13,accuracy:5,speed:0});recorder=context.window.GpsRecorder.mount(options);await recorder.readyPromise;assert(context.window.GpsRecorder.isActive());assert.equal(recorder.record.points.length,2);assert(opened.includes(options.journeyId));const before=opened.length;await recorder.nativeRead();assert.equal(opened.length,before);
 await recorder.stop();assert(!nativeRunning);assert(recorder.record.ended);assert.equal(body.points.length,2);const prior=recorder.record,adapter=context.window.AndroidPortal.gps;context.window.AndroidPortal.gps=async(method,values)=>{if(method==='start')throw Error('Permission denied');return adapter(method,values);};await assert.rejects(recorder.start());assert.strictEqual(recorder.record,prior);context.window.AndroidPortal.gps=adapter;await recorder.erase();assert.equal(nativePoints.length,0);
 console.log('Android GPS: native start, journal merge, WebView recovery, stop/sync and erase passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
