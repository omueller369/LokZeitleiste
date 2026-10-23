const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{constructor(tag='div',value=''){this.tag=tag;this.value=value;this.textContent='';this.children=[];this.dataset={};this.hidden=false;this.disabled=false;this.files=[];}append(...nodes){this.children.push(...nodes);}replaceChildren(...nodes){this.children=[...nodes];}reset(){}focus(){}reportValidity(){return true;}}
const ids=['protocolMessage','protocolEditor','protocolDetail','handoverNew','protocolRows','protocolDetailTitle','protocolData','protocolDownloads','protocolForm','protocolStations','protocolCount','protocolVehicle','protocolTime','protocolTimeLabel','protocolRecipient','protocolSave','protocolCancel','protocolNotes','protocolStation','protocolDetailClose','protocolFiles','protocolDuty','protocolTrain','protocol180','protocol280','protocolMileage'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));let records=[],posted,stationRequests=0;
const reply=data=>({ok:true,status:200,json:async()=>data});
class Body{constructor(){this.values={};}append(key,value){this.values[key]=value;}}
const context={document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},window:{},location:{pathname:'/tf/loco-handover'},Intl,Date,Option:function(text,value){const e=new Element('option',value);e.textContent=text;return e;},FormData:Body,setTimeout,clearTimeout,console,fetch:async(path,options)=>{
 if(path.endsWith('/recipients'))return reply([{id:3,label:'Leitstelle'}]);
 if(path.includes('/stations?')){stationRequests++;return reply([{code:'BGO',name:'Görlitz'}]);}
 if(options?.method==='POST'){posted=JSON.parse(options.body.values.payload);records=[{id:4,author_name:'Mira Beispiel',vehicle_number:'91 80 6185 001-2',vehicle_status:'limited',vehicle_status_label:'Eingeschränkt einsatzbereit',station_name:'Görlitz',recipient_name:'Leitstelle',...posted}];return reply(records[0]);}
 if(path.endsWith('/protocols/4'))return reply({...records[0],files:[{id:8,filename:'Bild.png'}]});
 return reply(records);
}};
(async()=>{
 vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/handover-protocols.js','utf8'),context);
 await context.window.HandoverProtocols.select({id:1,vehicle_number:'91 80 6185 001-2',status:'limited'},true);
 assert.equal(elements.handoverNew.hidden,false);await elements.handoverNew.onclick();assert.equal(elements.protocolEditor.hidden,false);assert.equal(elements.protocolVehicle.dataset.status,'limited');assert.equal(elements.protocolRecipient.children[1].textContent,'Leitstelle');
 elements.protocolNotes.value='Test';elements.protocolNotes.oninput();assert.equal(elements.protocolCount.textContent,'4/1000');
 elements.protocolStation.value='BGO';elements.protocolStation.oninput();await new Promise(r=>setTimeout(r,300));elements.protocolStation.value='BGO · Görlitz';elements.protocolStation.oninput();await new Promise(r=>setTimeout(r,300));assert.equal(stationRequests,1);
 for(const [id,value] of Object.entries({protocolTime:'2026-10-23T09:05',protocolDuty:'V1',protocolTrain:'000123',protocol180:'123',protocol280:'456',protocolMileage:'789',protocolRecipient:'3'}))elements[id].value=value;
 await elements.protocolForm.onsubmit({preventDefault(){}});assert.equal(posted.station_code,'BGO');assert.equal(posted.recipient_id,3);assert.equal(posted.train_number,'000123');assert.equal(elements.protocolEditor.hidden,true);assert.equal(elements.protocolRows.children.length,1);assert.equal(elements.protocolRows.children[0].children.length,5);assert.equal(elements.protocolRows.children[0].children[0].children[0].textContent,'23.10.2026 09.05');
 await elements.protocolRows.children[0].children[0].children[0].onclick();assert.equal(elements.protocolDetail.hidden,false);assert(elements.protocolData.children.some(e=>e.textContent==='Mira Beispiel'));assert(elements.protocolDownloads.children[0].children[0].href.endsWith('/protocols/4/files/8'));
 await context.window.HandoverProtocols.select({id:1,status:'limited'},false);assert.equal(elements.handoverNew.hidden,true);assert.equal(elements.protocolRows.children.length,1);
 context.window.HandoverProtocols.clear();assert.equal(elements.protocolDetail.hidden,true);assert.equal(elements.protocolRows.children.length,0);
 console.log('Handover protocol UI: form, status color, recipient selection, station lookup, counter, save/close, five-column list, detail/files and read-only mode passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
