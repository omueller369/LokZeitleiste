"""Permission-filtered landing page, available to every backend account."""
from .localization import source as _text_source
from pathlib import Path
from fastapi import APIRouter,Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .db import database_session
from .accounts.access import permissions
from .models import StaffProfile


def start_modules(user,p):
    employees=any(p.get(key,0) for key in ('employees','planning','worktime','reports','directory','shifts','email'))
    definitions=[
        ('tf',_text_source('server_backend_start.text_e9820ba217c3'),'/admin/tf',_text_source('server_backend_start.text_2456bb8ed72f'),p.get('employees',0) or int(employees)),
        ('staff',_text_source('server_backend_start.text_20e987b4a823'),'/admin/staff',_text_source('server_backend_start.text_2456bb8ed72f'),p.get('staff',0)),
        ('directory',_text_source('server_backend_start.text_143327b1cce7'),'/admin/directory',_text_source('server_backend_start.text_2456bb8ed72f'),p.get('directory',0)),
        ('planning',_text_source('server_backend_start.text_67f08af53537'),'/admin/planning',_text_source('server_backend_start.text_b702020127a6'),p.get('planning',0)),
        ('overview',_text_source('server_backend_start.text_8d19db2dc6b2'),'/admin/rest-plans',_text_source('server_backend_start.text_b702020127a6'),p.get('planning',0)),
        ('shifts',_text_source('server_backend_start.text_77ecaf5660bb'),'/admin/shifts',_text_source('server_backend_start.text_b702020127a6'),p.get('shifts',0)),
        ('loco_handover',_text_source('server_backend_start.text_2f571b7ba8ad'),'/admin/loco-handover',_text_source('server_backend_start.text_9f3d5f8d94cf'),p.get('loco_handover',0)),
        ('leasing',_text_source('server_backend_start.text_a23174dc39c0'),'/admin/leasing',_text_source('server_backend_start.text_c78f95997238'),p.get('leasing',0)),
        ('vehicles',_text_source('server_backend_start.text_e76efaf41a3e'),'/admin/vehicles',_text_source('server_backend_start.text_c78f95997238'),p.get('vehicles',0)),
        ('app_defaults',_text_source('server_backend_start.text_cb5129c1d8f0'),'/admin/app-defaults',_text_source('server_backend_start.text_c78f95997238'),p.get('app_defaults',0)),
        ('worktime',_text_source('server_backend_start.text_dd4fd942cb88'),'/admin/worktime',_text_source('server_backend_start.text_9f3d5f8d94cf'),p.get('worktime',0)),
        ('reports',_text_source('server_backend_start.text_1948beff57ad'),'/admin/tf',_text_source('server_backend_start.text_9f3d5f8d94cf'),p.get('reports',0)),
        ('roster',_text_source('server_backend_start.text_4c6e6372b010'),'/admin/planning?readonly=1',_text_source('server_backend_start.text_b702020127a6'),min(1,p.get('planning',0))),
        ('hours',_text_source('server_backend_start.text_09d2cf5dc984'),'/admin/tf/hours',_text_source('server_backend_start.text_b702020127a6'),1 if p.get('planning',0) and (p.get('worktime',0) or p.get('reports',0)) else 0),
        ('email',_text_source('server_backend_start.text_969ccbd3cf63'),'/admin/email',_text_source('server_backend_start.text_9f3d5f8d94cf'),p.get('email',0)),
        ('messages',_text_source('server_backend_start.text_73e0cf4b6d15'),'/admin/messages',_text_source('server_backend_start.text_824543888534'),2),
        ('documents',_text_source('server_backend_start.text_52b5952bea66'),'/documents',_text_source('server_backend_start.text_824543888534'),2),
        ('password',_text_source('server_backend_start.text_b4d616199968'),'/admin/me',_text_source('server_backend_start.text_824543888534'),2),
    ]
    if user.role=='admin':definitions.extend([('phpmyadmin','phpMyAdmin','/phpmyadmin',_text_source('server_backend_start.text_4b42c6690ebe'),3),('webmailer',_text_source('server_backend_start.text_99ed27bf3bdb'),'/webmailer',_text_source('server_backend_start.text_4b42c6690ebe'),3)])
    if user.role=='staff':definitions.append(('own_time',_text_source('server_backend_start.text_e71e0296d76b'),'/my/worktime',_text_source('server_backend_start.text_824543888534'),2))
    return [dict(id=id,label=label,url=url,group=group,level=level,new_tab=id in ('phpmyadmin','webmailer')) for id,label,url,group,level in definitions if level]


def create_router(require_admin):
    router=APIRouter()
    @router.get('/admin/start')
    def page():return FileResponse(Path(__file__).parent/'static'/'backend-start.html')
    @router.get('/admin/backend-start.js')
    def script():return FileResponse(Path(__file__).parent/'static'/'backend-start.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})
    @router.get('/admin/menu-designs')
    def designs():return FileResponse(Path(__file__).parent/'static'/'menu-designs.html')
    @router.get('/api/v1/admin/start')
    def data(user=Depends(require_admin),db:Session=Depends(database_session)):
        profile=db.get(StaffProfile,user.id) if user.role=='staff' else None
        name=(profile.first_name+' '+profile.last_name).strip() if profile else user.username
        modules=start_modules(user,permissions(db,user))
        return dict(name=name,modules=modules,admin_tools=[row for row in modules if row['id'] in ('phpmyadmin','webmailer')] if user.role=='admin' else [])
    return router

