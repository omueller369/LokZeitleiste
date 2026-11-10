const fs=require('node:fs'),vm=require('./localized-vm.cjs'),assert=require('node:assert/strict');
class E {
 constructor(){this.dataset={};this.value='';this.rows=[];this.children=[];this.attrs={};this.isConnected=true;}
 addEventListener(name,fn){this[name+'-event']=fn;}
 append(...children){this.children.push(...children);}
 setAttribute(name,value){this.attrs[name]=value;}
 focus(){this.focused=true;}
 showModal(){this.open=true;}
 close(value){this.open=false;if(value!==undefined)this.returnValue=value;this['close-event']?.();}
}
const nodes={},el=id=>nodes[id]??=new E(),window={},source=fs.readFileSync('backend/lokzeitleiste/static/work-report.js','utf8').split('// Keep collapse buttons')[0].replace(/\}\)\(\);\s*$/,`window.testSync={synchronize,monthReportActions,setup(rows,current){pending=structuredClone(rows);state={client_id:current,saved_id:null};user={id:1};key='test';reportViewOnly=false;trainEditor={hasPending:()=>false,restore(){},draft:()=>[]};syncDrafts=async()=>{};freeze=()=>{};hasDraft=()=>false;readFiles=renderServerFiles=month=loadCurrentMonth=async()=>{};totals=storeDraft=renderMonth=()=>{};files=async()=>[];},pending:()=>pending};})();`),sent=[];
vm.runInNewContext(source,{window,document:{getElementById:el,createElement:()=>new E(),createElementNS:()=>new E()},localStorage:{setItem(){}},fetch:async(path,opts)=>{const body=JSON.parse(opts.body);sent.push(body.client_id);return {ok:true,status:201,json:async()=>({...body,id:sent.length,train_revision:0})};},structuredClone,Date,Intl,console,setTimeout,clearTimeout});
(async()=>{const api=window.testSync,rows=['a','b','c'].map(client_id=>({client_id,start_at:'2026-10-01T09:01',end_at:'2026-10-01T10:02',trips:[]}));api.setup(rows,'a');await api.synchronize(['b']);assert.deepEqual(sent,['b']);assert.deepEqual(Array.from(api.pending(),r=>r.client_id),['a','c']);api.setup(rows,'a');sent.length=0;await api.synchronize();assert.deepEqual(sent,['a']);assert.deepEqual(Array.from(api.pending(),r=>r.client_id),['b','c']);api.setup(rows,'a');sent.length=0;await api.synchronize(['a','b','c']);assert.deepEqual(sent,['a','b','c']);assert.equal(api.pending().length,0);api.setup(rows,'a');sent.length=0;
 const cell=api.monthReportActions({...rows[1],local:true});
 const group=cell.children[0];
 assert.equal(group.className,'report-row-actions');
 assert.deepEqual(group.children.map(button=>button.attrs['aria-label']),['Löschen','Synchronisieren']);
 assert(group.children.every(button=>button.children[0].attrs['aria-hidden']==='true'));
 const conflict=api.monthReportActions({...rows[1],local:true,_cloud_conflict:true});
 assert.equal(conflict.children.length,1,'Conflict actions stay in the icon group');
 assert.equal(conflict.children[0].children[2].attrs['aria-label'],'Serverstand laden');
 assert.equal(conflict.children[0].children[1].disabled,true);

 const send=group.children[1],dialog=el('reportSendDialog'),event={stopPropagation(){}};
 const cancelled=send.onclick(event);assert.equal(dialog.open,true);assert(el('reportSendCancel').focused);assert.deepEqual(sent,[]);
 dialog.close('cancel');await cancelled;assert.deepEqual(sent,[]);assert.equal(api.pending().length,3);assert(send.focused);
 const escaped=send.onclick(event);dialog.close();await escaped;assert.deepEqual(sent,[]);
 const accepted=send.onclick(event);assert.deepEqual(sent,[]);dialog.close('send');await accepted;
 assert.deepEqual(sent,['b']);assert.deepEqual(Array.from(api.pending(),r=>r.client_id),['a','c']);
 console.log('Selective synchronization: icons, cancel and Escape without sending, explicit confirmation and selected report only passed.');})().catch(e=>{console.error(e);process.exitCode=1});
