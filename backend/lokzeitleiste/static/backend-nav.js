(async()=>{try{const response=await fetch('/api/v1/admin/me',{credentials:'same-origin',cache:'no-store'});if(!response.ok)return;const me=await response.json(),p=me.permissions;const fingerprint=JSON.stringify(p),existing=document.querySelector('.backend-menu-control');if(existing?.dataset.menuRevision==='20261022-tree-4'&&existing.dataset.accountId===String(me.id)&&existing.dataset.permissions===fingerprint)return;existing?.remove();let nav=document.getElementById('navigation');if(!nav){nav=document.createElement('nav');nav.className='card';nav.id='navigation';document.querySelector('main').prepend(nav);}nav.setAttribute('aria-label','Backend-Menü');nav.hidden=true;nav.classList.add('backend-menu');nav.replaceChildren();const list=document.createElement('ul');list.className='menu-tree';nav.append(list);
function group(label,parent=list,href=null,allowed=true){const item=document.createElement('li'),heading=document.createElement(href?'a':'span'),children=document.createElement('ul');heading.textContent=label;heading.className='menu-heading';if(href){heading.href=href;if(!allowed)heading.title='Freigabe erforderlich';markCurrent(heading,href);}item.append(heading,children);parent.append(item);return children;}
function markCurrent(anchor,href){const target=new URL(href,location.href);if(location.pathname!==target.pathname)return;if(target.pathname==='/admin/planning'&&['readonly','overview'].some(key=>target.searchParams.get(key)!==new URLSearchParams(location.search).get(key)))return;anchor.setAttribute('aria-current','page');}
function link(box,label,href,allowed=true){const li=document.createElement('li'),anchor=document.createElement('a');anchor.textContent=label;anchor.href=href;if(!allowed)anchor.title='Freigabe erforderlich';markCurrent(anchor,href);li.append(anchor);box.append(li);return anchor;}
function placeholder(box,label){const item=document.createElement('li'),text=document.createElement('span');text.className='menu-placeholder';text.textContent=label;text.setAttribute('aria-disabled','true');item.append(text);box.append(item);}
const hasEmployees=['employees','planning','worktime','reports','directory','shifts','email'].some(module=>p[module]);
const modules=[
 ['directory','Alle Mitarbeiter','/admin/directory',!!p.directory],
 ['tf','TFs (Liste)','/admin/tf',hasEmployees],
 ['tfNew','TF anlegen','/admin/tf/new',p.employees===3],
 ['staff','Verwaltungsmitarbeiter (Liste)','/admin/staff',!!p.staff],
 ['staffNew','Verwaltungsmitarbeiter anlegen','/admin/staff/new',p.staff===3],
 ['planning','Arbeitszeitplanung','/admin/planning',!!p.planning],
 ['shifts','Schichtplan','/admin/shifts',!!p.shifts],
 ['overview','TF-Übersicht','/admin/planning?overview=all',!!p.planning],
 ['vehicles','Triebfahrzeuge','/admin/vehicles',me.role==='admin'||!!p.vehicles],
 ['roster','Dienstplan','/admin/planning?readonly=1',!!p.planning],
 ['hours','Dienstzeit','/admin/tf/hours',!!p.planning&&!!(p.worktime||p.reports)],
 ['worktime','Arbeitszeiterfassung und Korrekturen','/admin/worktime',!!p.worktime],
 ['email','Email','/admin/email',!!p.email],
 ['documents','Meine Dokumente','/documents',true],
 ['password','Mein Passwort ändern','/account',true]
];
if(me.role==='staff')modules.push(['ownTime','Meine Arbeitszeiten','/my/worktime',true]);
function moduleLink(parent,id,label=null){const module=modules.find(item=>item[0]===id);return link(parent,label||module[1],module[2],module[3]);}
const administration=group('Administration');for(const module of modules)link(administration,module[1],module[2],module[3]);
const management=group('Verwaltung'),employees=group('Mitarbeiter',management);
const drivers=group('TFs',employees,'/admin/tf',hasEmployees);moduleLink(drivers,'tfNew','anlegen');
const office=group('Verwaltung',employees,'/admin/staff',!!p.staff);moduleLink(office,'staffNew','anlegen');
const planning=group('Personalplanung');for(const id of ['planning','shifts','overview'])moduleLink(planning,id);
const other=group('Sonstiges'),master=group('Stammdaten',other);moduleLink(master,'vehicles');placeholder(master,'App Grundwerte (folgt später)');
for(const id of ['directory','roster','hours','worktime','email','documents','password',...(me.role==='staff'?['ownTime']:[])])moduleLink(other,id);
const logoutItem=document.createElement('li'),logout=document.createElement('button');logout.type='button';logout.textContent='Abmelden';logout.onclick=async()=>{logout.disabled=true;try{const result=await fetch('/api/v1/admin/logout',{method:'POST',credentials:'same-origin'});if(!result.ok)throw Error('Abmelden fehlgeschlagen');location.href='/admin';}catch(error){logout.disabled=false;alert(error.message);}};logoutItem.className='menu-logout';logoutItem.append(logout);list.append(logoutItem);
const stylesheet=document.querySelector('link[href^="/responsive.css"]');if(stylesheet)stylesheet.href='/responsive.css?v=20261022-tree-4';
const header=document.querySelector('header');if(!header)return;
const control=document.createElement('div');control.className='backend-menu-control';control.dataset.menuRevision='20261022-tree-4';control.dataset.accountId=String(me.id);control.dataset.permissions=fingerprint;
const toggle=document.createElement('button');toggle.type='button';toggle.className='backend-menu-toggle';toggle.textContent='☰';toggle.setAttribute('aria-label','Backend-Menü');toggle.setAttribute('title','Backend-Menü');toggle.setAttribute('aria-controls','navigation');toggle.setAttribute('aria-expanded','false');
control.append(toggle,nav);header.append(control);
let pinned=false,closeTimer=null,suppressHover=false;
function show(){clearTimeout(closeTimer);nav.style.maxHeight=Math.max(100,window.innerHeight-toggle.getBoundingClientRect().bottom-20)+'px';nav.hidden=false;toggle.setAttribute('aria-expanded','true');}
function hide(restoreFocus=false){clearTimeout(closeTimer);pinned=false;nav.hidden=true;toggle.setAttribute('aria-expanded','false');if(restoreFocus)toggle.focus();}
toggle.onclick=()=>{if(pinned){suppressHover=true;hide();}else{pinned=true;show();}};
control.addEventListener('pointerenter',event=>{if(event.pointerType==='mouse'&&!suppressHover)show();});
control.addEventListener('pointerleave',event=>{if(event.pointerType!=='mouse')return;suppressHover=false;if(!pinned)closeTimer=setTimeout(()=>{if(!nav.contains(document.activeElement))hide();},180);});
control.addEventListener('keydown',event=>{if(event.key==='Escape'&&!nav.hidden){event.preventDefault();suppressHover=true;hide(true);}else if(event.key==='ArrowDown'&&event.target===toggle){event.preventDefault();show();nav.querySelector('a,button:not(:disabled)')?.focus();}});
control.addEventListener('focusout',event=>{if(!control.contains(event.relatedTarget))hide();});
document.addEventListener('pointerdown',event=>{if(!control.contains(event.target))hide();});
nav.addEventListener('click',event=>{if(event.target.closest('a'))hide();});

}catch(e){console.error('Backend-Menü konnte nicht geladen werden',e);}})();
