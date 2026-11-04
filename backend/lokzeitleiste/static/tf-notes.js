/* Personal server-backed notes. Render user content only with textContent/value. */
(()=>{
const make=(tag,text)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;return el;};
const size=value=>Array.from(value).length;
function stamp(value){
 const parts=new Intl.DateTimeFormat('de-DE',{timeZone:'Europe/Berlin',day:'2-digit',month:'2-digit',year:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));
 const get=type=>parts.find(part=>part.type===type)?.value||'';
 return get('day')+'.'+get('month')+'.'+get('year')+' '+get('hour')+':'+get('minute');
}
window.TfNotesFormat={size,stamp};
window.startTfNotes=async()=>{
 const root=document.getElementById('notesWorkspace');if(root.dataset.mounted)return;root.dataset.mounted='true';
 let rows=[],current=null,busy=false,editing=false,original='',opener=null,deleteTarget=null,ticket=0;
 const status=make('p'),actions=make('div'),add=make('button',globalThis.CtlText.source("portal_tf_notes.text_d4afa665cfd6")),reload=make('button',globalThis.CtlText.source("portal_tf_notes.text_96bf0098166f")),list=make('ul'),empty=make('p',globalThis.CtlText.source("portal_tf_notes.text_a53f7175f54a"));
 status.setAttribute('role','status');status.setAttribute('aria-live','polite');actions.className='controls';list.className='tf-notes-list';list.setAttribute('aria-label',globalThis.CtlText.source("portal_tf_notes.text_9176272cbb7e"));add.type=reload.type='button';actions.append(add,reload);root.append(actions,status,empty,list);
 const dialog=make('dialog'),heading=make('div'),close=make('button','X'),caption=make('h2',globalThis.CtlText.source("portal_tf_notes.text_74b487d9d223")),info=make('p'),problem=make('p'),read=make('article'),full=make('p'),edit=make('button',globalThis.CtlText.source("portal_tf_notes.text_84e45ee73411")),form=make('form'),titleLabel=make('label',globalThis.CtlText.source("portal_tf_notes.text_abcafc82daaf")),title=make('input'),textLabel=make('label',globalThis.CtlText.source("portal_tf_notes.text_71988c4d8e08")),body=make('textarea'),counter=make('p'),save=make('button',globalThis.CtlText.source("portal_tf_notes.text_f6b2ff39f540")),cancel=make('button',globalThis.CtlText.source("portal_tf_notes.text_f7ff1178af20"));
 dialog.id='tfNoteDialog';dialog.className='tf-notes-dialog';dialog.setAttribute('aria-labelledby','noteDialogTitle');caption.id='noteDialogTitle';heading.className='tf-notes-heading';close.type='button';close.setAttribute('aria-label',globalThis.CtlText.source("portal_tf_notes.text_2fe57afdc7c9"));problem.setAttribute('role','alert');read.setAttribute('data-i18n-ignore','');full.className='tf-note-text';title.id='noteTitle';titleLabel.htmlFor=title.id;title.required=true;title.autocomplete='off';body.id='noteText';body.rows=10;body.required=true;body.setAttribute('aria-describedby','noteRemaining');textLabel.htmlFor=body.id;counter.id='noteRemaining';counter.setAttribute('role','status');save.type='submit';cancel.type=edit.type='button';titleLabel.append(title);textLabel.append(body);form.append(titleLabel,textLabel,counter,save,cancel);read.append(full,edit);heading.append(close,caption);dialog.append(heading,info,problem,read,form);document.body.append(dialog);
 const confirm=make('dialog'),confirmTitle=make('h2',globalThis.CtlText.source("portal_tf_notes.text_ce4e2477f0e8")),question=make('p'),deleteError=make('p'),yes=make('button',globalThis.CtlText.source("portal_tf_notes.text_6c2d352161df")),no=make('button',globalThis.CtlText.source("portal_tf_notes.text_f7ff1178af20"));
 confirm.id='tfNoteDeleteDialog';confirm.className='tf-notes-dialog tf-notes-confirm';confirmTitle.id='noteDeleteTitle';confirm.setAttribute('aria-labelledby','noteDeleteTitle');deleteError.setAttribute('role','alert');yes.type=no.type='button';yes.className='tf-note-delete';confirm.append(confirmTitle,question,deleteError,yes,no);document.body.append(confirm);
 const payload=()=>({title:title.value.trim(),text:body.value});
 const dirty=()=>editing&&JSON.stringify(payload())!==original;
 function lock(value){busy=value;add.disabled=reload.disabled=value;yes.disabled=no.disabled=close.disabled=cancel.disabled=edit.disabled=value;title.disabled=body.disabled=value;for(const button of list.querySelectorAll('button'))button.disabled=value;count();}
 function count(){const remaining=1000-size(body.value);counter.textContent=remaining+' / 1000 Zeichen frei';counter.classList.toggle('tf-note-invalid',remaining<0);save.disabled=busy||remaining<0||!body.value.trim()||!title.value.trim()||size(title.value.trim())>120;}
 async function api(path='',options={}){
  const response=await fetch('/api/v1/tf/notes'+path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json',...options.headers}});
  const result=await response.json().catch(()=>({}));
  if(!response.ok)throw Error(response.status===401?globalThis.CtlText.source("portal_tf_notes.text_a3cc17fe0fbe"):typeof result.detail==='string'?result.detail:globalThis.CtlText.source("portal_tf_notes.text_4b9c829db809"));
  return result;
 }
 function render(){
  list.replaceChildren();empty.hidden=rows.length>0;
  for(const note of rows){
   const row=make('li'),open=make('button'),name=make('strong',note.title),date=make('time',stamp(note.created_at)),remove=make('button','🗑️');
   open.type=remove.type='button';open.className='tf-note-open';open.setAttribute('data-i18n-ignore','');date.dateTime=note.created_at;open.append(name,date);
   remove.className='tf-note-trash';remove.setAttribute('aria-label',globalThis.CtlText.source("portal_tf_notes.text_337dcd8f08f0")+note.title);remove.title=globalThis.CtlText.source("portal_tf_notes.text_df94e9b6582f");remove.onclick=()=>askDelete(note,remove);open.onclick=()=>show(note.id,open);row.append(open,remove);list.append(row);
  }
 }
 async function refresh(){const request=++ticket;reload.disabled=true;try{const values=await api();if(request!==ticket)return;rows=values;render();}finally{if(request===ticket)reload.disabled=busy;}}
 function view(note){
  current=note;editing=false;caption.textContent=note.title;caption.setAttribute('data-i18n-ignore','');info.textContent=globalThis.CtlText.source("portal_tf_notes.text_d6d1e74ac3cc")+stamp(note.created_at);full.textContent=note.text;form.hidden=true;read.hidden=false;problem.textContent='';edit.focus();
 }
 function editNote(note){
  editing=true;current=note;title.value=note?.title||'';body.value=note?.text||'';original=JSON.stringify(payload());caption.textContent=note?globalThis.CtlText.source("portal_tf_notes.text_97395593e308"):globalThis.CtlText.source("portal_tf_notes.text_d2f3a2fec038");info.textContent=note?globalThis.CtlText.source("portal_tf_notes.text_d6d1e74ac3cc")+stamp(note.created_at):globalThis.CtlText.source("portal_tf_notes.text_a99444601bc3");read.hidden=true;form.hidden=false;problem.textContent='';count();title.focus();
 }
 function safeClose(){if(busy)return;if(dirty()&&!window.confirm(globalThis.CtlText.source("portal_tf_notes.text_21e2a814d19c")))return;dialog.close();}
 async function show(id,button){
  if(busy)return;opener=button;status.textContent=globalThis.CtlText.source("portal_tf_notes.text_ef5b0c9c8ef3");lock(true);
  try{const note=await api('/'+id);dialog.showModal();view(note);status.textContent='';}catch(error){status.textContent=error.message;}finally{lock(false);}
 }
 function askDelete(note,button){
  if(busy)return;deleteTarget={note,button};deleteError.textContent='';question.textContent=globalThis.CtlText.source("portal_tf_notes.text_1c8665aac89d")+note.title+globalThis.CtlText.source("portal_tf_notes.text_96a7205cd76b");confirm.showModal();no.focus();
 }
 add.onclick=()=>{if(busy)return;opener=add;dialog.showModal();editNote(null);};
 reload.onclick=()=>{status.textContent='';refresh().catch(error=>status.textContent=error.message);};
 edit.onclick=()=>editNote(current);title.oninput=body.oninput=count;close.onclick=safeClose;
 dialog.addEventListener('cancel',event=>{event.preventDefault();safeClose();});
 dialog.addEventListener('close',()=>{editing=false;opener?.isConnected?opener.focus():add.focus();});
 cancel.onclick=()=>{if(dirty()&&!window.confirm(globalThis.CtlText.source("portal_tf_notes.text_8a122f9d3bff")))return;if(current)view(current);else dialog.close();};
 form.onsubmit=async event=>{
  event.preventDefault();count();if(save.disabled)return;const note=current;lock(true);problem.textContent='';
  try{
   const values=payload();if(note)values.expected_revision=note.revision;
   const saved=await api(note?'/'+note.id:'',{method:note?'PUT':'POST',body:JSON.stringify(values)});
   view(saved);status.textContent=globalThis.CtlText.source("portal_tf_notes.text_60d7926405df");
   try{await refresh();}catch(error){status.textContent=globalThis.CtlText.source("portal_tf_notes.text_313654defbdf")+error.message;}
  }catch(error){problem.textContent=error.message;}finally{lock(false);}
 };
 yes.onclick=async()=>{
  if(busy||!deleteTarget)return;const target=deleteTarget;lock(true);deleteError.textContent='';
  try{
   await api('/'+target.note.id+'?expected_revision='+target.note.revision,{method:'DELETE'});
   rows=rows.filter(note=>note.id!==target.note.id);render();confirm.close();status.textContent=globalThis.CtlText.source("portal_tf_notes.text_a9388678d697");add.focus();
  }catch(error){deleteError.textContent=error.message;}finally{lock(false);}
 };
 no.onclick=()=>{if(!busy)confirm.close();};
 confirm.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
 confirm.addEventListener('close',()=>{const button=deleteTarget?.button;if(button?.isConnected)button.focus();else add.focus();deleteTarget=null;});
 window.addEventListener('beforeunload',event=>{if(dirty()){event.preventDefault();event.returnValue='';}});
 try{await refresh();}catch(error){status.textContent=error.message;}
};
})();
