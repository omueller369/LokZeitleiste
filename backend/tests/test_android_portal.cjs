const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('backend/lokzeitleiste/static/android-portal.js','utf8'),storage=new Map();
async function boot(id){let online=true,status=200,calls=[];const native={postMessage(raw){const r=JSON.parse(raw);calls.push(r);const value=r.method==='session'?{account:{id,role:'tf'},profile:{id},username:'787100'}:r.method==='export.start'?{export_id:'export'}:{};queueMicrotask(()=>native.onmessage({data:JSON.stringify({id:r.id,ok:true,value})}));}};
 const window={addEventListener(){},NativePortal:native,fetch:async()=>{if(!online)throw TypeError('Network failed');return new Response(JSON.stringify({owner:id}),{status});}};
 class Reader{readAsDataURL(blob){blob.arrayBuffer().then(bytes=>{this.result='data:application/octet-stream;base64,'+Buffer.from(bytes).toString('base64');this.onload();});}}
 const context={window,NativePortal:native,URL,location:{href:'https://testserver/tf',origin:'https://testserver'},Response,FileReader:Reader,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},console};vm.runInNewContext(source,context);
 return {window,calls,offline(){online=false;},status(s){status=s;}};}
(async()=>{
 let app=await boot(1);const path='/api/v1/tf/portal/plan/2026/10';assert.equal((await (await app.window.fetch(path)).json()).owner,1);await new Promise(r=>setTimeout(r,0));app.offline();assert.equal((await (await app.window.fetch(path)).json()).owner,1);assert.equal((await (await app.window.fetch('/api/v1/account/me')).json()).id,1);await assert.rejects(app.window.fetch('/api/v1/tf/work-reports',{method:'POST'}));
 app=await boot(2);app.offline();await assert.rejects(app.window.fetch(path));
 app=await boot(1);app.status(401);assert.equal((await app.window.fetch(path)).status,401);assert(app.calls.some(r=>r.method==='expired'));
 const blob=new Blob(['x'.repeat(120000)]);await app.window.AndroidPortal.saveBlob('test.gpx',blob);assert.equal(app.calls.filter(r=>r.method==='export.chunk').length,3);assert(app.calls.filter(r=>r.method==='export.chunk').every(r=>Buffer.from(r.data,'base64').length<=49152));assert.equal(app.calls.at(-1).method,'export.finish');
 console.log('Android portal: account-isolated offline cache, rejected writes, authoritative 401 and chunked export passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
