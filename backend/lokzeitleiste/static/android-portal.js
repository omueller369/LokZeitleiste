/* Android-only adapters. Shared portal rules and APIs remain the source of truth. */
(()=>{
if(!window.NativePortal)return;
let serial=0;const waiting=new Map();
NativePortal.onmessage=event=>{let reply;try{reply=JSON.parse(event.data);}catch(_){return;}const job=waiting.get(reply.id);if(!job)return;waiting.delete(reply.id);reply.ok?job.resolve(reply.value):job.reject(Error(reply.error||'App-Anfrage fehlgeschlagen.'));};
function request(method,values={}){return new Promise((resolve,reject)=>{const id=String(++serial);waiting.set(id,{resolve,reject});try{NativePortal.postMessage(JSON.stringify({id,method,...values}));}catch(error){waiting.delete(id);reject(error);}});}
const session=request('session'),originalFetch=window.fetch.bind(window);
function cacheable(path){if(path.startsWith('/api/v1/tf/gps/')||path.startsWith('/api/v1/tf/work-report'))return false;return path==='/api/v1/account/me'||path==='/api/v1/account/locale'||path.startsWith('/api/v1/tf/')||path==='/api/v1/documents/tree';}
window.fetch=async(input,options={})=>{
 const url=new URL(typeof input==='string'?input:input.url,location.href),method=options.method||input.method||'GET';
 if(url.origin!==location.origin)return originalFetch(input,options);if(method!=='GET'||!cacheable(url.pathname)){const response=await originalFetch(input,options);if((response.status===401&&(url.pathname==='/api/v1/account/me'||url.pathname.startsWith('/api/v1/tf/')))||(response.ok&&['/api/v1/account/logout','/api/v1/account/password'].includes(url.pathname)))request('expired').catch(()=>{});return response;}
 const current=await session,key='lokzeitleiste.android.'+current.account.id+'.'+url.pathname+url.search;
 try{const response=await originalFetch(input,options);if(response.status===401)request('expired').catch(()=>{});if(response.ok){response.clone().text().then(value=>{if(value.length>64000)return;try{const indexKey='lokzeitleiste.android.'+current.account.id+'.cache-index',index=JSON.parse(localStorage.getItem(indexKey)||'[]').filter(item=>item!==key);index.push(key);while(index.length>8)localStorage.removeItem(index.shift());localStorage.setItem(indexKey,JSON.stringify(index));localStorage.setItem(key,value);}catch(_){}});}return response;}
 catch(error){let cached;try{cached=localStorage.getItem(key);}catch(_){}if(!cached&&url.pathname==='/api/v1/account/me')cached=JSON.stringify(current.account);if(!cached&&url.pathname==='/api/v1/tf/portal')cached=JSON.stringify(current.profile);if(cached)return new Response(cached,{status:200,headers:{'Content-Type':'application/json','X-LokZeitleiste-Offline':'1'}});throw error;}
};
async function saveBlob(name,blob){const job=await request('export.start',{name});try{for(let offset=0;offset<blob.size;offset+=49152){const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob.slice(offset,offset+49152));});await request('export.chunk',{export_id:job.export_id,data});}}finally{await request('export.finish',{export_id:job.export_id});}}
window.AndroidPortal={request,saveBlob,gps:(method,values)=>request('gps.'+method,values)};
window.addEventListener('languagechange',()=>{if(window.I18n?.language)request('language',{language:window.I18n.language}).catch(()=>{});});
})();
