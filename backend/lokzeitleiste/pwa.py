"""Two installable web apps. A shared origin scope keeps account/documents inside the app."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from PIL import Image, ImageDraw, ImageChops

STATIC=Path(__file__).parent/'static'
APPS={'tf':('LokZeitleiste TF-Portal','TF-Portal','/tf','#117d83'),
      'backend':('LokZeitleiste Verwaltung','Verwaltung','/admin/start','#17445b')}

@lru_cache(maxsize=6)
def icon(area,size):
    color=APPS[area][3];scale=2;im=Image.new('RGB',(size*scale,size*scale),color)
    d=ImageDraw.Draw(im);s=size*scale
    def box(coords,fill):d.rectangle(tuple(round(v*s) for v in coords),fill=fill)
    if area=='tf':
        logo=Image.open(STATIC/'ctl-logistics-logo.jpg').convert('RGB')
        bounds=ImageChops.difference(logo,Image.new('RGB',logo.size,'white')).convert('L').point(lambda v:255 if v>30 else 0).getbbox()
        if bounds:logo=logo.crop(bounds)
        im=Image.new('RGB',(size,size),'white');logo.thumbnail((int(size*.76),int(size*.76)),Image.Resampling.LANCZOS);im.paste(logo,((size-logo.width)//2,(size-logo.height)//2));out=BytesIO();im.save(out,format='PNG');return out.getvalue()
    else:
        d.polygon([(s*.24,s*.33),(s*.5,s*.18),(s*.76,s*.33)],fill='white')
        box((.26,.35,.74,.72),'white');box((.23,.75,.77,.81),'white')
        for x in [.32,.47,.62]:
            for y in [.41,.55]:box((x,y,x+.07,y+.08),color)
    out=BytesIO();im.resize((size,size),Image.Resampling.LANCZOS).save(out,format='PNG');return out.getvalue()

def create_router():
    router=APIRouter()
    @router.get('/pwa/{area}/manifest.webmanifest')
    def manifest(area:Literal['tf','backend']):
        name,short,start,color=APPS[area]
        # Separate stable IDs allow both apps on one device. Shared modules require root scope.
        return JSONResponse(dict(id='/pwa/apps/'+area,name=name,short_name=short,start_url=start,
            scope='/',display='standalone',background_color='#eef3f5',theme_color=color,lang='de',
            description=name+' auf dem Mobilgerät',prefer_related_applications=False,
            icons=[dict(src=f'/pwa/{area}/icon-{size}.png'+('?v=20261026-ctl' if area=='tf' else ''),sizes=f'{size}x{size}',type='image/png',purpose='any maskable') for size in (192,512)]),
            media_type='application/manifest+json',headers={'Cache-Control':'no-cache'})
    @router.get('/pwa/{area}/icon-{size}.png')
    def app_icon(area:Literal['tf','backend'],size:int):
        if size not in (180,192,512):raise HTTPException(404,'Symbol nicht gefunden.')
        return Response(icon(area,size),media_type='image/png',headers={'Cache-Control':'public, max-age=86400'})
    @router.get('/pwa/install.js')
    def script():return FileResponse(STATIC/'pwa-install.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/pwa/install.css')
    def styles():return FileResponse(STATIC/'pwa-install.css',media_type='text/css',headers={'Cache-Control':'no-cache'})
    @router.get('/pwa-sw.js')
    def worker():return FileResponse(STATIC/'pwa-sw.js',media_type='text/javascript',headers={'Cache-Control':'no-cache','Service-Worker-Allowed':'/'})
    @router.get('/tf/install')
    @router.get('/admin/install')
    def installation(request:Request):
        area='tf' if request.url.path.startswith('/tf/') else 'backend'
        name,short,start,color=APPS[area]
        html=(STATIC/'pwa-install.html').read_text().replace('App installieren · LokZeitleiste',name)
        metadata=f'<link id="ctlPwaManifest" rel="manifest" href="/pwa/{area}/manifest.webmanifest"><link rel="apple-touch-icon" href="/pwa/{area}/icon-180.png?v=20261026-ctl"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="{short}"><meta name="theme-color" content="{color}">'
        return HTMLResponse(html.replace('</head>',metadata+'</head>'),headers={'Cache-Control':'no-store'})
    return router
