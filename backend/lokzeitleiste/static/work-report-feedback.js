/* Accessible error and help dialogs shared by the work report and its GPS editor. */
(()=>{
const t=value=>window.I18n?.t(value)||value,node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=t(text);return n;};
const queue=[];let current=null,returnFocus=null;
function hint(message){
 if(/pause|pausen/i.test(message))return 'Bitte eine Pause als Zugfahrtereignis eintragen und die erforderlichen Minuten prüfen.';
 if(/bahnhof|betriebsstelle|station/i.test(message))return 'Bitte DS100 oder Bahnhofsname eingeben und einen Eintrag aus den Vorschlägen auswählen.';
 if(/überschneid|innerhalb|nach Von|kürzer|Dienstzeit|Dienstbeginn|Dienstende|Datum|Uhrzeit/i.test(message))return 'Bitte Datum und Uhrzeit von Beginn und Ende sowie mögliche Überschneidungen prüfen.';
 if(/GPS|Standort|geolocation|location/i.test(message))return 'Bitte die Standortfreigabe und die sichere Verbindung (HTTPS) prüfen. Eine laufende Aufzeichnung zuerst beenden.';
 if(/beleg|datei|anhang|upload/i.test(message))return 'Bitte Dateigröße und Dateiformat sowie die Internetverbindung prüfen. Nicht übertragene Belege bleiben lokal gespeichert.';
 if(/offline|fetch|network|verbindung|synchron|Anfrage fehlgeschlagen/i.test(message))return 'Bitte die Internetverbindung prüfen und erneut versuchen. Lokale Berichte bleiben bis zur erfolgreichen Übertragung gespeichert.';
 if(/lokal|speicher/i.test(message))return 'Bitte freien Browserspeicher und die Speicherfreigabe prüfen. Die Seite vor dem Sichern der Eingaben nicht schließen.';
 if(/Ereignis|Bearbeitung|Entwurf/i.test(message))return 'Bitte die aktuelle Eingabe zuerst speichern oder die Bearbeitung abbrechen.';
 return 'Bitte die Eingaben prüfen und die angegebene Ursache korrigieren. Anschließend erneut versuchen.';
}
const dialog=node('dialog');dialog.className='report-feedback';dialog.setAttribute('role','alertdialog');dialog.setAttribute('aria-labelledby','reportErrorTitle');dialog.setAttribute('aria-describedby','reportErrorText reportErrorHint');
const title=node('h2','Eingabe oder Vorgang prüfen');title.id='reportErrorTitle';const message=node('p');message.id='reportErrorText';message.setAttribute('data-i18n-ignore','');const suggestion=node('p');suggestion.id='reportErrorHint';const actions=node('div');actions.className='report-feedback-actions';const okay=node('button','Okay'),helpButton=node('button','Hilfe');for(const b of [okay,helpButton])b.type='button';actions.append(okay,helpButton);dialog.append(title,message,suggestion,actions);
const help=node('dialog');help.className='report-feedback';help.setAttribute('aria-labelledby','reportHelpTitle');const helpHead=node('div');helpHead.className='report-feedback-heading';const helpTitle=node('h2','Hilfe');helpTitle.id='reportHelpTitle';const close=node('button','X');close.type='button';close.className='report-feedback-close';close.setAttribute('aria-label',t('Hilfe schließen'));helpHead.append(helpTitle,close);help.append(helpHead,node('p','Hier erscheint später die passende Hilfeseite. Dieser Text dient vorläufig als Platzhalter.'));
document.body.append(dialog,help);
function next(){if(current||!queue.length)return;current=queue.shift();returnFocus=current.field||document.activeElement;message.textContent=t(current.message);suggestion.textContent=t(current.hint||hint(current.message));dialog.showModal();okay.focus();}
function finish(){current=null;const focus=returnFocus;returnFocus=null;if(focus?.isConnected!==false&&!focus?.disabled)focus?.focus?.();next();}
okay.onclick=()=>dialog.close();dialog.addEventListener('close',finish);dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.close();});
helpButton.onclick=()=>{help.showModal();close.focus();};close.onclick=()=>help.close();help.addEventListener('close',()=>helpButton.focus());
window.ReportFeedback={error(value,options={}){const message=String(value||'').trim();if(!message||current?.message===message||queue.some(row=>row.message===message))return;queue.push({message,...options});next();},hint};
// A form can emit several invalid events at once. Show its first invalid field only.
let invalidPending=false;
document.getElementById('workReport')?.addEventListener('invalid',event=>{event.preventDefault();if(invalidPending)return;invalidPending=true;setTimeout(()=>invalidPending=false,0);const field=event.target,label=field.labels?.[0]?.textContent?.trim()||field.getAttribute('aria-label')||'';window.ReportFeedback.error(label?label+': '+field.validationMessage:field.validationMessage,{field,hint:'Bitte das markierte Pflichtfeld vollständig und im angegebenen Format ausfüllen.'});},true);
})();
