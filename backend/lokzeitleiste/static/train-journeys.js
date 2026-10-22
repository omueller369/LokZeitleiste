(()=>{
const REASONS=['V1','V3','A1','A1A','A3','Pause','Rangieren','Zugvorbereitung','BrP','vBrP','Zugfolge','Warten auf Zug','Warten auf Fpl','Warten auf FPLO','Lok defekt','sonstiges'];
window.TrainJourneyReasons=Object.freeze(REASONS);
const CAUSES=['CTL','DB InfraGo','Dritte Stelle','sonstiges'];
const node=(tag,value)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=value;return n;};
const t=value=>window.I18n?.t(value)||value;
const labelStation=(code,name)=>name?code+' · '+name:code;
const stationParts=value=>{const parts=value.trim().split(' · ');return {code:parts[0],name:parts.slice(1).join(' · ')};};
window.ReportTableTime=(value,start,end,previous=start)=>{if(!value)return '';const day=value.slice(0,10),time=value.slice(11,16);return start&&end&&start.slice(0,10)!==end.slice(0,10)&&day!==(previous||start).slice(0,10)?day.split('-').reverse().join('.')+' · '+time:time;};
const causeLabel=value=>value==='CTL Logistics DE'?'CTL':value;
window.TrainJourneyEditor=class{
 constructor(options){
  this.o=options;this.stationCache=new Map();this.items=[];this.active=null;
  this.tabs=node('div');this.tabs.className='train-tabs';this.tabs.setAttribute('role','tablist');this.tabs.setAttribute('aria-label','Zugfahrten');
  this.panels=node('div');this.summary=node('p');this.summary.id='trainPauseSummary';
  this.bar=node('div');this.bar.className='train-tab-bar';this.bar.append(this.tabs);options.container.append(this.bar,this.panels,this.summary);
  options.button.onclick=()=>{try{this.add();}catch(error){this.o.message(error.message);}};
  window.addEventListener('languagechange',()=>{this.refreshTabs();this.items.forEach(item=>this.table(item));this.pauseSummary();});
 }
 add(){
  if(this.o.readonly())return;
  if(this.items.length>=50){this.o.message('Höchstens 50 Zugfahrten pro Bericht.');return;}
  const start=this.o.bounds().start;
  const end=this.after(start,60);
  const item=this.make({id:this.o.uuid(),train_number:'',start_at:start,end_at:end,events:[]});
  this.items.push(item);this.activate(item.id);this.changed();item.fields.train_number.focus();
 }
 after(value,n){const minute=this.o.minute(value);return Number.isFinite(minute)?new Date((minute+n)*60000).toISOString().slice(0,16):'';}
 field(parent,title,type='text',extra={}){
  const label=node('label'),caption=node('span',title),input=node('input');input.type=type;Object.assign(input,extra);if(type==='datetime-local')input.title='Uhrzeiten in 5-Minuten-Schritten';const full=({'StartBf':'Startbahnhof (DS100 oder Bahnhofsname)','ZielBf':'Endbahnhof (DS100 oder Bahnhofsname)','Meldestelle/Ort':'Ort (DS100 oder Bahnhofsname)'})[title];if(full){label.title=full;input.setAttribute('aria-label',full);}label.append(caption,input);parent.append(label);return input;
 }
 station(parent,title,value){
  const input=this.field(parent,title,'text',{required:true,maxLength:270,autocomplete:'off'}),list=node('datalist');list.id='train-station-'+this.o.uuid();input.setAttribute('list',list.id);parent.append(list);input.value=value||'';this.o.stations(input,list);return input;
 }
 select(parent,title,values){
  const label=node('label'),select=node('select');select.required=true;const placeholder=node('option','Bitte wählen');placeholder.value='';select.append(placeholder);
  for(const value of values){const option=node('option',value==='Pause'?'Pause (Pausenzeit dokumentieren)':value);option.value=value;select.append(option);}label.append(node('span',title),select);parent.append(label);return select;
 }
 make(data){
  this.cacheStation(data.start_station,data.start_station_name);this.cacheStation(data.end_station,data.end_station_name);for(const event of data.events||[])this.cacheStation(event.station,event.station_name);
  const item={id:data.id,events:(data.events||[]).map(e=>({...e,cause:causeLabel(e.cause)})),editing:null};
  item.panel=node('section');item.panel.className='train-panel';item.panel.id='train-panel-'+data.id;item.panel.setAttribute('role','tabpanel');
  item.tab=node('button');item.tab.type='button';item.tab.id='train-tab-'+data.id;item.tab.setAttribute('role','tab');item.tab.setAttribute('aria-controls',item.panel.id);item.panel.setAttribute('aria-labelledby',item.tab.id);
  item.tab.onclick=()=>this.activate(item.id);
  item.tab.onkeydown=event=>{let i=this.items.indexOf(item);if(event.key==='ArrowRight')i=(i+1)%this.items.length;else if(event.key==='ArrowLeft')i=(i+this.items.length-1)%this.items.length;else if(event.key==='Home')i=0;else if(event.key==='End')i=this.items.length-1;else return;event.preventDefault();this.activate(this.items[i].id);this.items[i].tab.focus();};
  item.header=node('form');item.header.onsubmit=event=>event.preventDefault();item.headerSet=node('fieldset');item.headerSet.append(node('legend','Zugdaten'));const grid=node('div');grid.className='report-grid train-data-grid';
  const fields=item.fields={};fields.train_number=this.field(grid,'Zugnummer','text',{required:true,maxLength:12,size:12});fields.train_number.value=data.train_number||'';
  fields.start_station=this.station(grid,'StartBf',labelStation(data.start_station||'',data.start_station_name));
  fields.start_at=this.field(grid,'Abfahrt','datetime-local',{required:true,step:'300'});fields.start_at.value=(data.start_at||'').slice(0,16);
  fields.end_station=this.station(grid,'ZielBf',labelStation(data.end_station||'',data.end_station_name));
  fields.end_at=this.field(grid,'Ankunft','datetime-local',{required:true,step:'300'});fields.end_at.value=(data.end_at||'').slice(0,16);
  for(const [name,cls] of Object.entries({train_number:'train-number',start_station:'train-start-station',start_at:'train-departure',end_station:'train-end-station',end_at:'train-arrival'}))fields[name].parentElement.classList.add(cls);
  item.autoStart=fields.start_at.value===this.o.bounds().start;item.autoEnd=fields.end_at.value===this.after(fields.start_at.value,60);item.lastStart=fields.start_at.value;
  item.headerSet.append(grid);item.header.append(item.headerSet);item.panel.append(item.header);
  item.gps=window.GpsRecorder?.mount({userId:this.o.userId,journeyId:item.id,container:item.panel,numberField:fields.train_number,trainNumber:()=>fields.train_number.value,readonly:()=>this.o.readonly(),stations:this.o.stations,resolve:this.o.resolve});
  for(const [name,field] of Object.entries(fields)){field.dataset.field=name;field.addEventListener('input',()=>{if(name==='start_at'){item.autoStart=false;if(item.autoEnd)fields.end_at.value=this.after(fields.start_at.value,60);item.lastStart=fields.start_at.value;}if(name==='end_at')item.autoEnd=fields.end_at.value===this.after(fields.start_at.value,60);item.gps?.freeze();this.ready(item);this.table(item);this.changed();this.refreshTabs();});}
  item.form=node('form');item.eventSet=node('fieldset');item.eventSet.append(node('legend','Zugfahrt'));item.ctlPause=node('button','CTL Pause');item.ctlPause.type='button';item.ctlPause.onclick=()=>{if(this.o.readonly())return;this.clearEvent(item);item.eventFields.reason.value='Pause';item.eventFields.cause.value='CTL';this.details(item);item.eventFields.start_at.focus();};item.eventSet.append(item.ctlPause);const eventGrid=node('div');eventGrid.className='report-grid train-event-grid';const f=item.eventFields={};
  f.cause=this.select(eventGrid,'Art',CAUSES);
  f.reason=this.select(eventGrid,'Grund',REASONS);
  f.cause_detail=this.field(eventGrid,'Sonstige Art (max. 50 Zeichen)','text',{maxLength:50});
  f.reason_detail=this.field(eventGrid,'Sonstiger Grund (max. 256 Zeichen)','text',{maxLength:256});
  f.station=this.station(eventGrid,'Meldestelle/Ort','');
  f.start_at=this.field(eventGrid,'Von','datetime-local',{required:true,step:'300'});f.end_at=this.field(eventGrid,'Bis','datetime-local',{required:true,step:'300'});
  for(const [name,field] of Object.entries(f))field.parentElement.classList.add('event-'+name);
  f.start_at.oninput=()=>{if(!f.end_at.value||f.end_at.value===this.after(f.start_at.dataset.previous,15)||this.o.minute(f.end_at.value)<=this.o.minute(f.start_at.value))f.end_at.value=this.after(f.start_at.value,15);f.start_at.dataset.previous=f.start_at.value;f.end_at.min=f.start_at.value;};
  for(const [name,field] of Object.entries(f)){field.dataset.field=name;for(const type of ['input','change'])field.addEventListener(type,()=>{if(item.cancel)item.cancel.hidden=!this.pendingEvent(item);});}
  f.reason.onchange=()=>this.details(item);f.cause.onchange=()=>this.details(item);
  item.submit=node('button','Eintragen');item.submit.type='submit';item.cancel=node('button','Bearbeitung abbrechen');item.cancel.type='button';item.cancel.onclick=()=>this.clearEvent(item);
  item.deleteEvent=node('button','Eintrag entfernen');item.deleteEvent.type='button';item.deleteEvent.onclick=()=>{if(this.o.readonly()||!item.editing)return;if(!confirm('Eintrag entfernen?'))return;item.events=item.events.filter(e=>e.id!==item.editing);this.clearEvent(item);this.changed();};item.eventSet.append(eventGrid,item.submit,item.cancel,item.deleteEvent);item.form.append(item.eventSet);item.form.onsubmit=event=>{event.preventDefault();this.insert(item).catch(error=>this.o.message(error.message));};item.panel.append(item.form);
  const scroll=node('div');scroll.className='excel-scroll';item.eventTable=scroll;const table=node('table');table.className='excel train-event-table';const head=node('thead'),row=node('tr');
  for(const caption of ['Zugnummer','Startbahnhof','Abfahrt','Endbahnhof','Ankunft','Art','Grund','Meldestelle/Ort','Von','Bis','Dauer','Pausenzeit']){const short=({'Zugnummer':'Zug-Nr.','Startbahnhof':'Startbf.','Endbahnhof':'Endbf.','Verursacher':'Verurs.','Pausenzeit':'Pause'})[caption]||caption;const cell=node('th',short);cell.title=caption;cell.setAttribute('aria-label',caption);row.append(cell);}head.append(row);item.rows=node('tbody');table.append(head,item.rows);scroll.append(table);item.panel.append(scroll);
  item.remove=node('button','Zugfahrt entfernen');item.remove.type='button';item.remove.onclick=()=>{if(this.o.readonly())return;if(window.GpsRecorder?.activeFor(item.id)){this.o.message('Bitte zuerst die GPS-Aufzeichnung beenden.');return;}if(item.gps?.record?.points?.length){this.o.message('Bitte die GPS-Aufzeichnung vor dem Entfernen der Zugfahrt löschen.');return;}if(!confirm('Zugfahrt und ihre Einträge entfernen?'))return;this.items=this.items.filter(x=>x!==item);item.panel.remove();item.tab.remove();this.activate(this.items[0]?.id);this.changed();};item.panel.append(item.remove);
  this.tabs.append(item.tab);this.panels.append(item.panel);this.clearEvent(item);this.table(item);this.ready(item);return item;
 }
 details(item){const f=item.eventFields;const ctl=f.reason.value==='Pause'&&f.cause.value==='CTL';f.station.required=!ctl;f.station.parentElement.hidden=ctl;if(ctl)f.station.value='';for(const [name,detail] of [['reason','reason_detail'],['cause','cause_detail']]){const visible=f[name].value==='sonstiges';f[detail].parentElement.hidden=!visible;f[detail].required=visible;if(!visible)f[detail].value='';}if(item.cancel)item.cancel.hidden=!this.pendingEvent(item);}
 previousEnd(item){const index=this.items.indexOf(item),previous=index<0?this.items.at(-1):this.items[index-1];return previous?.events.at(-1)?.end_at;}
 refreshSuggestions(){for(const item of this.items)if(!item.events.length&&!this.pendingEvent(item))this.clearEvent(item);}
 clearEvent(item,nextStart){
  item.editing=null;item.form.reset();for(const f of Object.values(item.eventFields))f.value='';
  const f=item.eventFields,bounds=this.o.bounds(),start=(nextStart||item.events.at(-1)?.end_at||this.previousEnd(item)||bounds.start||'').slice(0,16),end=this.after(start,15);
  f.start_at.value=start;f.end_at.value=end;item.suggestedTimes={start_at:start,end_at:end};f.start_at.dataset.previous=start;f.end_at.min=start;
  item.submit.textContent='Eintragen';item.cancel.hidden=true;item.deleteEvent.hidden=true;this.details(item);this.table(item);
 }
 ready(item){const f=item.fields,number=f.train_number.value.trim(),complete=!!(number&&[...number].length<=12&&/^[\p{L}\p{N}]+$/u.test(number)&&f.start_station.value.trim()&&f.end_station.value.trim()&&Number.isFinite(this.o.minute(f.start_at.value))&&this.o.minute(f.end_at.value)>this.o.minute(f.start_at.value));item.form.hidden=!complete;item.eventTable.hidden=!complete;}
 dutyChanged(){if(this.o.readonly())return;const bounds=this.o.bounds(),start=bounds.start;for(const item of this.items){if(item.autoStart){item.fields.start_at.value=start;item.lastStart=start;if(item.autoEnd)item.fields.end_at.value=this.after(start,60);}if(!item.events.length&&!this.pendingEvent(item))this.clearEvent(item);this.ready(item);this.table(item);}this.changed();}
 activate(id){this.active=id;this.refreshTabs();}
 refreshTabs(){this.bar.hidden=!this.items.length;if(this.items.length)this.bar.append(this.o.button);else this.o.container.before(this.o.button);for(const [i,item] of this.items.entries()){item.tab.textContent=t('Zugfahrt')+' '+(i+1)+(item.fields.train_number.value?' · '+item.fields.train_number.value:'');item.tab.setAttribute('data-i18n-ignore','');const selected=item.id===this.active;item.tab.setAttribute('aria-selected',String(selected));item.tab.tabIndex=selected?0:-1;item.panel.hidden=!selected;}this.freeze();}
 table(item){
  item.rows.replaceChildren();const f=item.fields,bounds=this.o.bounds();let previous=bounds.start;const stamp=(value,prior)=>window.ReportTableTime(value,bounds.start,bounds.end,prior);
  for(const event of item.events){const row=node('tr');row.tabIndex=0;row.classList.toggle('selected',item.editing===event.id);const n=this.o.minute(event.end_at)-this.o.minute(event.start_at),reason=t(event.reason)+(event.reason==='sonstiges'?' · '+event.reason_detail:''),cause=t(event.cause)+(event.cause==='sonstiges'?' · '+event.cause_detail:'');
   for(const value of [f.train_number.value,f.start_station.value,stamp(f.start_at.value),f.end_station.value,stamp(f.end_at.value,f.start_at.value),cause,reason,labelStation(event.station,event.station_name),stamp(event.start_at,previous),stamp(event.end_at,event.start_at),this.o.clock(n),this.o.clock(event.reason==='Pause'?n:0)]){const cell=node('td',value);cell.setAttribute('data-i18n-ignore','');row.append(cell);}
   previous=event.end_at;
   const load=()=>{if(this.o.readonly())return;item.editing=event.id;if(!CAUSES.includes(event.cause)&&![...item.eventFields.cause.options].some(o=>o.value===event.cause)){const legacy=node('option',event.cause);legacy.value=event.cause;legacy.disabled=true;item.eventFields.cause.append(legacy);}for(const name of ['reason','reason_detail','cause','cause_detail','start_at','end_at'])item.eventFields[name].value=(event[name]||'').toString().slice(0,name.endsWith('_at')?16:undefined);item.eventFields.station.value=labelStation(event.station,event.station_name);item.eventFields.start_at.dataset.previous=item.eventFields.start_at.value;item.eventFields.end_at.min=item.eventFields.start_at.value;this.details(item);item.submit.textContent='Speichern';item.cancel.hidden=false;item.deleteEvent.hidden=false;this.table(item);item.form.scrollIntoView?.({behavior:'smooth',block:'nearest'});};row.onclick=load;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();load();}};item.rows.append(row);
  }
 }
 draft(){return this.items.map(item=>{const f=item.fields,a=stationParts(f.start_station.value),b=stationParts(f.end_station.value);return {id:item.id,train_number:f.train_number.value.trim(),start_station:a.code,start_station_name:a.name,start_at:f.start_at.value,end_station:b.code,end_station_name:b.name,end_at:f.end_at.value,events:item.events.map(e=>({...e}))};});}
 pauseMinutes(){return this.items.reduce((n,item)=>n+item.events.reduce((a,e)=>a+(e.reason==='Pause'?this.o.minute(e.end_at)-this.o.minute(e.start_at):0),0),0);}
 pauseSummary(){this.summary.textContent=t('Pausen aus Zugfahrten')+': '+this.o.clock(this.pauseMinutes());this.summary.setAttribute('data-i18n-ignore','');}
 changed(){this.refreshSuggestions();this.pauseSummary();this.o.changed(this.draft());}
 restore(data){this.items=[];this.active=null;this.tabs.replaceChildren();this.panels.replaceChildren();for(const train of data||[])this.items.push(this.make(train));this.activate(this.items[0]?.id);this.pauseSummary();}
 freeze(){const disabled=this.o.readonly();this.o.button.disabled=disabled;for(const item of this.items){item.headerSet.disabled=disabled;item.eventSet.disabled=disabled;item.remove.disabled=disabled;item.gps?.freeze();}}
 checkRange(start,end){const a=this.o.minute(start),b=this.o.minute(end),bounds=this.o.bounds();if(!Number.isFinite(a)||!Number.isFinite(b)||b<=a)throw Error('Bis muss nach Von liegen.');if(a%5||b%5)throw Error('Uhrzeiten in 5-Minuten-Schritten');if(a<this.o.minute(bounds.start)||b>this.o.minute(bounds.end))throw Error('Zugfahrten und Ereignisse müssen innerhalb des Dienstes liegen.');}
 cacheStation(code,name){if(code&&name)this.stationCache.set(code.toUpperCase(),{code,name});}
 async resolve(field){try{const station=await this.o.resolve(field);this.cacheStation(station.code,station.name);return station;}catch(error){const station=this.stationCache.get(stationParts(field.value).code.toUpperCase());if(!station)throw error;field.value=labelStation(station.code,station.name);return station;}}
 async header(item){const f=item.fields,number=f.train_number.value.trim();if(!number||[...number].length>12||!/^[\p{L}\p{N}]+$/u.test(number))throw Error('Zugnummer: nur Buchstaben und Zahlen, maximal zwölf Zeichen.');if(!item.header.reportValidity())throw Error('Bitte die Zugdaten vollständig in 5-Minuten-Schritten eingeben.');this.checkRange(f.start_at.value,f.end_at.value);await this.resolve(f.start_station);await this.resolve(f.end_station);}
 pendingEvent(item){if(item.editing)return true;return Object.entries(item.eventFields).some(([name,field])=>field.value.trim()!==(item.suggestedTimes?.[name]||''));}
 hasPending(){return this.items.some(item=>this.pendingEvent(item));}
 async validate(){for(const item of this.items){if(this.pendingEvent(item))throw Error('Bitte das Ereignis zuerst eintragen oder die Bearbeitung abbrechen.');await this.header(item);for(const event of item.events)this.checkRange(event.start_at,event.end_at);}this.changed();return this.draft();}
 async insert(item){
  if(this.o.readonly()||!item.form.reportValidity())return;
  this.o.block(true);
  try{await this.header(item);const f=item.eventFields;if(!REASONS.includes(f.reason.value)||!CAUSES.includes(f.cause.value))throw Error('Bitte Grund und Art auswählen.');this.checkRange(f.start_at.value,f.end_at.value);const station=f.reason.value==='Pause'&&f.cause.value==='CTL'?{code:'',name:''}:await this.resolve(f.station);
   if(f.reason.value==='sonstiges'&&(!f.reason_detail.value.trim()||f.reason_detail.value.length>256))throw Error('Sonstigen Grund bitte beschreiben.');if(f.cause.value==='sonstiges'&&(!f.cause_detail.value.trim()||f.cause_detail.value.length>50))throw Error('Sonstige Art bitte beschreiben.');
   const event={id:item.editing||this.o.uuid(),reason:f.reason.value,reason_detail:f.reason.value==='sonstiges'?f.reason_detail.value.trim():'',cause:f.cause.value,cause_detail:f.cause.value==='sonstiges'?f.cause_detail.value.trim():'',station:station.code,station_name:station.name,start_at:f.start_at.value,end_at:f.end_at.value};
   const all=this.items.flatMap(train=>train.events.filter(e=>e.id!==event.id));if(event.reason==='Pause'&&all.some(e=>e.reason==='Pause'&&this.o.minute(event.start_at)<this.o.minute(e.end_at)&&this.o.minute(event.end_at)>this.o.minute(e.start_at)))throw Error('Dokumentierte Pausen dürfen sich nicht überschneiden.');
   if(item.editing)item.events=item.events.map(e=>e.id===item.editing?event:e);else{if(item.events.length>=500)throw Error('Höchstens 500 Ereignisse pro Zugfahrt.');item.events.push(event);}this.clearEvent(item,event.end_at);this.changed();this.o.message('');
  }catch(error){this.o.message(error.message);}finally{this.o.block(false);}
 }
};
})();
