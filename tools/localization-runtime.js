/* Shared deterministic key resolver. No network dependency, including in Android assets. */
(()=>{
 const languages=['de','pl','en'],catalog=globalThis.CtlMessages;
 let language='de';try{const saved=globalThis.localStorage?.getItem('lokzeitleiste.language');if(languages.includes(saved))language=saved;}catch{}
 const token=/\{\{([a-z][a-z0-9_]*\.text_[a-f0-9]{12})\}\}/g;
 function source(key){if(!Object.hasOwn(catalog.de,key))throw Error('Unknown translation key: '+key);return catalog.de[key];}
 function text(key,parameters={},locale=language){let value=(catalog[locale]||catalog.de)[key]??source(key);for(const [name,replacement]of Object.entries(parameters))value=value.replaceAll('{'+name+'}',String(replacement));return value;}
 function restore(value,locale='de'){if(typeof value==='string')return value.replace(token,(_,key)=>text(key,{},locale));if(Array.isArray(value))return value.map(v=>restore(v,locale));if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,restore(v,locale)]));return value;}
 function resolve(root){if(!root)return;const visit=node=>{if(node.nodeType===3){if(node.parentElement?.closest('script,style,textarea,[contenteditable],[data-i18n-ignore]'))return;const value=restore(node.nodeValue,language);if(value!==node.nodeValue)node.nodeValue=value;}else if(node.nodeType===1){for(const attr of ['title','aria-label','alt','placeholder']){const old=node.getAttribute(attr);if(old!==null){const value=restore(old,language);if(value!==old)node.setAttribute(attr,value);}}}};visit(root);if(globalThis.document?.createTreeWalker){const walker=document.createTreeWalker(root,5);let n;while(n=walker.nextNode())visit(n);}}
 globalThis.CtlText={source,text,restore,resolve,languages,setLanguage(value){if(languages.includes(value))language=value;},get language(){return language;}};
 if(typeof document!=='undefined'&&document.documentElement&&typeof MutationObserver!=='undefined'){
  new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)resolve(node);}).observe(document.documentElement,{childList:true,subtree:true});
  document.addEventListener('DOMContentLoaded',()=>resolve(document.documentElement),{once:true});
 }
})();
