const fs=require('node:fs'),vm=require('./localized-vm.cjs'),assert=require('node:assert/strict');
class E{constructor(){this.children=[];this.attrs={};this.style={};this.dataset={};}append(...n){this.children.push(...n);}replaceChildren(){this.children=[];}setAttribute(k,v){this.attrs[k]=v;}addEventListener(name,handler){this[name]=handler;}}
const nodes={},window={addEventListener(){}},data={has_photo:false,data:{first_name:'<script>kein HTML</script>',last_name:'Beispiel',tf_number:787123,personnel_number:'00123',gender:'female',nationality:'DE',role:'tf',weekly_minutes:2400,monthly_minutes:10440,bahncard:100,addresses:[{street:'Teststraße',house_number:'1A',postal_code:'01234',city:'Berlin',federal_state:'BE',is_postal:true}]}};
let navigatedTo;
const location={pathname:'/tf/me',assign(url){navigatedTo=url;}};
vm.runInNewContext(fs.readFileSync('backend/lokzeitleiste/static/tf-profile.js','utf8'),{location,window,document:{getElementById:id=>nodes[id]??=new E(),createElement:()=>new E()},Intl,URL,console,fetch:async()=>({ok:true,json:async()=>data})});
(async()=>{await new Promise(setImmediate);const values=nodes.profileValues.children.filter((_,i)=>i%2===1);assert.equal(values[0].textContent,'<script>kein HTML</script>');assert.equal(values[0].attrs['data-i18n-ignore'],'');const labels = nodes.profileValues.children.filter((_, i) => i % 2 === 0).map(n => n.textContent);
for (const label of ['Dienstart', 'Wochenarbeitszeit', 'Sollstunden (monatlich)', 'Monat', 'Urlaubstage', 'BahnCard', 'gültig bis', 'Beitrittsdatum', 'Austrittsdatum', 'Sofortige Sperre', 'Heimatbahnhof', 'Bahnhofsname', 'Bundesland']) {
    assert(!labels.includes(label), `Unexpected TF profile field: ${label}`);
}
assert.equal(nodes.profileAddresses.children[0].textContent, 'Teststraße 1A\n01234 Berlin · Postanschrift');
assert(values.some(n=>n.textContent==='Deutschland'));assert(values.some(n=>n.textContent===787123));assert.equal(nodes.profileAddresses.children.length,1);assert(nodes.profileAddresses.children[0].textContent.includes('Postanschrift'));const html = require('./localized-vm.cjs').resolveHtml(fs.readFileSync('backend/lokzeitleiste/static/tf-profile.html','utf8'));
const passwordButton = html.match(/<button type="button" id="profilePassword" data-url="([^"]+)">Passwort ändern<\/button>/);
assert(passwordButton, 'Visible password button');
nodes.profilePassword.dataset.url = passwordButton[1];
nodes.profilePassword.click();
assert.equal(navigatedTo, '/account?area=tf');
console.log('Own personnel view: safe literal data, own TF number, hidden employment fields, nationality, postal addresses and password button passed.');})().catch(e=>{console.error(e);process.exitCode=1});
