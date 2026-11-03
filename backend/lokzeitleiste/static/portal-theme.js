/* A device/browser preference shared by every portal page. Never touches form or GPS state. */
(()=>{
if(window.PortalTheme)return;
const root=document.documentElement,key='ctl.portal.theme';let mode=root.dataset.theme==='dark'?'dark':'light',button;
const t=s=>window.I18n?.t(s)||s;
function icon(dark){
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','24');svg.setAttribute('height','24');svg.setAttribute('aria-hidden','true');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.8');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');
 if(dark){const circle=document.createElementNS(ns,'circle');circle.setAttribute('cx','12');circle.setAttribute('cy','12');circle.setAttribute('r','4');const rays=document.createElementNS(ns,'path');rays.setAttribute('d','M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4');svg.append(circle,rays);}
 else {const moon=document.createElementNS(ns,'path');moon.setAttribute('d','M20.4 14A8.8 8.8 0 0 1 10 3.6 8.8 8.8 0 1 0 20.4 14Z');svg.append(moon);}return svg;
}
function refresh(){
 if(button){const label=t(mode==='dark'?'Tagmodus einschalten':'Nachtmodus einschalten');button.replaceChildren(icon(mode==='dark'));button.title=label;button.setAttribute('aria-label',t('Nachtmodus'));button.setAttribute('aria-description',label);button.setAttribute('aria-pressed',String(mode==='dark'));}
 let meta=document.querySelector('meta[name="theme-color"]');if(!meta){meta=document.createElement('meta');meta.name='theme-color';document.head.append(meta);}meta.content=mode==='dark'?'#0d1722':'#132c40';
}
function set(value,persist=true){mode=value==='dark'?'dark':'light';root.dataset.theme=mode;root.style.colorScheme=mode;if(persist)try{localStorage.setItem(key,mode);}catch{}refresh();window.dispatchEvent(new Event('portalthemechange'));return mode;}
function toggle(){return set(mode==='dark'?'light':'dark');}
function mount(container){
 container=container||document.querySelector('header.tf-shell .tf-shell-brand')||document.querySelector('header');if(!container&&document.body){container=document.createElement('header');container.className='portal-theme-header';document.body.prepend(container);}if(!container)return;
 if(!button){button=document.createElement('button');button.id='portalThemeToggle';button.type='button';button.className='portal-theme-toggle';button.setAttribute('data-i18n-ignore','');button.onclick=toggle;}
 if(button.parentNode!==container)container.append(button);refresh();
}
window.PortalTheme={get:()=>mode,set,toggle,mount,refresh};
window.addEventListener('storage',event=>{if(event.key===key||event.key===null)set(event.newValue,false);});
window.addEventListener('languagechange',refresh);window.addEventListener('portal-shell-ready',()=>mount());
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>mount(),{once:true});else mount();
refresh();
})();
