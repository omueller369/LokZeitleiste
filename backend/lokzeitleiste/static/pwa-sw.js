/* Network only: never cache authenticated pages, API responses, files or credentials. */
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||event.request.mode!=='navigate'||url.origin!==self.location.origin||!/^\/(tf|admin|account|documents|my\/worktime)(\/|$)/.test(url.pathname))return;
 event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LokZeitleiste · Offline</title><body style="font:18px system-ui;padding:24px"><h1>Keine Verbindung</h1><p>Zum Öffnen der Anwendung wird eine Internetverbindung benötigt. Bereits lokal gespeicherte Arbeitsberichte bleiben im Browser erhalten.</p><p>Bitte die Verbindung prüfen und die Seite erneut laden.</p><a href="">Erneut versuchen</a></body></html>',{status:503,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})));
});
