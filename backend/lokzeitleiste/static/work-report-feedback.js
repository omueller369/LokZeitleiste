/* Accessible error and help dialogs shared by the work report and its GPS editor. */
(()=>{
const t=value=>window.I18n?.t(value)||value,node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=t(text);return n;};
const queue=[];let current=null,returnFocus=null,dismissTimer;
function hint(message){
 if(/pause|pausen/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_7e760b946147");
 if(/bahnhof|betriebsstelle|station/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_a9b72683e9fb");
 if(/überschneid|innerhalb|nach Von|kürzer|Dienstzeit|Dienstbeginn|Dienstende|Datum|Uhrzeit/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_609b67679bc4");
 if(/GPS|Standort|geolocation|location/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_f561a249bf4d");
 if(/beleg|datei|anhang|upload/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_3ef5d7a7ff5e");
 if(/offline|fetch|network|verbindung|synchron|Anfrage fehlgeschlagen/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_1824ed44017f");
 if(/lokal|speicher/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_0d3544409de9");
 if(/Ereignis|Bearbeitung|Entwurf/i.test(message))return globalThis.CtlText.source("portal_work_report_feedback.text_440190ed4a16");
 return globalThis.CtlText.source("portal_work_report_feedback.text_55abf32cdd8e");
}
const dialog=node('dialog');dialog.className='report-feedback';dialog.setAttribute('role','alertdialog');dialog.setAttribute('aria-labelledby','reportErrorTitle');dialog.setAttribute('aria-describedby','reportErrorText reportErrorHint');
const title=node('h2',globalThis.CtlText.source("portal_work_report_feedback.text_d034ea0fdad1"));title.id='reportErrorTitle';const message=node('p');message.id='reportErrorText';message.setAttribute('data-i18n-ignore','');const suggestion=node('p');suggestion.id='reportErrorHint';const actions=node('div');actions.className='report-feedback-actions';const okay=node('button',globalThis.CtlText.source("portal_work_report_feedback.text_16584052fd33")),helpButton=node('button',globalThis.CtlText.source("portal_work_report_feedback.text_95472f650a2b"));for(const b of [okay,helpButton])b.type='button';actions.append(okay,helpButton);dialog.append(title,message,suggestion,actions);
document.body.append(dialog);
async function openHelp(){try{const reader=window.TfHelp||await window.loadTfHelp?.();if(!reader)throw Error(globalThis.CtlText.source("portal_work_report_feedback.text_423e45b97d3e"));reader.open(reader.contextFor(location.pathname));}catch(error){window.ReportFeedback.error(error.message);}}
function next(){if(current||!queue.length)return;current=queue.shift();returnFocus=current.field||document.activeElement;message.textContent=t(current.message);suggestion.textContent=t(current.hint||hint(current.message));dialog.showModal();okay.focus();const shown=current;if(current.autoCloseMs) dismissTimer=setTimeout(()=>{if(current===shown&&dialog.open)dialog.close();},current.autoCloseMs);}
function finish(){clearTimeout(dismissTimer);current=null;const focus=returnFocus;returnFocus=null;if(focus?.isConnected!==false&&!focus?.disabled)focus?.focus?.();next();}
okay.onclick=()=>dialog.close();dialog.addEventListener('close',finish);dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.close();});
helpButton.onclick=openHelp;
window.ReportFeedback={help:openHelp,error(value,options={}){const message=String(value||'').trim();window.CtlValidation?.report(message,options.field?[options.field]:undefined);if(!message||current?.message===message||queue.some(row=>row.message===message))return;queue.push({message,...options});next();},hint};
// A form can emit several invalid events at once. Show its first invalid field only.
let invalidPending=false;
(document.getElementById('workReport')||(document.getElementById('messageCompose')?document:null))?.addEventListener('invalid',event=>{event.preventDefault();if(invalidPending)return;invalidPending=true;setTimeout(()=>invalidPending=false,0);const field=event.target,label=field.labels?.[0]?.textContent?.trim()||field.getAttribute('aria-label')||'';window.ReportFeedback.error(label?label+': '+field.validationMessage:field.validationMessage,{field,hint:globalThis.CtlText.source("portal_work_report_feedback.text_d19d77ca4519")});},true);
})();
