(async()=>{try{const response=await fetch('/api/v1/admin/me',{credentials:'same-origin',cache:'no-store'});if(!response.ok){window.BackendNavigation?.destroy();return;}const me=await response.json(),p=me.permissions;let preference={user_id:me.id,variant:'sidebar'};try{const r=await fetch('/api/v1/admin/menu-preference',{credentials:'same-origin',cache:'no-store'});if(r.ok)preference=await r.json();}catch(_){}const variants=['sidebar','compact','sections'];let variant=variants.includes(preference.variant)?preference.variant:'sidebar';const fingerprint=JSON.stringify({role:me.role,permissions:p}),existing=document.querySelector('.backend-menu-control');if(existing?.dataset.menuRevision==='20261024-admin-tools-11'&&existing.dataset.variant===variant&&existing.dataset.accountId===String(me.id)&&existing.dataset.permissions===fingerprint&&window.BackendNavigation&&document.getElementById('backend-sidebar'))return;window.BackendNavigation?.destroy();existing?.remove();let nav=document.getElementById('navigation');if(!nav){nav=document.createElement('nav');nav.className='card';nav.id='navigation';document.querySelector('main').prepend(nav);}nav.setAttribute('aria-label','Backend-Menü');nav.hidden=true;nav.classList.add('backend-menu');nav.replaceChildren();const list=document.createElement('ul');list.className='menu-tree';nav.append(list);
let groupCount=0;
function group(label,parent=list,href=null,allowed=true){
 const item=document.createElement('li'),row=document.createElement('div'),heading=document.createElement(href?'a':'button'),children=document.createElement('ul'),toggle=href?document.createElement('button'):heading;
 row.className='menu-group-row';heading.textContent=label;heading.className='menu-heading';
 children.id='backend-submenu-'+(++groupCount);children.hidden=true;
 toggle.type='button';toggle.classList.add('menu-submenu-toggle');toggle.setAttribute('aria-controls',children.id);toggle.setAttribute('aria-expanded','false');
 toggle.onclick=()=>{children.hidden=!children.hidden;toggle.setAttribute('aria-expanded',String(!children.hidden));};
 if(href){heading.href=href;heading.id=children.id+'-label';toggle.setAttribute('aria-labelledby',heading.id);if(!allowed)heading.title='Freigabe erforderlich';markCurrent(heading,href);row.append(heading,toggle);}else row.append(heading);
 item.append(row,children);parent.append(item);return children;
}
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
 ['app_defaults','App Grundwerte','/admin/app-defaults',me.role==='admin'||!!p.app_defaults],
 ['loco_handover','Lokübergabebuch','/admin/loco-handover',me.role==='admin'||!!p.loco_handover],
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
const home=document.createElement('li'),homeLink=document.createElement('a');home.style.gridColumn='1 / -1';homeLink.textContent='Startseite';homeLink.href='/admin/start';markCurrent(homeLink,homeLink.href);home.append(homeLink);list.append(home);
link(list,'Menü anpassen','/admin/menu-designs');
if(me.role==='admin'){const administration=group('Administration');for(const module of modules)link(administration,module[1],module[2],module[3]);}
const management=group('Verwaltung'),employees=group('Mitarbeiter',management);
const drivers=group('TFs',employees,'/admin/tf',hasEmployees);moduleLink(drivers,'tfNew','anlegen');
const office=group('Verwaltung',employees,'/admin/staff',!!p.staff);moduleLink(office,'staffNew','anlegen');
const planning=group('Personalplanung');for(const id of ['planning','shifts','overview'])moduleLink(planning,id);
const other=group('Sonstiges'),master=group('Stammdaten',other);moduleLink(master,'vehicles');moduleLink(master,'app_defaults');
for(const id of ['loco_handover','directory','roster','hours','worktime','email','documents','password',...(me.role==='staff'?['ownTime']:[])])moduleLink(other,id);
const logoutItem=document.createElement('li'),logout=document.createElement('button');logout.type='button';logout.textContent='Abmelden';logout.onclick=async()=>{logout.disabled=true;try{const result=await fetch('/api/v1/admin/logout',{method:'POST',credentials:'same-origin'});if(!result.ok)throw Error('Abmelden fehlgeschlagen');location.href='/admin';}catch(error){logout.disabled=false;alert(error.message);}};logoutItem.className='menu-logout';logoutItem.append(logout);list.append(logoutItem);
const stylesheet=document.querySelector('link[href^="/responsive.css"]');if(stylesheet)stylesheet.href='/responsive.css?v=20261024-admin-tools-11';
if(!document.querySelector('link[data-backend-sidebar]')){const style=document.createElement('link');style.rel='stylesheet';style.href='/admin/backend-nav.css?v=20261024-admin-tools-11';style.dataset.backendSidebar='true';document.head.append(style);}
const header=document.querySelector('header');if(!header)return;
const t=value=>window.I18n?.t(value)||value;
const control=document.createElement('div');control.className='backend-menu-control';control.dataset.menuRevision='20261024-admin-tools-11';control.dataset.accountId=String(me.id);control.dataset.permissions=fingerprint;
const toggle=document.createElement('button');toggle.type='button';toggle.className='backend-menu-toggle';toggle.textContent='☰';toggle.setAttribute('aria-label',t('Backend-Menü'));toggle.setAttribute('title',t('Backend-Menü'));toggle.setAttribute('aria-controls','backend-sidebar');toggle.setAttribute('aria-expanded','false');control.append(toggle);header.append(control);
const sidebar=document.createElement('aside');sidebar.id='backend-sidebar';sidebar.className='backend-sidebar-panel';sidebar.hidden=true;sidebar.setAttribute('aria-labelledby','backend-sidebar-title');
const top=document.createElement('div');top.className='backend-sidebar-header';const title=document.createElement('h2');title.id='backend-sidebar-title';title.textContent='Backend-Menü';
const closeButton=document.createElement('button');closeButton.type='button';closeButton.className='backend-sidebar-close';closeButton.textContent='×';closeButton.setAttribute('data-i18n-ignore','');closeButton.setAttribute('aria-label',t('Menü schließen'));top.append(title,closeButton);nav.hidden=false;sidebar.append(top,nav);
const overlay=document.createElement('button');overlay.type='button';overlay.className='backend-sidebar-overlay';overlay.hidden=true;overlay.tabIndex=-1;overlay.setAttribute('aria-label',t('Menü schließen'));
document.body.append(overlay,sidebar);
const bar=document.createElement('nav');bar.className='backend-section-bar';bar.setAttribute('aria-label','Hauptbereiche');for(const [label,href]of [['Startseite','/admin/start'],['Verwaltung','/admin/start?section=management'],['Personalplanung','/admin/start?section=planning']]){if(label==='Verwaltung'&&!hasEmployees&&!p.staff)continue;if(label==='Personalplanung'&&!p.planning&&!p.shifts)continue;const a=document.createElement('a');a.textContent=label;a.href=href;bar.append(a);}const more=document.createElement('button');more.type='button';more.textContent='Mehr';more.setAttribute('aria-controls','backend-sidebar');bar.append(more);header.after(bar);
function permanent(){return variant==='sidebar'&&media.matches;}
const media=window.matchMedia('(min-width:1100px)'),cleanups=[];let opened=false,locked=false,restoreTarget=null,inertElements=[],previousOverflow='';
function on(target,event,handler){target.addEventListener(event,handler);cleanups.push(()=>target.removeEventListener(event,handler));}
function focusable(){return [...sidebar.querySelectorAll('a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),[tabindex]:not([tabindex="-1"])')].filter(item=>!item.closest('[hidden]')&&!item.disabled);}
function release(){for(const [item,inert]of inertElements)item.inert=inert;inertElements=[];if(locked)document.body.style.overflow=previousOverflow;locked=false;opened=false;sidebar.removeAttribute('role');sidebar.removeAttribute('aria-modal');overlay.hidden=true;toggle.setAttribute('aria-expanded','false');more.setAttribute('aria-expanded','false');}
function close(restoreFocus=false){const target=restoreTarget;release();sidebar.hidden=!permanent();if(restoreFocus&&!permanent())(target?.isConnected?target:variant==='sections'?more:toggle).focus();}
function open(){if(permanent()||opened)return;restoreTarget=document.activeElement;opened=true;sidebar.hidden=false;toggle.setAttribute('aria-expanded','true');more.setAttribute('aria-expanded','true');if(!media.matches){previousOverflow=document.body.style.overflow;locked=true;overlay.hidden=false;sidebar.setAttribute('role','dialog');sidebar.setAttribute('aria-modal','true');document.body.style.overflow='hidden';for(const item of document.body.children){if(item===sidebar||item===overlay||['SCRIPT','STYLE','LINK'].includes(item.tagName))continue;inertElements.push([item,item.inert]);item.inert=true;}}closeButton.focus();}
function layout(){const hadFocus=sidebar.contains(document.activeElement);release();const desktop=permanent();document.body.classList.toggle('backend-sidebar-desktop',desktop);document.body.classList.toggle('backend-sections-layout',variant==='sections');sidebar.dataset.variant=variant;control.dataset.variant=variant;bar.hidden=variant!=='sections';control.hidden=desktop||variant==='sections';closeButton.hidden=desktop;sidebar.hidden=!desktop;if(!desktop&&hadFocus)(variant==='sections'?more:toggle).focus();else if(desktop&&document.activeElement===closeButton)homeLink.focus();}
toggle.onclick=more.onclick=()=>opened?close(true):open();closeButton.onclick=()=>close(true);overlay.onclick=()=>close(true);
on(sidebar,'click',event=>{if(!permanent()&&event.target.closest('a'))close(false);});
on(document,'keydown',event=>{if(!opened)return;if(event.key==='Escape'){event.preventDefault();close(true);return;}if(event.key!=='Tab'||!locked)return;const items=focusable(),first=items[0],last=items.at(-1);if(!first){event.preventDefault();closeButton.focus();return;}if(!sidebar.contains(document.activeElement)||(event.shiftKey&&document.activeElement===first)){event.preventDefault();(event.shiftKey?last:first).focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}});
on(window,'backendmenuchange',event=>{const value=event.detail;if(value?.user_id!==me.id||!variants.includes(value.variant))return;variant=value.variant;layout();});
on(document,'pointerdown',event=>{if(opened&&!locked&&!sidebar.contains(event.target)&&!control.contains(event.target)&&!bar.contains(event.target))close(false);});
on(window,'languagechange',()=>{toggle.setAttribute('aria-label',t('Backend-Menü'));toggle.setAttribute('title',t('Backend-Menü'));closeButton.setAttribute('aria-label',t('Menü schließen'));overlay.setAttribute('aria-label',t('Menü schließen'));});
if(media.addEventListener){media.addEventListener('change',layout);cleanups.push(()=>media.removeEventListener('change',layout));}else{media.addListener(layout);cleanups.push(()=>media.removeListener(layout));}
window.BackendNavigation={destroy(){release();for(const cleanup of cleanups)cleanup();control.remove();sidebar.remove();overlay.remove();bar.remove();document.body.classList.remove('backend-sidebar-desktop','backend-sections-layout');if(window.BackendNavigation===this)delete window.BackendNavigation;}};
layout();
}catch(e){console.error('Backend-Menü konnte nicht geladen werden',e);}})();
