(()=>{
const t=s=>window.I18n?.t(s)||s,node=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
let active=null,manualActive=null,dbPromise;
function db(){if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{const r=indexedDB.open('lokzeitleiste.gps',1);r.onupgradeneeded=()=>r.result.createObjectStore('tracks',{keyPath:'key'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});return dbPromise;}
async function local(key,value){const database=await db();return new Promise((resolve,reject)=>{const transaction=database.transaction('tracks',value===undefined?'readonly':'readwrite'),store=transaction.objectStore('tracks'),request=value===undefined?store.get(key):value===null?store.delete(key):store.put({key,value});transaction.oncomplete=()=>resolve(value===undefined?request.result?.value:value);transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);});}
async function api(path,options={}){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});if(r.status===404)return null;const data=await r.json().catch(()=>({}));if(!r.ok){const error=Error(typeof data.detail==='string'?data.detail:t(globalThis.CtlText.source("portal_gps.text_03169f7c2fb3")));error.status=r.status;throw error;}return data;}
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const berlinDate=ms=>new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(ms));
function stamp(ms,previous){const time=new Intl.DateTimeFormat(window.I18n?.locale||'de-DE',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(ms));return previous&&berlinDate(ms)!==berlinDate(previous)?new Intl.DateTimeFormat(window.I18n?.locale||'de-DE',{timeZone:'Europe/Berlin',dateStyle:'short'}).format(new Date(ms))+' · '+time:time;}
function download(name,content,type){if(window.AndroidPortal){window.AndroidPortal.saveBlob(name,new Blob([content],{type})).catch(error=>window.ReportFeedback?.error(error.message));return;}const url=URL.createObjectURL(new Blob([content],{type})),anchor=node('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function berlinInput(ms){const p=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(new Date(ms)).map(p=>[p.type,p.value]));return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute+':'+p.second;}
function berlinTime(value){if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value))return null;const wall=Date.parse(value+(value.length===16?':00':'')+'Z');let result=wall;for(let i=0;i<3;i++)result+=wall-Date.parse(berlinInput(result)+'Z');return berlinInput(result).slice(0,value.length)===value?result:null;}
const clock=ms=>berlinInput(ms).slice(11,16);
const placeLabel=place=>place?[place.code,place.name].filter(Boolean).join(' · '):'';
const durationLabel=ms=>[Math.floor(ms/3600000),Math.floor(ms/60000)%60].map(n=>String(n).padStart(2,'0')).join(':');
const projectPoint=p=>{const lat=Math.max(-85,Math.min(85,p.lat))*Math.PI/180;return{x:(p.lon+180)/360,y:(1-Math.log(Math.tan(lat)+1/Math.cos(lat))/Math.PI)/2};};
function stopEnd(row,value,previous){
 if(!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value))return null;
 const anchor=previous||row.end||row.observed_end||row.start;let day=berlinInput(anchor).slice(0,10),result=berlinTime(day+'T'+value);
 if(result!=null&&result<=row.start&&value<clock(row.start)&&day===berlinInput(row.start).slice(0,10)){
  day=new Date(Date.parse(day+'T12:00:00Z')+86400000).toISOString().slice(0,10);result=berlinTime(day+'T'+value);
 }
 return result;
}
const distance=(a,b)=>{const r=Math.PI/180,h=Math.sin((b.lat-a.lat)*r/2)**2+Math.cos(a.lat*r)*Math.cos(b.lat*r)*Math.sin((b.lon-a.lon)*r/2)**2;return 6371000*2*Math.asin(Math.min(1,Math.sqrt(h)));};
const speedAt=(p,last)=>p.speed??(last&&last.accuracy<=50&&p.t>last.t&&p.t-last.t<=30000?distance(last,p)/((p.t-last.t)/1000):null);
// A fixed scale keeps colors comparable between recordings and while zooming.
const trailScale=[[0,[25,85,195]],[60,[0,119,70]],[120,[207,107,0]],[160,[190,22,40]]];
const trailColor=rgb=>'rgb('+rgb.join(',')+')';
const unknownTrail='#626b78';
function speedColor(speed){
 if(!Number.isFinite(speed))return unknownTrail;
 const kmh=Math.min(160,Math.max(0,Math.round(speed*3.6/5)*5));
 const end=trailScale.findIndex(([limit])=>limit>=kmh);
 if(end===0)return trailColor(trailScale[0][1]);
 const [startSpeed,startColor]=trailScale[end-1],[endSpeed,endColor]=trailScale[end];
 const fraction=(kmh-startSpeed)/(endSpeed-startSpeed);
 return trailColor(startColor.map((channel,index)=>Math.round(channel+(endColor[index]-channel)*fraction)));
}

// Four consecutive accurate fixes must show sustained movement in one direction.
function* confirmedMotion(points, inclusive){
 const fast=speed=>inclusive?speed>=10:speed>10;
 for(let i=0;i+3<points.length;i++){
  const fixes=points.slice(i,i+4);
  if(fixes.some(p=>p.accuracy>50||(p.speed!=null&&!fast(p.speed*3.6))))continue;
  let path=0,valid=true;
  for(let j=1;j<fixes.length;j++){
   const elapsed=fixes[j].t-fixes[j-1].t,meters=distance(fixes[j-1],fixes[j]);
   if(elapsed<=0||elapsed>30000||!fast(meters*3600/elapsed)){valid=false;break;}
   path+=meters;
  }
  if(valid&&distance(fixes[0],fixes[3])>=0.75*path&&fast(distance(fixes[0],fixes[3])*3600/(fixes[3].t-fixes[0].t)))yield fixes[0].t;
 }
}
// Current rail rule: start below 5 km/h, finish above 10 km/h; keep local drift together.
function liveStops(points,ended=false,edits={},legacy=false,version2=false,version3=false,version4=false,display=null,totals=null){
 let run=[],last=null,rows=[],previousState=null;const previousRule=version2||version3;
 const confirmed=legacy||previousRule||version4?null:new Set(confirmedMotion(points,false));
 const finish=closed=>{const duration=run.length>1?run.at(-1).t-run[0].t:0;if(legacy?duration>300000:previousRule?duration>=240000:duration>120000)rows.push({key:'live-'+run[0].t,kind:globalThis.CtlText.source("portal_gps.text_0fd998791d67"),start:run[0].t,end:closed?run.at(-1).t:null,observed_end:run.at(-1).t,lat:run[0].lat,lon:run[0].lon});run=[];};
 for(const p of points){
  if(totals&&previousState&&p.accuracy<=50&&p.t>last.t&&p.t-last.t<=30000)totals[previousState]+=p.t-last.t;
  if(last&&p.t-last.t>30000)finish(ended);
  if(p.accuracy>50){finish(ended);last=p;previousState=null;display?.push(p);continue;}
  // Existing edited/imported stops retain their identity after an update.
  if(version2&&run.length&&edits?.['live-'+p.t])finish(true);
  const speed=speedAt(p,last);
  if(legacy){if(speed!=null&&speed*3.6<3)run.push(p);else finish(true);}
  else if(run.length){const nearby=distance(run[0],p)<=100+1e-6;if(confirmed?confirmed.has(p.t):speed!=null&&speed*3.6>(previousRule?5:10)&&(!nearby||(p.speed!=null&&!previousRule)))finish(true);else if(nearby)run.push(p);}
  else if(!confirmed?.has(p.t)&&speed!=null&&speed*3.6<(previousRule?3:5))run.push(p);
  if(totals)previousState=run.length?'stopped':speed!=null||confirmed?.has(p.t)?'moving':null;
  if(display)display.push({...p,lat:run.length?run[0].lat:p.lat,lon:run.length?run[0].lon:p.lon,mapSpeed:run.length?0:speed});
  last=p;
 }
 finish(ended);return rows;
}
// Upgrade cached legacy assignments by start time, never by a newly shifted row number.
function normaliseRecording(record){
 if(!record||record.detection_version===5)return;
 const edits=record.stop_edits||{},old=liveStops(record.points||[],true,edits,![2,3,4].includes(record.detection_version),record.detection_version===2,record.detection_version===3,record.detection_version===4);
 for(const [i,row]of old.entries()){
  const station=record.stations?.['s'+i]||record.locations?.[String(row.start)],reason=record.reasons?.['s'+i]||{};
  if(!edits[row.key]&&(station||reason.reason))edits[row.key]={station,station_input:station?(station.code?station.code+' · ':'')+station.name:'',reason:reason.reason||'',detail:reason.detail||'',imported:false};
 }
 record.stop_edits=edits;
 const fresh=liveStops(record.points||[],true,edits),mapping={start:'start',end:'end'};
 for(const [i,row]of old.entries()){const j=fresh.findIndex(item=>item.start<=row.start&&(item.end||item.observed_end)>=row.start);if(j>=0)mapping['s'+i]='s'+j;}
 for(const field of ['stations','reasons']){const values={};for(const [key,value]of Object.entries(record[field]||{}))if(mapping[key]&&!(mapping[key] in values))values[mapping[key]]=value;record[field]=values;}
 record.selection=[...new Set((record.selection||[]).filter(key=>mapping[key]).map(key=>mapping[key]))];record.detection_version=5;
}
function firstDeparture(points){
 return confirmedMotion(points,true).next().value??null;
}
function lastMovement(points){
 let last=null;
 for(const time of confirmedMotion(points,true))last=time;
 if(last===null)return null;
 // A confirmed sequence includes three more fixes after its first point.
 const end=points.findIndex(point=>point.t===last)+3;
 for(let i=points.length-1;i>end;i--){
  const point=points[i];
  if(point.accuracy<=50&&point.speed!=null&&point.speed*3.6>=5)return point.t;
 }
 return points[end].t;
}
const gpsNotice=message=>/HTTPS|localhost|Standortfreigabe|Standortberechtigung|Standort.*(nicht erlaubt|verweigert|abgelehnt|fehlt)|geolocation|GPS.*(Signal|fehlt|abgelehnt|ausfall|ungenau|einschalten|gestartet|Fix|Dienst|aussetzen|Position)/i.test(message);

class Recorder{
 constructor(o){this.o=o;this.key=o.userId+'.'+o.journeyId;this.path='/api/v1/tf/gps/'+o.journeyId;this.record=null;this.analysis=null;this.pending=false;this.loading=false;this.stationInputs=[];this.box=node('section');this.box.className='gps-box';this.heading=node('h3',globalThis.CtlText.source("portal_gps.text_9313f74419cd"));this.box.append(this.heading);
 this.hint=node('p',globalThis.CtlText.source("portal_gps.text_4db3ec741184"));if(window.AndroidPortal){this.heading.textContent=t(globalThis.CtlText.source("portal_gps.text_af2c7de76a15"));this.hint.textContent=t(globalThis.CtlText.source("portal_gps.text_8f6bcc8fd171"));}this.content=node('div');this.content.id='gps-content-'+this.o.userId+'-'+this.o.journeyId;this.content.className='gps-block-content';this.content.hidden=true;this.collapseButton=node('button','+');this.collapseButton.type='button';this.collapseButton.className='report-block-toggle';this.collapseButton.setAttribute('data-i18n-ignore','');this.collapseButton.setAttribute('aria-controls',this.content.id);this.collapseButton.onclick=()=>this.setExpanded(this.content.hidden);this.heading.append(this.collapseButton);this.box.append(this.content);this.updateCollapse();this.content.append(this.hint);const tools=node('div');tools.className='gps-tools';
 const button=(label,fn)=>{const b=node('button',label);b.type='button';b.onclick=()=>this.run(fn);tools.append(b);return b;};
 this.manualButton=button(globalThis.CtlText.source("portal_gps.text_ea7a852a9397"),()=>this.toggleManual());this.manualButton.className='gps-stand-toggle';this.manualDuration=node('strong');this.manualDuration.className='gps-stand-duration';this.manualDuration.setAttribute('role','timer');this.manualDuration.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_a698bdef0fac")));this.manualDuration.setAttribute('data-i18n-ignore','');tools.append(this.manualDuration);
 this.startButton=button(globalThis.CtlText.source("portal_gps.text_0a08578cb4ee"),()=>this.start());this.helpButton=button('?',()=>this.help());this.helpButton.onclick=()=>this.help();this.helpButton.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_9864176d9d3d")));this.importButton=button(globalThis.CtlText.source("portal_gps.text_936378b371b9"),()=>this.importStops());this.stopButton=button(globalThis.CtlText.source("portal_gps.text_dd9f56658b7d"),()=>this.stop());this.syncButton=button(globalThis.CtlText.source("portal_gps.text_ea75d1374ab3"),()=>this.sync());this.loadButton=button(globalThis.CtlText.source("portal_gps.text_b4ba21896850"),()=>this.reload());this.resolveButton=button(globalThis.CtlText.source("portal_gps.text_0d03c4f256ee"),()=>this.resolve());this.choiceButton=button(globalThis.CtlText.source("portal_gps.text_8bf8e40c1815"),()=>this.choose());this.exportButton=button(globalThis.CtlText.source("portal_gps.text_acdcacf4345a"),()=>this.export());this.deleteButton=button(globalThis.CtlText.source("portal_gps.text_f4e43a8d31f2"),()=>this.erase());this.content.append(tools);this.message=node('p');this.message.setAttribute('role','status');this.message.setAttribute('aria-live','polite');this.message.setAttribute('data-i18n-ignore','');this.content.append(this.message);this.map=node('div');this.map.className='gps-map';this.setupMap();this.results=node('div');this.results.className='excel-scroll';this.content.append(this.map,this.results);o.container.append(this.box);
 this.readyPromise=this.read();window.addEventListener('languagechange',()=>{this.updateCollapse();this.draw();});document.addEventListener('visibilitychange',()=>{if(active===this&&!window.AndroidPortal){if(document.visibilityState==='hidden')this.say(globalThis.CtlText.source("portal_gps.text_625519aef9da"));else{this.say(globalThis.CtlText.source("portal_gps.text_2bf0ce6687cd"));this.wake();}}});this.freeze();
 }
 updateCollapse(){this.collapseButton.textContent=this.content.hidden?'+':'−';this.collapseButton.setAttribute('aria-expanded',String(!this.content.hidden));this.collapseButton.setAttribute('aria-label',t(this.content.hidden?globalThis.CtlText.source("portal_gps.text_37e7d85ac04d"):globalThis.CtlText.source("portal_gps.text_357b8d0b4dc0")));}
 setExpanded(expanded){this.content.hidden=!expanded;this.updateCollapse();if(expanded)this.draw();}
 say(message){clearTimeout(this.messageTimer);this.message.textContent=t(message);if(gpsNotice(message))this.messageTimer=setTimeout(()=>{this.message.textContent='';},3000);}
 fail(message){if(navigator.onLine===false||/fetch|network|internet|verbindung/i.test(message)){this.say(globalThis.CtlText.source("portal_gps.text_05b6b4dee7bc"));return;}this.say(message);if(this.lastError!==message)window.ReportFeedback?.error(message,gpsNotice(message)?{autoCloseMs:3000}:{});this.lastError=message;}
 async run(action){if(this.loading)return;this.loading=true;this.freeze();try{await this.readyPromise;await action();}catch(error){this.fail(error.message);}finally{this.loading=false;this.freeze();}}
 past(){const day=this.o.dutyDay?.();return !!day&&day<new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());}
 recordForDay(){return this.forDay(this.record);}
 forDay(record){return !!record&&(record.points?.some(p=>berlinDate(p.t)===this.o.dutyDay?.())||record.manual_stops?.some(row=>berlinDate(row.start)===this.o.dutyDay?.()));}
 serverForDay(){return this.forDay(this.serverRecord);}
 async read(){try{const saved=await local(this.key);if(saved){this.record=saved;this.analysis=saved.analysis||null;this.say(saved.manual_stops?.some(row=>!row.end)?globalThis.CtlText.source("portal_gps.text_9e4ff21163f0"):saved.ended?globalThis.CtlText.source("portal_gps.text_ed23cbcf3cb4"):globalThis.CtlText.source("portal_gps.text_3f4e4b5c92b7"));}if(navigator.onLine){const remote=await api(this.path);this.serverRecord=remote;if(this.past()){this.record=this.forDay(saved)?saved:this.serverForDay()?remote:null;this.analysis=this.record?.analysis||null;}else if(remote&&(!saved||(!saved.dirty&&remote.revision>=(saved.revision||0)))){this.record={...remote,dirty:false,reason_drafts:saved?.reason_drafts||{},station_drafts:saved?.station_drafts||{},selection:saved?.selection??remote.selection??[]};this.analysis=remote.analysis;await local(this.key,this.record);}}}catch(error){this.fail(error.message);}if(window.AndroidPortal&&!this.past()){try{await this.nativeRead();}catch(error){this.fail(error.message);}}this.draw();}
 freeze(){for(const row of this.liveInputs||[]){const disabled=this.loading||this.o.readonly();for(const field of [row.station,row.reason,row.detail,row.end,row.take,row.remove])field.disabled=disabled;}this.importButton.hidden=true;this.resolveButton.hidden=this.choiceButton.hidden=true;this.importButton.disabled=this.loading||this.o.readonly()||this.past()||!this.record?.selection?.length;this.updateManual();const running=active===this,hasGps=!!this.record?.points?.length,has=hasGps||!!this.record?.manual_stops?.length,number=this.o.trainNumber().trim();this.box.hidden=!number&&!has;if(this.o.numberField)this.o.numberField.readOnly=running||!!this.manualRunning();this.startButton.hidden=running;this.manualButton.hidden=this.past()&&!this.manualRunning();this.manualButton.disabled=this.loading||this.o.readonly()||(!this.manualRunning()&&(!!active||!!manualActive||(hasGps&&!this.record.ended)))||!/^[A-Za-z0-9]{1,12}$/.test(number);this.startButton.disabled=this.loading||this.o.readonly()||!!active||!!manualActive||!/^[A-Za-z0-9]{1,12}$/.test(number);this.startButton.textContent=t(has&&!this.record.ended?globalThis.CtlText.source("portal_gps.text_f424ce8fdf10"):globalThis.CtlText.source("portal_gps.text_0a08578cb4ee"));this.stopButton.hidden=!(running||(hasGps&&!this.record.ended));this.stopButton.disabled=this.loading;for(const button of [this.syncButton,this.exportButton,this.deleteButton]){button.hidden=!has;button.disabled=this.loading||running||!!this.manualRunning();}this.exportButton.hidden=!hasGps;this.loadButton.disabled=this.loading||running||!!this.manualRunning();this.resolveButton.hidden=this.choiceButton.hidden=true;this.resolveButton.disabled=this.choiceButton.disabled=this.loading||running;if(this.past()){this.box.hidden=!this.recordForDay();for(const button of [this.startButton,this.stopButton,this.syncButton,this.exportButton,this.deleteButton,this.resolveButton,this.choiceButton,this.importButton])button.hidden=true;this.loadButton.hidden=false;this.hint.hidden=true;for(const {input,reason,detail,check} of this.stationInputs)input.disabled=reason.disabled=detail.disabled=check.disabled=true;}else{this.loadButton.hidden=false;this.hint.hidden=false;}}
 manualRunning(){return this.record?.manual_stops?.find(row=>!row.end);}
 rows(){if(!this.record)return [];const edits=this.record.stop_edits||{};return [...liveStops(this.record.points||[],!!this.record.ended),...(this.record.manual_stops||[]).filter(row=>row.end).map(row=>({...row,kind:globalThis.CtlText.source("portal_gps.text_0fd998791d67"),manual:true}))].map(row=>{const keys=row.manual?[row.key]:[row.key,...Object.keys(edits).filter(key=>key.startsWith('live-')&&Number(key.slice(5))>=row.start&&Number(key.slice(5))<=(row.end||row.observed_end)),...(this.o.importedKeys?.()||[]).filter(key=>key.startsWith('live-')&&Number(key.slice(5))>=row.start&&Number(key.slice(5))<=(row.end||row.observed_end))];return {...row,source_keys:[...new Set(keys)]};}).sort((a,b)=>a.start-b.start||String(a.key).localeCompare(String(b.key)));}
 removed(row){return row.source_keys.some(key=>this.record.stop_edits?.[key]?.deleted);}
 async deleteStop(row){
 if(this.o.readonly()||this.imported(row)||this.removed(row))return;
 if(!confirm(t(globalThis.CtlText.source("portal_gps.text_8a25c4e048ac"))))return;
 const previous=JSON.parse(JSON.stringify(this.record.stop_edits||{})),wasDirty=this.record.dirty;this.record.stop_edits||={};for(const key of row.source_keys)this.record.stop_edits[key]={...this.record.stop_edits[key],deleted:true};this.record.dirty=true;
 try{await this.persist();}catch(error){this.record.stop_edits=previous;this.record.dirty=wasDirty;throw error;}
 if(row.source_keys.includes(this.focusedStopKey))this.setFocusedStop(null);this.draw();this.o.changed?.();
 }
 imported(row){return row.source_keys.some(key=>this.record.stop_edits?.[key]?.imported||this.o.hasImported?.(key));}
 updateManual(){const row=this.manualRunning();this.manualButton.textContent=t(row?globalThis.CtlText.source("portal_gps.text_da1612a26c8c"):globalThis.CtlText.source("portal_gps.text_ea7a852a9397"));this.manualButton.setAttribute('aria-pressed',String(!!row));this.manualDuration.hidden=!row;if(row)this.manualDuration.textContent=new Intl.NumberFormat(window.I18n?.locale||'de-DE',{minimumFractionDigits:1,maximumFractionDigits:1}).format(Math.max(0,Date.now()-row.start)/60000)+globalThis.CtlText.source("portal_gps.text_2e75737a6b58");if(row&&!this.manualTimer){manualActive=this;this.manualTimer=setInterval(()=>this.updateManual(),1000);}if(!row)this.clearManual();}
 clearManual(){clearInterval(this.manualTimer);this.manualTimer=null;if(manualActive===this)manualActive=null;}
 async toggleManual(){
 if(this.o.readonly())return;
 const running=this.manualRunning();if(this.past()&&!running)return;if(!running&&(active||manualActive||this.record?.points?.length&&!this.record.ended))throw Error(t(globalThis.CtlText.source("portal_gps.text_13b0c930ce1a")));
 const number=this.o.trainNumber().trim();if(!/^[A-Za-z0-9]{1,12}$/.test(number))throw Error(t(globalThis.CtlText.source("portal_gps.text_b9009a6c1629")));
 const prior=this.record?JSON.parse(JSON.stringify(this.record)):null,now=Date.now();
 if(running){if(now<=running.start)throw Error(t(globalThis.CtlText.source("portal_gps.text_5241a073e0be")));running.end=now;}
 else {this.record||={train_number:number,points:[],ended:true,revision:0,detection_version:5};this.record.manual_stops||=[];if(this.record.manual_stops.length>=500)throw Error(t(globalThis.CtlText.source("portal_gps.text_c704954a2ce2")));this.record.manual_stops.push({key:'manual-'+now,start:now,end:null});}
 this.record.dirty=true;try{await this.persist();}catch(error){this.record=prior;throw error;}
 this.updateManual();this.draw();this.o.changed?.();if(running)this.say(globalThis.CtlText.source("portal_gps.text_3e685afd44c8"));
 }
 applyDeparture(){if(!this.record||this.record.ended||this.record.departure_applied||this.o.readonly()||!this.o.journeyTime)return;const time=firstDeparture(this.record.points||[]);if(time==null)return;this.o.journeyTime('start',time);this.record.departure_applied=true;this.record.dirty=true;return true;}
 async persist(){if(this.record)await local(this.key,this.record);}
 async wake(){try{if(navigator.wakeLock&&document.visibilityState==='visible'){await this.wakeLock?.release();this.wakeLock=await navigator.wakeLock.request('screen');}}catch(error){/* Recording remains possible without optional screen wake lock. */}}
 fix(){return new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,reject,{enableHighAccuracy:true,maximumAge:0,timeout:12000}));}
 async add(position){if(active!==this)return;const c=position.coords,timestamp=Math.floor(position.timestamp);if(!Number.isFinite(c.latitude)||!Number.isFinite(c.longitude)||!Number.isFinite(c.accuracy))return;const previous=this.record.points.at(-1);if(previous&&timestamp<=previous.t)return;if(c.accuracy>100000)return;
 if(this.record.points.length>=20000||(this.record.points.length&&timestamp-this.record.points[0].t>48*3600000)){await this.stop(false);this.say(globalThis.CtlText.source("portal_gps.text_a25eb4b089e0"));return;}
 this.record.points.push({t:timestamp,lat:c.latitude,lon:c.longitude,accuracy:c.accuracy,speed:Number.isFinite(c.speed)&&c.speed>=0&&c.speed<=200?c.speed:null});this.record.dirty=true;this.applyDeparture();
 try{await this.persist();}catch(error){this.clear();this.fail(globalThis.CtlText.source("portal_gps.text_be16e184bac2"));this.freeze();return;}
 this.lastError=null;this.say(t(globalThis.CtlText.source("portal_gps.text_e11d7606e7e0"))+' '+this.record.points.length+' · '+Math.round(c.accuracy)+' m');this.draw();
 }
 async sample(){if(this.pending||active!==this)return;this.pending=true;try{await this.add(await this.fix());}catch(error){if(active===this){this.fail(globalThis.CtlText.source("portal_gps.text_754c85b57a48"));if(error.code===1){this.clear();this.freeze();}}}finally{this.pending=false;}}
 async nativeRead(){let running=false;for(;;){const previous=this.record?.points?.at(-1)?.t||0,result=await window.AndroidPortal.gps('snapshot',{key:this.key,after:previous});running=result.running;if(result.points.length){if(!this.record)this.record={train_number:this.o.trainNumber().trim(),points:[],ended:false,revision:0,dirty:true};for(const point of result.points)if(point.t>(this.record.points.at(-1)?.t||0))this.record.points.push(point);this.record.dirty=true;await this.persist();}if(result.points.length<1000)break;}if(active!==this&&this.record?.points?.length&&!this.record.ended)window.openActiveGpsReport?.(this.o.journeyId);if(running&&!active){window.openActiveGpsReport?.(this.o.journeyId);active=this;this.record.ended=false;this.nativeTimer=setInterval(()=>this.nativeRead().catch(error=>this.fail(error.message)),5000);}if(this.applyDeparture())await this.persist();if(active===this&&!running){clearInterval(this.nativeTimer);active=null;this.say(globalThis.CtlText.source("portal_gps.text_989a5a596446"));}this.draw();this.freeze();}
 async nativeStart(){const prior=this.record,reset=!this.record||this.record.ended;if(reset)this.record={train_number:this.o.trainNumber().trim(),departure_applied:false,points:[],manual_stops:this.record?.manual_stops||[],stop_edits:Object.fromEntries(Object.entries(this.record?.stop_edits||{}).filter(([key])=>key.startsWith('manual-'))),detection_version:5,ended:false,revision:this.record?.revision||0,dirty:true};try{await window.AndroidPortal.gps('start',{key:this.key,reset});}catch(error){this.record=prior;throw error;}active=this;this.record.ended=false;this.setEndpoint('start',this.startChoice);this.setEndpoint('end',this.endChoice);this.analysis=null;this.record.analysis=null;this.record.reasons={};this.record.reason_drafts={};await this.persist();this.nativeTimer=setInterval(()=>this.nativeRead().catch(error=>this.fail(error.message)),5000);await this.nativeRead();this.freeze();this.o.changed?.();}
 async help(){try{const reader=window.TfHelp||await window.loadTfHelp?.();if(!reader)throw Error(globalThis.CtlText.source("portal_gps.text_423e45b97d3e"));reader.open('gps');}catch(error){this.fail(error.message);}}
 chooseEndpoint(kind){
 if(kind==='start'&&this.o.selectStart)return this.o.selectStart();
 if(kind==='end'&&this.o.selectEnd)return this.o.selectEnd();
 const dialog=node('dialog'),title=node('h2',t(kind==='start'?globalThis.CtlText.source("portal_gps.text_9227f0b954f4"):globalThis.CtlText.source("portal_gps.text_26b65b9318e6"))),manual=node('input'),list=node('datalist'),message=node('p'),accept=node('button',t(globalThis.CtlText.source("portal_gps.text_aa30480ab57a"))),cancel=node('button',t(globalThis.CtlText.source("portal_gps.text_f7ff1178af20")));
 dialog.className='gps-dialog';manual.maxLength=270;manual.placeholder=t(globalThis.CtlText.source("portal_gps.text_3ac37da56214"));manual.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_3ac37da56214")));list.id='gps-'+kind+'-'+this.o.journeyId;manual.setAttribute('list',list.id);this.o.stations(manual,list);accept.type=cancel.type='button';message.setAttribute('role','status');dialog.append(title,manual,list,message,accept,cancel);document.body.append(dialog);
 const state={dialog,manual,list,accept,cancel};if(kind==='start')this.startDialog=state;else this.endDialog=state;
 return new Promise(resolve=>{let done=false;const finish=choice=>{if(done)return;done=true;dialog.close();dialog.remove();resolve(choice);};cancel.onclick=()=>finish(null);dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});accept.onclick=async()=>{accept.disabled=true;try{if(!manual.value.trim())throw Error(t(globalThis.CtlText.source("portal_gps.text_f177c377fb1f")));const choice=await this.o.resolve(manual);finish(choice);}catch(error){message.textContent=t(globalThis.CtlText.source("portal_gps.text_b675bc7ca31b"));}finally{accept.disabled=false;}};dialog.showModal();});
 }
 async selectedEndpoint(kind){
 const current=await (this.o.selectedEndpoint?.(kind)??this.o.endpointStation?.(kind));
 if(current?.code||current?.name)return current;
 if(this.record&&!this.record.ended){
  const code=this.record[kind+'_station']||'',name=this.record[kind+'_station_name']||this.record.stations?.[kind]?.name||'';
  if(code||name)return {code,name};
 }
 return null;
 }
 async prepareEndpoints(){for(const kind of ['start','end']){const choice=await this.selectedEndpoint(kind)||await this.chooseEndpoint(kind);if(!choice)return false;this[kind+'Choice']=choice;this.o.endpoint?.(kind,choice);}return true;}
 chooseStart(){return this.chooseEndpoint('start');}
 setEndpoint(kind,place){
  this.record[kind+'_station']=place.code||null;
  this.record[kind+'_station_name']=place.name||'';
 }
 async chooseEnd(){const choice=await this.selectedEndpoint('end')||await this.chooseEndpoint('end');if(choice){this.setEndpoint('end',choice);this.record.dirty=true;this.o.endpoint?.('end',choice);await this.persist();}return choice;}
 async importStops(){
 if(this.o.readonly()||this.past()||active===this||!this.record?.ended)return;
 if(!this.o.importStops)throw Error(t(globalThis.CtlText.source("portal_gps.text_81cfd9b89bb2")));
 const selected=new Set(this.record.selection||[]);if(!selected.size)throw Error(t(globalThis.CtlText.source("portal_gps.text_ee5afc9962c8")));
 if(this.stationInputs.length)await this.choose(true);
 const rows=(this.analysis?.rows||[]).filter(row=>selected.has(row.key));const imported=await this.o.importStops(rows);if(imported!==false)this.say(globalThis.CtlText.source("portal_gps.text_a968519f656e"));
 }
 async start(){if(this.past())return;if(this.o.readonly()||active||manualActive)return;if(!window.AndroidPortal&&(!window.isSecureContext||!navigator.geolocation))throw Error(t(globalThis.CtlText.source("portal_gps.text_38fdca6391ba")));if(!/^[A-Za-z0-9]{1,12}$/.test(this.o.trainNumber().trim()))throw Error(t(globalThis.CtlText.source("portal_gps.text_b9009a6c1629")));
 if(this.record?.ended&&this.record.points.length&&!confirm(t(globalThis.CtlText.source("portal_gps.text_ba5568b6ce4d"))))return;
 if(!await this.prepareEndpoints())return;
 this.mapState={mode:'follow',zoom:this.mapState?.zoom||15};
 if(window.AndroidPortal){await this.nativeStart();return;}
 if(!this.record||this.record.ended)this.record={train_number:this.o.trainNumber().trim(),departure_applied:false,points:[],manual_stops:this.record?.manual_stops||[],stop_edits:Object.fromEntries(Object.entries(this.record?.stop_edits||{}).filter(([key])=>key.startsWith('manual-'))),detection_version:5,ended:false,revision:this.record?.revision||0,dirty:true};
 this.setEndpoint('start',this.startChoice);this.setEndpoint('end',this.endChoice);this.analysis=null;this.record.analysis=null;this.record.reasons={};this.record.reason_drafts={};active=this;try{await this.persist();}catch(error){this.clear();throw error;}await this.wake();this.timer=setInterval(()=>this.sample(),5000);this.sample();this.freeze();this.o.changed?.();
 }
 clear(){clearInterval(this.timer);clearInterval(this.nativeTimer);if(active===this)active=null;this.wakeLock?.release().catch(()=>{});}
 async stop(finalFix=true){if(!this.record||this.record.ended)return;if(window.AndroidPortal){await window.AndroidPortal.gps('stop',{key:this.key});await this.nativeRead();}if(active===this&&finalFix&&!window.AndroidPortal){clearInterval(this.timer);try{await this.add(await this.fix());}catch(error){this.say(globalThis.CtlText.source("portal_gps.text_df6a9e9a8721"));}}
 if(this.record.ended)return;
 this.applyDeparture();
 this.clear();
 this.record.ended=true;this.record.dirty=true;
 await this.persist();this.draw();
 if(!this.record.points.length){this.say(globalThis.CtlText.source("portal_gps.text_74a3cf033540"));return;}
 let noArrival=false;
 if(finalFix&&!this.o.readonly()){
  const destination=await this.chooseEnd();
  const arrival=lastMovement(this.record.points);
  if(destination&&arrival!==null&&this.o.journeyTime){
   const message=t(globalThis.CtlText.source("portal_gps.text_0ff345ca4d07"))
    .replace('{station}',()=>destination.name||destination.code)
    .replace('{time}',()=>stamp(arrival,this.record.points[0].t));
   if(confirm(message)){
    this.o.journeyTime('end',arrival);
    this.record.arrival_at=arrival;this.record.dirty=true;
    await this.persist();
   }
  }else if(destination&&arrival===null)noArrival=true;
 }
 try{await this.checkpointTask;if(navigator.onLine)await this.sync();}catch(error){this.say(globalThis.CtlText.source("portal_gps.text_05b6b4dee7bc"));return;}
 this.say(globalThis.CtlText.source(noArrival?"portal_gps.text_86d975e208e9":"portal_gps.text_f90390ecedc2"));
 }
 async sync(){if(!this.record||(!this.record.points?.length&&!this.record.manual_stops?.length))return;const reply=await api(this.path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({train_number:this.record.train_number,start_station:this.record.start_station||null,start_station_name:this.record.start_station_name||'',end_station_name:this.record.end_station_name||'',points:this.record.points,departure_applied:!!this.record.departure_applied,arrival_at:this.record.arrival_at||null,end_station:this.record.end_station||null,stop_edits:this.record.stop_edits||{},manual_stops:this.record.manual_stops||[],ended:this.record.ended,expected_revision:this.record.revision||0})});if(!reply)throw Error(t(globalThis.CtlText.source("portal_gps.text_03169f7c2fb3")));this.serverRecord=reply;this.record={...reply,dirty:false,reason_drafts:this.record?.reason_drafts||{},station_drafts:this.record?.station_drafts||{},selection:this.record?.selection??reply.selection??[]};this.analysis=reply.analysis;await this.persist();this.draw();this.say(globalThis.CtlText.source("portal_gps.text_d9d95ec8044f"));}
 async reload(){if((this.record?.dirty||Object.keys(this.record?.reason_drafts||{}).length||Object.keys(this.record?.station_drafts||{}).length)&&!confirm(t(globalThis.CtlText.source("portal_gps.text_49ea0b5fe962"))))return;const reply=await api(this.path);this.serverRecord=reply;if(!reply)throw Error(t(globalThis.CtlText.source("portal_gps.text_d425fe5589f1")));this.record={...reply,dirty:false,reason_drafts:{}};this.analysis=reply.analysis;await this.persist();this.draw();}
 async resolve(){if(this.record?.dirty)await this.sync();if(!this.record?.points.length)return;let reply;
 for(let i=0;i<=this.record.points.length;i++){reply=await api(this.path+'/stations',{method:'POST'});if(!reply)throw Error(t(globalThis.CtlText.source("portal_gps.text_d425fe5589f1")));this.analysis=reply.analysis;this.record={...reply,dirty:false,reason_drafts:this.record?.reason_drafts||{},station_drafts:this.record?.station_drafts||{},selection:this.record?.selection??reply.selection??[]};await this.persist();this.draw();const pending=reply.analysis.rows.filter(row=>row.lookup_pending).length;if(!pending)break;this.say(t(globalThis.CtlText.source("portal_gps.text_36442944a80a"))+' '+pending);await pause(2200);}
 this.say(globalThis.CtlText.source("portal_gps.text_78b9550c8d91"));}
 async choose(selectedOnly=false){
 const stations={...this.record.stations},reasons={...this.record.reasons},selection=this.record.selection||[],remainingReasons={...this.record.reason_drafts},remainingStations={...this.record.station_drafts};
 for(const {row,input,reason,detail} of this.stationInputs){
 if(selectedOnly&&!selection.includes(row.key))continue;
 if(input.value.trim())stations[row.key]=await this.o.resolve(input);else delete stations[row.key];
 if(reason.value===globalThis.CtlText.source("portal_gps.text_69384a6be550")&&!detail.value.trim())throw Error(t(globalThis.CtlText.source("portal_gps.text_58f91be54d8a")));
 reasons[row.key]={reason:reason.value,detail:detail.value.trim()};delete remainingReasons[row.key];delete remainingStations[row.key];
 }
 // Keep both station codes and free-text assignments when saving the selection.
 for(const key of Object.keys(stations))if(typeof stations[key]==='object')stations[key]=stations[key].code||{name:stations[key].name};
 const reply=await api(this.path+'/stations',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:this.record.revision,stations,reasons,selection})});
 this.record={...reply,dirty:false,reason_drafts:remainingReasons,station_drafts:remainingStations,selection};this.analysis=reply.analysis;await this.persist();this.draw();this.say(globalThis.CtlText.source("portal_gps.text_e237c9e516bb"));
 }

 export(){if(!this.record?.points.length)return;const points=this.record.points;let last=null,segments='',part='',interrupted=false;const point=p=>'<trkpt lat="'+p.lat+'" lon="'+p.lon+'"><time>'+new Date(p.t).toISOString()+'</time></trkpt>';const flush=()=>{if(part)segments+='<trkseg>'+part+'</trkseg>';part='';};for(const p of points){if(p.accuracy>50){flush();interrupted=true;continue;}if(last&&(interrupted||p.t-last.t>30000)){flush();segments+='<trkseg>'+point(last)+point(p)+'<extensions><lzt:estimated>true</lzt:estimated></extensions></trkseg>';}part+=point(p);last=p;interrupted=false;}flush();download(globalThis.CtlText.source("portal_gps.text_64f66e9ae5db")+this.record.train_number+'-'+new Date(points[0].t).toISOString().slice(0,10)+'.gpx','<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="LokZeitleiste" xmlns="http://www.topografix.com/GPX/1/1" xmlns:lzt="https://github.com/omueller369/LokZeitleiste/gps"><trk><name>'+this.record.train_number+'</name>'+segments+'</trk></gpx>','application/gpx+xml');}
 async erase(){if(active===this)throw Error(t(globalThis.CtlText.source("portal_gps.text_fe08e27c0231")));if(!confirm(t(globalThis.CtlText.source("portal_gps.text_f7fb397c1880"))))return;await api(this.path,{method:'DELETE'});await local(this.key,null);if(window.AndroidPortal)await window.AndroidPortal.gps('erase',{key:this.key});this.record=null;this.serverRecord=null;this.analysis=null;this.draw();this.say(globalThis.CtlText.source("portal_gps.text_09630f0c79e5"));}
 setupMap(){
 this.mapTools=node('div');this.mapTools.className='gps-map-tools';this.mapTools.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_fae9dd10ec93")));
 const control=(label,caption,action)=>{const b=node('button',label);b.type='button';b.title=t(caption);b.setAttribute('aria-label',t(caption));b.onclick=action;this.mapTools.append(b);return b;};
 this.mapZoomIn=control('+',globalThis.CtlText.source("portal_gps.text_809820ce88d5"),()=>this.mapZoom(1));this.mapZoomOut=control('−',globalThis.CtlText.source("portal_gps.text_914f3003d3a8"),()=>this.mapZoom(-1));
 this.mapZoomLevel=node('span');this.mapZoomLevel.className='gps-map-zoom';this.mapTools.append(this.mapZoomLevel);
 this.mapFollow=control(t(globalThis.CtlText.source("portal_gps.text_33ee562dc3d3")),globalThis.CtlText.source("portal_gps.text_e945e3bd7919"),()=>{this.mapState={mode:'follow',zoom:this.mapState?.zoom||15};this.drawMap();});
 this.mapOverview=control(t(globalThis.CtlText.source("portal_gps.text_b2dc8ee2fa59")),globalThis.CtlText.source("portal_gps.text_bc631a1b8308"),()=>{this.mapState={mode:'overview',zoom:this.mapState?.zoom||15};this.drawMap();});
 this.railEnabled=true;this.mapRail=control(t(globalThis.CtlText.source("portal_gps.text_da54ccd0ee5a")),globalThis.CtlText.source("portal_gps.text_272f99c19dbe"),()=>{this.railEnabled=!this.railEnabled;this.railFailed=false;this.drawMap();});
 this.mapPointers=new Map();const xy=e=>{const r=this.mapSvg?.getBoundingClientRect?.();return r?{x:(e.clientX-r.left)/r.width*600,y:(e.clientY-r.top)/r.height*300}:null;};
 const begin=()=>{if(!this.mapView)return;const ps=[...this.mapPointers.values()],v=this.mapView;this.mapGesture={points:ps.map(p=>({...p})),zoom:v.zoom,center:{...v.center},size:v.size};};
 this.map.addEventListener('pointerdown',e=>{if(e.target?.closest?.('button,a,[data-gps-stop]')||!this.mapView||e.pointerType==='mouse'&&e.button!==0)return;const p=xy(e);if(!p)return;e.preventDefault();this.map.setPointerCapture?.(e.pointerId);this.mapPointers.set(e.pointerId,p);begin();});
 this.map.addEventListener('pointermove',e=>{if(!this.mapPointers.has(e.pointerId))return;const p=xy(e);if(!p)return;e.preventDefault();this.mapPointers.set(e.pointerId,p);const g=this.mapGesture,ps=[...this.mapPointers.values()];if(!g||g.points.length!==ps.length){begin();return;}
 let zoom=g.zoom,center={...g.center};if(ps.length>=2){const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y),d0=distance(g.points[0],g.points[1]),d=distance(ps[0],ps[1]);if(d0<10||d<10)return;zoom=Math.max(2,Math.min(19,g.zoom+Math.round(Math.log2(d/d0))));const oldMid={x:(g.points[0].x+g.points[1].x)/2,y:(g.points[0].y+g.points[1].y)/2},mid={x:(ps[0].x+ps[1].x)/2,y:(ps[0].y+ps[1].y)/2},size=256*2**zoom;center={x:g.center.x+(oldMid.x-300)/g.size-(mid.x-300)/size,y:g.center.y+(oldMid.y-150)/g.size-(mid.y-150)/size};}else center={x:g.center.x+(g.points[0].x-ps[0].x)/g.size,y:g.center.y+(g.points[0].y-ps[0].y)/g.size};
 if(Math.abs(ps[0].x-g.points[0].x)+Math.abs(ps[0].y-g.points[0].y)<3&&ps.length===1)return;
 this.mapState={mode:'free',zoom,center:{x:Math.max(0,Math.min(1,center.x)),y:Math.max(0,Math.min(1,center.y))}};this.drawMap();});
 for(const type of ['pointerup','pointercancel','lostpointercapture'])this.map.addEventListener(type,e=>{this.mapPointers.delete(e.pointerId);begin();});
 }
 setFocusedStop(key,center=false){const row=this.rows().find(row=>row.source_keys.includes(key));key=row?.key||key;const same=this.focusedStopKey===key;if(same&&!center&&!this.content.hidden)return;this.focusedStopKey=key;
 if(row&&!row.manual&&!this.removed(row)){const wasHidden=this.content.hidden;if(wasHidden){this.content.hidden=false;this.updateCollapse();}const target=projectPoint(row);if(!wasHidden&&same&&this.mapState?.mode==='free'&&this.mapView?.zoom>=16&&this.mapView.center.x===target.x&&this.mapView.center.y===target.y)return;this.mapState={mode:'free',zoom:Math.min(19,Math.max(16,this.mapView?.zoom||this.mapState?.zoom||15)),center:projectPoint(row)};this.drawMap();return;}
 for(const marker of this.mapSvg?.children||[]){const stopKey=marker.getAttribute('data-gps-stop');if(!stopKey)continue;const selected=stopKey===key,position=marker.getAttribute('transform').replace(/ scale\([^)]*\)$/,'');marker.setAttribute('transform',position+globalThis.CtlText.source("portal_gps.text_7d14c715b37c")+(selected?2:1)+')');marker.setAttribute('aria-pressed',String(selected));}
 }
 focusStop(key){this.setFocusedStop(key,true);const input=this.liveInputs?.find(item=>item.row.key===key)?.station;if(input){input.scrollIntoView?.({behavior:'smooth',block:'center'});input.focus({preventScroll:true});input.setSelectionRange?.(input.value.length,input.value.length);}else {const row=this.rows().find(row=>row.source_keys.includes(key));this.o.focusImported?.(row?.source_keys.find(source=>this.o.hasImported?.(source))||key);}}
 drawPositionMarker(svg,make,x,y,point,totals){
 const marker=make('g');
 marker.setAttribute('data-gps-position','true');
 marker.setAttribute('transform','translate('+x+' '+y+')');
 marker.setAttribute('pointer-events','none');
 const append=(tag,attributes)=>{const element=make(tag);for(const [key,value] of Object.entries(attributes))element.setAttribute(key,value);marker.append(element);return element;};
 const label=(value,x,y,size=12,fill='#172338',anchor='middle')=>{
  append('text',{x,y,'text-anchor':anchor,'font-size':size,'font-weight':700,fill,stroke:'#fff','stroke-width':size>=20?4:2.5,'stroke-linejoin':'round','paint-order':'stroke'}).textContent=value;
 };
 const speed=Number.isFinite(point.speed)&&point.speed>=0?Math.round(point.speed*3.6)+' km/h':'–';
 label(speed,23,4,11,'#172338','start');
 label(durationLabel(totals.moving),-7,-25,12,'#146c34','end');
 label('/',0,-25);
 label(durationLabel(totals.stopped),7,-25,12,'#b42318','start');
 append('path',{d:'M -12 -9 L -5 -16 L 5 -12 L 12 -19 M 4 -19 H 17',fill:'none',stroke:'#172338','stroke-width':2.5,'stroke-linecap':'round'});
 append('path',{d:'M -19 6 V -3 L -15 -10 H 13 L 19 -3 V 6 L 15 10 H -15 Z',fill:'#1565c0',stroke:'#fff','stroke-width':2});
 append('path',{d:'M -14 -5 H -8 V 0 H -17 Z M 9 -5 H 13 L 17 0 H 9 Z',fill:'#fff'});
 append('path',{d:'M 2 -7 L -4 1 H 0 L -2 7 L 5 -2 H 1 Z',fill:'#ffe26d'});
 for(const cx of [-11,11])append('circle',{cx,cy:11,r:4,fill:'#172338',stroke:'#fff','stroke-width':1.5});
 label(this.record.train_number||this.o.trainNumber().trim(),0,34,20);
 svg.append(marker);
 }
 drawTrail(svg,make,display,position){
 const paths=new Map(),bridges=[];
 let last=null,interrupted=false;
 for(const point of display){
  if(point.accuracy>50){interrupted=true;continue;}
  const next=position(point);
  if(last){
   if(interrupted||point.t-last.t>30000)bridges.push([last,next]);
   else if(last.x!==next.x||last.y!==next.y){
    const color=speedColor(point.mapSpeed);
    const segment='M'+last.x.toFixed(1)+' '+last.y.toFixed(1)+'L'+next.x.toFixed(1)+' '+next.y.toFixed(1);
    if(!paths.has(color))paths.set(color,[]);
    paths.get(color).push(segment);
   }
  }
  interrupted=false;
  last={...next,t:point.t};
 }
 for(const [color,segments] of paths){
  const line=make('path');line.setAttribute('data-gps-trail','');line.setAttribute('d',segments.join(''));
  line.setAttribute('fill','none');line.setAttribute('stroke',color);line.setAttribute('stroke-width',3);
  line.setAttribute('stroke-linecap','round');svg.append(line);
 }
 for(const [a,b] of bridges){
  const bridge=make('line');
  for(const [key,value] of Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:unknownTrail,'stroke-width':2,'stroke-dasharray':'6 4'}))bridge.setAttribute(key,value);
  const title=make('title');title.textContent=t(globalThis.CtlText.source("portal_gps.text_8067c798e3d6"));
  bridge.append(title);svg.append(bridge);
 }
 }
 trailLegend(){
 const legend=node('div');legend.className='gps-trail-legend';legend.setAttribute('data-i18n-ignore','');
 legend.append(node('span',t(globalThis.CtlText.source("portal_gps.text_8af2c376113e"))));
 const scale=node('div');scale.className='gps-trail-scale';scale.setAttribute('style','--gps-trail-gradient:linear-gradient(90deg,'+
  trailScale.map(([speed,color])=>trailColor(color)+' '+speed/160*100+'%').join(',')+')');
 for(const [speed] of trailScale){
  const tick=node('span',speed===160?'160+':String(speed));
  tick.setAttribute('style','left:'+speed/160*100+'%');scale.append(tick);
 }
 legend.append(scale);
 return legend;
 }
 mapZoom(delta){if(!this.mapView)return;const zoom=Math.max(2,Math.min(19,this.mapView.zoom+delta)),mode=this.mapState?.mode==='follow'?'follow':'free';this.mapState={mode,zoom,center:this.mapView.center};this.drawMap();}
 drawMap(){
 this.map.replaceChildren();this.map.append(this.mapTools);const display=[],totals={moving:0,stopped:0};liveStops(this.record?.points||[],!!this.record?.ended,{},false,false,false,false,display,totals);const points=display.filter(p=>p.accuracy<=50);if(!points.length){this.mapSvg=null;this.mapView=null;this.mapZoomLevel.hidden=true;this.mapZoomIn.disabled=this.mapZoomOut.disabled=true;return;}
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg'),make=tag=>document.createElementNS(ns,tag);this.mapSvg=svg;svg.setAttribute('viewBox','0 0 600 300');svg.setAttribute('role','group');svg.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_f5976363df27")));
 const project=projectPoint;
 const coords=points.map(project),minX=Math.min(...coords.map(p=>p.x)),maxX=Math.max(...coords.map(p=>p.x)),minY=Math.min(...coords.map(p=>p.y)),maxY=Math.max(...coords.map(p=>p.y));
 if(!this.mapState)this.mapState={mode:this.record.ended?'overview':'follow',zoom:15};let zoom=this.mapState.zoom,center=this.mapState.center||coords.at(-1);
 if(this.mapState.mode==='overview'){zoom=15;while(zoom>2&&((maxX-minX)*256*2**zoom>540||(maxY-minY)*256*2**zoom>240))zoom--;center={x:(minX+maxX)/2,y:(minY+maxY)/2};}else if(this.mapState.mode==='follow')center=coords.at(-1);
 this.mapZoomLevel.hidden=false;
 this.mapZoomLevel.textContent=t(globalThis.CtlText.source("portal_gps.text_7afb2d86cd0c"))+' '+zoom;
 this.mapZoomLevel.setAttribute('data-i18n-ignore','');
 this.mapView={zoom,center,size:256*2**zoom};this.mapFollow.setAttribute('aria-pressed',String(this.mapState.mode==='follow'));this.mapOverview.setAttribute('aria-pressed',String(this.mapState.mode==='overview'));this.mapRail.setAttribute('aria-pressed',String(this.railEnabled&&!this.railFailed));this.mapZoomIn.disabled=zoom>=19;this.mapZoomOut.disabled=zoom<=2;
 const size=256*2**zoom,left=center.x*size-300,top=center.y*size-150,visible=!this.content.hidden&&document.visibilityState!=='hidden'&&!this.box.closest?.('[hidden]');
 if(visible&&navigator.onLine){const tiles=[];for(let x=Math.floor(left/256);x<=Math.floor((left+600)/256);x++)for(let y=Math.floor(top/256);y<=Math.floor((top+300)/256);y++){if(y<0||y>=2**zoom)continue;tiles.push({x,y});}
 const layer=(template,rail=false)=>{for(const {x,y}of tiles){const image=make('image');image.setAttribute('x',x*256-left);image.setAttribute('y',y*256-top);image.setAttribute('width',256);image.setAttribute('height',256);image.setAttribute('href',template.replace('{z}',zoom).replace('{x}',((x%2**zoom)+2**zoom)%2**zoom).replace('{y}',y));image.setAttribute('referrerpolicy','origin');if(rail)image.setAttribute('data-gps-rail','true');if(rail)image.addEventListener('error',()=>{if(this.railFailed)return;this.railFailed=true;this.drawMap();});svg.append(image);}};
 layer(window.GpsTileUrl||'https://tile.openstreetmap.org/{z}/{x}/{y}.png');if(this.railEnabled&&!this.railFailed)layer(window.GpsRailTileUrl||'https://tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png',true);}
 this.drawTrail(svg,make,display,p=>{const c=project(p);return {x:c.x*size-left,y:c.y*size-top};});
 const endpoints=[[0,'#008000']];if(this.record.ended)endpoints.push([coords.length-1,'#c40000']);
 for(const [i,color]of endpoints){const c=make('circle');c.setAttribute('cx',coords[i].x*size-left);c.setAttribute('cy',coords[i].y*size-top);c.setAttribute('r',5);c.setAttribute('fill',color);svg.append(c);}for(const row of this.rows().filter(row=>!row.manual&&!this.removed(row))){
 const p=project(row),marker=make('g');marker.setAttribute('data-gps-stop',row.key);marker.setAttribute('transform','translate('+(p.x*size-left)+' '+(p.y*size-top)+globalThis.CtlText.source("portal_gps.text_c436a7be64bc")+(this.focusedStopKey===row.key?2:1)+')');marker.setAttribute('aria-pressed',String(this.focusedStopKey===row.key));marker.setAttribute('role','button');marker.setAttribute('tabindex','0');marker.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_1a86455fdc47"))+' · '+stamp(row.start));marker.setAttribute('style','cursor:pointer');
 const dot=make('circle');dot.setAttribute('r',8);dot.setAttribute('fill','#1565c0');dot.setAttribute('stroke','#fff');dot.setAttribute('stroke-width',2);const half=make('path');half.setAttribute('d','M 0 -7 A 7 7 0 0 1 0 7 Z');half.setAttribute('fill','#d00000');half.setAttribute('pointer-events','none');const title=make('title');title.textContent=t(globalThis.CtlText.source("portal_gps.text_1a86455fdc47"))+' · '+stamp(row.start);marker.append(dot,half,title);
 marker.addEventListener('click',()=>this.focusStop(row.key));marker.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();this.focusStop(row.key);}});svg.append(marker);
 }
 if(!this.record.ended){const position=coords.at(-1);this.drawPositionMarker(svg,make,position.x*size-left,position.y*size-top,points.at(-1),totals);}
 this.map.append(svg,this.trailLegend());
 const link=(label,url)=>{const a=node('a',label);a.href=url;a.target='_blank';a.rel='noopener';return a;};this.map.append(link(globalThis.CtlText.source("portal_gps.text_f834e3bb911e"),'https://www.openstreetmap.org/copyright'));if(this.railEnabled)this.map.append(link('OpenRailwayMap','https://www.openrailwaymap.org/'),link('CC-BY-SA 2.0','https://creativecommons.org/licenses/by-sa/2.0/'));
 this.map.append(node('small',t(this.mapState.mode==='follow'?globalThis.CtlText.source("portal_gps.text_b2b3a3f2bec3"):globalThis.CtlText.source("portal_gps.text_8e02679954f1"))));if(this.railFailed)this.map.append(node('small',t(globalThis.CtlText.source("portal_gps.text_f1b2882182df"))));
 }

 draw(){normaliseRecording(this.record);if(this.liveInputs?.some(row=>[row.tr,row.station,row.reason,row.detail,row.end,row.take,row.remove].includes(document.activeElement))){const rows=this.rows().filter(row=>!this.imported(row)&&!this.removed(row));for(const input of this.liveInputs){const current=rows.find(row=>row.key===input.row.key);if(current){Object.assign(input.row,current);if(current.end&&!this.record.stop_edits?.[current.key]?.manual_end)input.end.value=clock(current.end);}}if(rows.map(row=>row.key).join()===this.liveInputs.map(input=>input.row.key).join()){this.drawMap();this.freeze();return;}}this.drawMap();this.results.replaceChildren();this.stationInputs=[];this.drawStops();this.freeze();}
 async checkpoint(){
 if(this.checkpointTask)return this.checkpointTask;
 this.checkpointTask=(async()=>{if(active===this&&window.AndroidPortal)await this.nativeRead();await this.persist();if(!this.record||(!this.record.points?.length&&!this.record.manual_stops?.length)||navigator.onLine===false)return false;
 const record=this.record,snapshot=JSON.parse(JSON.stringify(record));
 try{const reply=await api(this.path,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({train_number:snapshot.train_number,start_station:snapshot.start_station||null,start_station_name:snapshot.start_station_name||'',end_station_name:snapshot.end_station_name||'',end_station:snapshot.end_station||null,points:snapshot.points,departure_applied:!!snapshot.departure_applied,arrival_at:snapshot.arrival_at||null,ended:snapshot.ended,stop_edits:snapshot.stop_edits||{},manual_stops:snapshot.manual_stops||[],expected_revision:snapshot.revision||0})});
 if(!reply) return false;this.serverRecord=reply;if(this.record===record){record.revision=reply.revision;record.dirty=['start_station','end_station','start_station_name','end_station_name','ended','departure_applied','arrival_at'].some(key=>record[key]!==snapshot[key])||JSON.stringify(record.points)!==JSON.stringify(snapshot.points)||JSON.stringify(record.stop_edits||{})!==JSON.stringify(snapshot.stop_edits||{})||JSON.stringify(record.manual_stops||[])!==JSON.stringify(snapshot.manual_stops||[]);await this.persist();}return true;
 }catch(error){if(error.status===409)throw error;return false;}})();try{return await this.checkpointTask;}finally{this.checkpointTask=null;}
 }
 async discard(){if(window.AndroidPortal)await window.AndroidPortal.gps('stop',{key:this.key});this.clear();this.clearManual();await local(this.key,null);this.record=null;this.analysis=null;this.draw();}
 drawStops(){
 if(!this.record)return;const stops=this.rows().filter(row=>!this.imported(row)&&!this.removed(row));
 this.results.append(node('h4',t(globalThis.CtlText.source("portal_gps.text_e461aed646b6"))));this.liveInputs=[];
 if(!stops.length){this.results.append(node('p',t(globalThis.CtlText.source("portal_gps.text_280e8fae6dfe"))));return;}
 const table=node('table');table.className='excel';const head=node('tr');for(const value of [globalThis.CtlText.source("portal_gps.text_792751a9dcdb"),globalThis.CtlText.source("portal_gps.text_640e86cbc244"),globalThis.CtlText.source("portal_gps.text_078a815372af"),globalThis.CtlText.source("portal_gps.text_b45f40c737c3"),globalThis.CtlText.source("portal_gps.text_936378b371b9"),globalThis.CtlText.source("portal_gps.text_6c2d352161df")])head.append(node('th',t(value)));table.append(head);
 for(const row of stops){const old=this.analysis?.rows?.find(item=>item.kind===globalThis.CtlText.source("portal_gps.text_0fd998791d67")&&item.start===row.start),legacy=this.record.locations?.[String(row.start)]||old?.station,draft=row.source_keys.map(key=>this.record.stop_edits?.[key]).find(Boolean)||(legacy?{station:legacy,station_input:(legacy.code?legacy.code+' · ':'')+legacy.name,reason:old?.reason?.reason||'',detail:old?.reason?.detail||''}:{}),tr=node('tr'),station=node('input'),list=node('datalist'),reason=node('select'),detail=node('input'),end=node('input'),take=node('button',t(globalThis.CtlText.source("portal_gps.text_8956021eae0e"))),remove=node('button',t(globalThis.CtlText.source("portal_gps.text_6c2d352161df")));
 station.maxLength=270;station.value=draft.station_input??(draft.station?placeLabel(draft.station):'');station.placeholder=t(globalThis.CtlText.source("portal_gps.text_3ac37da56214"));station.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_792751a9dcdb")));list.id='gps-live-'+this.o.journeyId+'-'+row.key;station.setAttribute('list',list.id);this.o.stations(station,list);
 const empty=node('option',t(globalThis.CtlText.source("portal_gps.text_4112179c8995")));empty.value='';reason.append(empty);for(const value of window.TrainJourneyReasons||[]){const option=node('option',t(window.TrainJourneyReasonLabel?.(value)||value));option.value=value;reason.append(option);}reason.value=draft.reason||'';reason.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_820c55eb8960")));detail.maxLength=256;detail.value=draft.detail||'';detail.placeholder=t(globalThis.CtlText.source("portal_gps.text_d2373f70bb27"));detail.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_e73e1be46ebb")));
 let endTouched=false,editedEnd=null;const previousEnd=()=>draft.manual_end&&draft.end?draft.end:row.end;const endTime=()=>endTouched?editedEnd:!end.value?null:!endTouched&&previousEnd()&&end.value===clock(previousEnd())?previousEnd():stopEnd(row,end.value,previousEnd());
 end.type='time';end.step='60';end.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_ea90c8a580d4")));end.value=previousEnd()?clock(previousEnd()):'';take.type='button';take.title=t(globalThis.CtlText.source("portal_gps.text_6781a6571713"));take.disabled=this.o.readonly();
 const remember=()=>{this.record.stop_edits||={};this.record.stop_edits[row.key]={...this.record.stop_edits[row.key],station_input:station.value,station:draft.station&&station.value===placeLabel(draft.station)?draft.station:null,reason:reason.value,detail:detail.value,end:endTime(),manual_end:endTouched||!!draft.manual_end,imported:false};this.record.dirty=true;this.persist().catch(error=>this.fail(error.message));};
 tr.tabIndex=0;tr.onclick=event=>{if(!event.target?.closest?.('button,details,summary'))this.setFocusedStop(row.key,true);};tr.addEventListener('focusin',()=>this.setFocusedStop(row.key));tr.addEventListener('focusout',event=>{if(!tr.contains(event.relatedTarget))this.setFocusedStop(null);});
 station.oninput=remember;reason.onchange=remember;detail.oninput=()=>{if(detail.value.trim())reason.value=globalThis.CtlText.source("portal_gps.text_69384a6be550");remember();};end.oninput=()=>{editedEnd=stopEnd(row,end.value,editedEnd||previousEnd());endTouched=true;remember();};
 take.onclick=async()=>{if(this.o.readonly())return;take.disabled=true;try{const until=endTime();if(!until||until<=row.start)throw Error(t(globalThis.CtlText.source("portal_gps.text_3469ecb39054")));if(!reason.value)throw Error(t(globalThis.CtlText.source("portal_gps.text_f2df21cce73d")));if(reason.value===globalThis.CtlText.source("portal_gps.text_69384a6be550")&&!detail.value.trim())throw Error(t(globalThis.CtlText.source("portal_gps.text_58f91be54d8a")));const choice=draft.station&&station.value===placeLabel(draft.station)?draft.station:await this.o.resolve(station);const imported=await this.o.importStops([{...row,end:until,station:choice,reason:{reason:reason.value,detail:reason.value===globalThis.CtlText.source("portal_gps.text_69384a6be550")?detail.value.trim():'',label:window.TrainJourneyReasonLabel?.(reason.value)||reason.value}}]);if(imported===false)return;
 this.record.stop_edits||={};this.record.stop_edits[row.key]={station_input:placeLabel(choice),station:choice,reason:reason.value,detail:detail.value,end:until,manual_end:endTouched||!!draft.manual_end,imported:true};this.record.dirty=true;await this.persist();this.draw();}catch(error){this.fail(error.message);}finally{take.disabled=this.o.readonly();}};
 remove.type='button';remove.setAttribute('aria-label',t(globalThis.CtlText.source("portal_gps.text_ee3fb0eb114c"))+' · '+stamp(row.start));remove.onclick=()=>this.run(()=>this.deleteStop(row));
 const history=node('details'),historyRows=row.source_keys.map(key=>({key,edit:this.record.stop_edits?.[key]})).filter(item=>item.edit);if(historyRows.length>1){history.append(node('summary',t(globalThis.CtlText.source("portal_gps.text_557314f9ed76"))));for(const {key,edit}of historyRows)history.append(node('p',stamp(Number(key.slice(5)))+' · '+(edit.station_input||edit.station?.name||'')+' · '+(edit.reason||'')+(edit.detail?' · '+edit.detail:'')));}history.hidden=historyRows.length<2;
 for(const elements of [[station,list,history],[node('span',stamp(row.start))],[end],[reason,detail],[take],[remove]]){const td=node('td');td.append(...elements);tr.append(td);}table.append(tr);this.liveInputs.push({row,tr,station,reason,detail,end,take,remove});
 }
 this.results.append(table);
 }

}
window.GpsRecorder={liveStops,firstDeparture,berlinTime,berlinInput,removeLocal:(userId,journeyId)=>local(userId+'.'+journeyId,null),mount:options=>new Recorder(options),isActive:()=>!!(active||manualActive),activeFor:id=>active?.o.journeyId===id||manualActive?.o.journeyId===id};
window.addEventListener('pagehide',()=>{active?.persist().catch(()=>{});manualActive?.persist().catch(()=>{});});
})();
