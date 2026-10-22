(()=>{
const label='zurück TF-Portal';let generation=0;
function clear(){document.querySelectorAll('[data-tf-portal-return]').forEach(node=>node.remove());}
async function refresh(){const revision=++generation;try{
 const response=await fetch('/api/v1/account/me',{credentials:'same-origin'});
 if(revision!==generation)return;
 if(!response.ok){clear();return;}
 const user=await response.json();if(revision!==generation)return;
 const main=document.querySelector('main');
 if(user.role!=='tf'||location.pathname==='/tf'||!main){clear();return;}
 if(!document.getElementById('tfPortalReturnStyle')){const style=document.createElement('style');style.id='tfPortalReturnStyle';style.textContent='.tf-portal-return{display:flex;margin:18px 0}.tf-portal-return button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;max-width:100%;padding:11px 18px;border:1px solid #103346;border-radius:8px;background:#17445b;color:#fff;font:inherit;font-weight:650;cursor:pointer;box-shadow:0 2px 4px #132c4030}.tf-portal-return button:hover{background:#103346}.tf-portal-return button:focus-visible{outline:3px solid #db9b22;outline-offset:3px}';document.head.append(style);}
 clear();
 for(const position of ['top','bottom']){const nav=document.createElement('nav');nav.className='tf-portal-return';nav.dataset.tfPortalReturn=position;nav.setAttribute('aria-label','TF Portal');const button=document.createElement('button');button.type='button';button.textContent=window.I18n?.t(label)||label;button.dataset.i18nIgnore='';button.onclick=()=>{location.href='/tf';};nav.append(button);if(position==='top')main.prepend(nav);else main.append(nav);}
 }catch(error){/* Keep existing navigation available during a network outage. */}}
window.TfPortalReturn={refresh};
window.addEventListener('accountchange',refresh);
window.addEventListener('languagechange',()=>document.querySelectorAll('[data-tf-portal-return] button').forEach(button=>{button.textContent=window.I18n?.t(label)||label;}));
refresh();
})();
