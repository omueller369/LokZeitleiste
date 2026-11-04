"""Two installable web apps. A shared origin scope keeps account/documents inside the app."""
from .localization import source as _text_source, resolve_placeholders
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from PIL import Image

STATIC=Path(__file__).parent/'static'
APPS={'tf':(_text_source('server_pwa.text_875244874743'),'TF-Portal','/tf','#117d83'),
      'backend':(_text_source('server_pwa.text_b716e9d02951'),_text_source('server_pwa.text_2456bb8ed72f'),'/admin/start','#17445b')}

@lru_cache(maxsize=6)
def icon(area,size):
    # Shared RS freight mark: both independently installed apps use the selected brand.
    im=Image.open(STATIC/'rail-software-icon.png').convert('RGB')
    mark=im.resize((round(size*.8),round(size*.8)),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(size,size),'white');canvas.paste(mark,((size-mark.width)//2,(size-mark.height)//2))
    out=BytesIO();canvas.save(out,format='PNG');return out.getvalue()

def create_router():
    router=APIRouter()
    @router.get('/pwa/{area}/manifest.webmanifest')
    def manifest(area:Literal['tf','backend']):
        name,short,start,color=APPS[area]
        # Separate stable IDs allow both apps on one device. Shared modules require root scope.
        return JSONResponse(dict(id='/pwa/apps/'+area,name=name,short_name=short,start_url=start,
            scope='/',display='standalone',background_color='#eef3f5',theme_color=color,lang='de',
            description=name+_text_source('server_pwa.text_3a574fa974cf'),prefer_related_applications=False,
            icons=[dict(src=f'/pwa/{area}/icon-{size}.png'+'?v=20261104-rail-0263',sizes=f'{size}x{size}',type='image/png',purpose='any maskable') for size in (192,512)]),
            media_type='application/manifest+json',headers={'Cache-Control':'no-cache'})
    @router.get('/pwa/{area}/icon-{size}.png')
    def app_icon(area:Literal['tf','backend'],size:int):
        if size not in (180,192,512):raise HTTPException(404,_text_source('server_pwa.text_fdbc3fb065a2'))
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
        html=resolve_placeholders((STATIC/'pwa-install.html').read_text()).replace(_text_source('server_pwa.text_3d876c220a51'),name)
        metadata=f'<link id="ctlPwaManifest" rel="manifest" href="/pwa/{area}/manifest.webmanifest"><link rel="apple-touch-icon" href="/pwa/{area}/icon-180.png?v=20261104-rail-0263"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="{short}"><meta name="theme-color" content="{color}">'
        return HTMLResponse(html.replace('</head>',metadata+'</head>'),headers={'Cache-Control':'no-store'})
    return router
