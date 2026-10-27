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
 getBoundingClientRect(){return {left:0,top:0,width:600,height:300};}
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
 const r=context.window.GpsRecorder.mount({userId:5,journeyId:'map',container:new Element('div'),trainNumber:()=> '123',readonly:()=>false,stations(){}});await r.readyPromise;
 const point=(lat,lon,t)=>({lat,lon,t,accuracy:5,speed:10});r.record={points:[point(52,13,1),point(52.1,13.1,5001)],ended:false};r.drawMap();
 assert.equal(r.mapState.mode,'follow');assert(Math.abs(r.mapView.center.x-(193.1/360))<1e-12);assert(r.mapSvg.children.some(n=>String(n.attributes.href).includes('tiles.openrailwaymap.org')));
 r.mapZoomIn.onclick();assert.equal(r.mapView.zoom,16);assert.equal(r.mapState.mode,'follow');r.record.points.push(point(52.2,13.3,10001));r.drawMap();assert(Math.abs(r.mapView.center.x-(193.3/360))<1e-12);assert.equal(r.mapView.zoom,16);
 r.mapOverview.onclick();assert.equal(r.mapState.mode,'overview');assert.notEqual(r.mapView.center.x,(193.3/360));r.mapFollow.onclick();assert.equal(r.mapState.mode,'follow');
 const e=(pointerId,x,y)=>({pointerId,clientX:x,clientY:y,pointerType:'touch',target:r.mapSvg,preventDefault(){}});r.map.events.pointerdown(e(1,200,150));r.map.events.pointerdown(e(2,400,150));const zoom=r.mapView.zoom;r.map.events.pointermove(e(2,600,150));assert.equal(r.mapView.zoom,zoom+1);assert.equal(r.mapState.mode,'free');r.map.events.pointerup(e(1,200,150));r.map.events.pointerup(e(2,600,150));
 r.mapFollow.onclick();assert.equal(r.mapState.mode,'follow');r.mapState.zoom=19;r.drawMap();r.mapZoomIn.onclick();assert.equal(r.mapView.zoom,19);assert.equal(r.mapZoomIn.disabled,true);
 const layer=r.mapSvg.children.find(n=>String(n.attributes.href).includes('tiles.openrailwaymap.org'));layer.events.error();assert.equal(r.railFailed,true);assert(!r.mapSvg.children.some(n=>String(n.attributes.href).includes('tiles.openrailwaymap.org')));assert(r.mapSvg.children.some(n=>String(n.attributes.href).includes('tile.openstreetmap.org')));
 context.document.visibilityState='hidden';r.drawMap();assert(!r.mapSvg.children.some(n=>n.tag==='image'));assert(r.mapSvg.children.some(n=>n.tag==='polyline'));
 console.log('GPS map: live follow, preserved zoom, pinch, overview, zoom limits, ORM fallback and visible-only tiles: PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
