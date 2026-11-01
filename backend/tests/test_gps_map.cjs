// Simulated browser contract test; no real GPS hardware or installed browser required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
 constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.value='';this.events={};}
 addEventListener(k,f){this.events[k]=f;}
 contains(value){return this===value||this.children.some(child=>child.contains?.(value));}
 showModal(){this.open=true;}
 close(){this.open=false;}
 remove(){this.removed=true;}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(key,value){this.attributes[key]=value;}
 getAttribute(key){return this.attributes[key];}
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
 // Old recordings need no migration: markers are derived from original fixes.
 r.record={ended:true,points:Array.from({length:63},(_,i)=>({...point(52,13,100000+i*5000),speed:0}))};r.draw();
 const markers=()=>r.mapSvg.children.filter(n=>n.attributes['data-gps-stop']);assert.equal(markers().length,1);
 const marker=markers()[0];assert.equal(marker.children[0].attributes.fill,'#1565c0');assert.equal(marker.children[1].attributes.fill,'#d00000');
 const input=r.liveInputs[0].station;let focused=0,scrolled=0;input.focus=()=>focused++;input.scrollIntoView=()=>scrolled++;input.setSelectionRange=(a,b)=>assert.equal(a,b);marker.events.click();assert.equal(focused,1);assert.equal(scrolled,1);
 let prevented=false;marker.events.keydown({key:'Enter',preventDefault(){prevented=true;}});assert(prevented);assert.equal(focused,2);
 assert.equal(r.mapState.mode,'free');assert(r.mapView.zoom>=16);assert(markers()[0].attributes.transform.includes('translate(300 150)'));assert(markers()[0].attributes.transform.endsWith('scale(2)'));r.liveInputs[0].tr.events.focusout({relatedTarget:null});
 assert(markers()[0].attributes.transform.endsWith('scale(1)'));r.liveInputs[0].tr.events.focusin();assert(markers()[0].attributes.transform.endsWith('scale(2)'));
 const key=r.liveInputs[0].row.key;r.record.stop_edits={[key]:{imported:true}};let imported=null;r.o.focusImported=value=>imported=value;r.draw();assert.equal(r.liveInputs.length,0);markers()[0].events.click();assert.equal(imported,key);
 // Signal gaps do not invent stops, and short stationary runs have no marker.
 r.record={ended:true,points:[{...point(52,13,1),speed:0},{...point(52,13,400001),speed:0}]};r.draw();assert.equal(markers().length,0);
 for(const fixture of JSON.parse(fs.readFileSync('backend/tests/fixtures/gps-rail-stops.json','utf8'))){const actual=context.window.GpsRecorder.liveStops(fixture.points,true,fixture.edits).map(({start,end})=>({start,end}));assert.equal(JSON.stringify(actual),JSON.stringify(fixture.expected),fixture.name);}
 // A newly visible four-minute stop must not inherit the old s0 location of a later stop.
 const oldTrack=JSON.parse(fs.readFileSync('backend/tests/fixtures/gps-rail-stops.json','utf8')).find(f=>f.name==='two different stops').points;
 const base=oldTrack[0].t;r.record={ended:true,points:oldTrack.concat(Array.from({length:13},(_,i)=>({...oldTrack.at(-2),t:base+(495+i*5)*1000,speed:0}))).filter(p=>p.t!==base+495000),stations:{s0:{code:'CCC',name:'Old stop'}},reasons:{s0:{reason:'V1'}},selection:['s0']};
 // Keep the second stop stationary for >5 minutes so it was the only legacy stop.
 r.draw();assert.equal(r.liveInputs.length,2);assert.equal(r.liveInputs[0].station.value,'');assert.equal(r.liveInputs[1].station.value,'CCC · Old stop');assert.equal(r.record.selection[0],'s1');
 // Version-2 edited intervals are re-evaluated and merged; all source edits remain available.
 const mergedBase=1792627200000,oldKey='live-'+(mergedBase+300000),firstKey='live-'+mergedBase;
 r.record={ended:true,detection_version:2,points:Array.from({length:121},(_,i)=>({t:mergedBase+i*5000,lat:52,lon:13,accuracy:5,speed:0})),stop_edits:{[firstKey]:{station_input:'BBB · First',reason:'V1'},[oldKey]:{station_input:'CCC · Second',reason:'V3'}}};r.draw();assert.equal(r.liveInputs.length,1);assert.equal(markers().length,1);assert.equal(r.record.stop_edits[oldKey].station_input,'CCC · Second');assert(r.liveInputs[0].row.source_keys.includes(oldKey));
 const beforeDelete=JSON.stringify(r.record);await r.deleteStop(r.liveInputs[0].row);assert.equal(r.record.stop_edits[firstKey].deleted,true);assert.equal(r.record.stop_edits[oldKey].deleted,true);assert.equal(r.liveInputs.length,0);assert.equal(markers().length,0);r.record=JSON.parse(beforeDelete);r.draw();
 let focusedOld;r.o.hasImported=key=>key===oldKey;r.o.importedKeys=()=>[oldKey];r.o.focusImported=key=>focusedOld=key;r.draw();assert.equal(r.liveInputs.length,0);r.focusStop(firstKey);assert.equal(focusedOld,oldKey);r.setFocusedStop(oldKey);assert(markers()[0].attributes.transform.endsWith('scale(2)'));
 // Row clicks center and zoom the selected stop rather than the last GPS point.
 r.o.hasImported=()=>false;r.o.importedKeys=()=>[];r.record={ended:true,detection_version:3,points:JSON.parse(fs.readFileSync('backend/tests/fixtures/gps-rail-stops.json','utf8')).find(f=>f.name==='two different stops').points};r.mapState={mode:'overview',zoom:3};r.draw();
 const selected=r.liveInputs[0];selected.tr.onclick({target:{}});assert.equal(r.mapState.mode,'free');assert(r.mapView.zoom>=16);assert.equal(r.mapView.center.x,(13+180)/360);assert.equal(markers().find(m=>m.attributes['data-gps-stop']===selected.row.key).attributes.transform,'translate(300 150) scale(2)');
 const center={...r.mapView.center};r.drawMap();assert.deepEqual(r.mapView.center,center);r.mapState={mode:'free',zoom:12,center:{x:0,y:0}};r.drawMap();selected.tr.onclick({target:{}});assert(r.mapView.zoom>=16);assert.deepEqual(r.mapView.center,center);
 // All visible time fields use HH:MM, and changing a station preserves the measured seconds.
 r.record={ended:true,detection_version:3,points:Array.from({length:63},(_,i)=>({t:mergedBase+37123+i*5000,lat:52,lon:13,accuracy:5,speed:0}))};r.draw();const timed=r.liveInputs[0];assert.equal(timed.end.type,'time');assert.equal(timed.end.step,'60');assert.match(timed.end.value,/^\d{2}:\d{2}$/);assert.match(timed.tr.children[1].children[0].textContent,/^\d{2}:\d{2}$/);timed.station.value='BBB';timed.station.oninput();assert.equal(r.record.stop_edits[timed.row.key].end,r.record.points.at(-1).t);assert.equal(r.record.stop_edits[timed.row.key].manual_end,false);
 // Removing a halt keeps every fix, survives redraw and sync, and respects read-only/cancel.
 const original=JSON.stringify(r.record.points),deletedKey=timed.row.key;r.o.readonly=()=>true;await r.deleteStop(timed.row);assert.equal(r.liveInputs.length,1);r.o.readonly=()=>false;context.confirm=()=>false;await r.deleteStop(timed.row);assert.equal(r.liveInputs.length,1);context.confirm=()=>true;await timed.remove.onclick();assert.equal(r.liveInputs.length,0);assert.equal(markers().length,0);assert.equal(JSON.stringify(r.record.points),original);assert.equal(r.record.stop_edits[deletedKey].deleted,true);r.draw();assert.equal(r.liveInputs.length,0);r.record.train_number='123';await r.sync();assert.equal(body.stop_edits[deletedKey].deleted,true);assert.equal(r.liveInputs.length,0);
 // GPS/HTTPS warnings pass  the auto-dismiss option and clear their status after 3 seconds.
 const scheduled=[],notices=[];context.setTimeout=(fn,ms)=>{scheduled.push({fn,ms});return scheduled.length;};context.clearTimeout=id=>{if(scheduled[id-1])scheduled[id-1].cancelled=true;};context.window.ReportFeedback={error:(message,options)=>notices.push({message,options})};
 r.fail('GPS fehlt oder wurde abgelehnt. Aufzeichnung hat eine Lücke.');assert.equal(notices.at(-1).options.autoCloseMs,3000);assert.equal(scheduled.at(-1).ms,3000);scheduled.at(-1).fn();assert.equal(r.message.textContent,'');
 r.fail('GPS benötigt HTTPS oder localhost.');assert.equal(notices.at(-1).options.autoCloseMs,3000);const timeout=scheduled.at(-1);r.say('GPS-Aufzeichnung läuft.');assert(timeout.cancelled);assert.equal(r.message.textContent,'GPS-Aufzeichnung läuft.');
 r.fail('Präziser Standort wurde nicht erlaubt.');assert.equal(notices.at(-1).options.autoCloseMs,3000);
 r.fail('GPS konnte nicht lokal gespeichert werden. Bitte GPX herunterladen.');assert.equal(notices.at(-1).options.autoCloseMs,undefined);
 console.log('Rail stop fixtures, four-minute threshold, 100m jitter, >5kmh departure and transient GPS/HTTPS warnings: PASS');
 console.log('GPS stop markers: legacy fixes, two colors, click/keyboard focus, imported details and gap exclusion: PASS');
 console.log('GPS map: live follow, preserved zoom, pinch, overview, zoom limits, ORM fallback and visible-only tiles: PASS');
})().catch(e=>{console.error(e);process.exitCode=1;});
