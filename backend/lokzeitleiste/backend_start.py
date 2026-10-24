"""Permission-filtered landing page, available to every backend account."""
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
        ('tf','TFs (Liste)','/admin/tf','Verwaltung',p.get('employees',0) or int(employees)),
        ('staff','Verwaltungsmitarbeiter (Liste)','/admin/staff','Verwaltung',p.get('staff',0)),
        ('directory','Alle Mitarbeiter','/admin/directory','Verwaltung',p.get('directory',0)),
        ('planning','Arbeitszeitplanung','/admin/planning','Personalplanung',p.get('planning',0)),
        ('overview','TF-Übersicht','/admin/planning?overview=all','Personalplanung',p.get('planning',0)),
        ('shifts','Schichtplan','/admin/shifts','Personalplanung',p.get('shifts',0)),
        ('loco_handover','Lokübergabebuch','/admin/loco-handover','Sonstiges',p.get('loco_handover',0)),
        ('vehicles','Triebfahrzeuge','/admin/vehicles','Stammdaten',p.get('vehicles',0)),
        ('app_defaults','App Grundwerte','/admin/app-defaults','Stammdaten',p.get('app_defaults',0)),
        ('worktime','Arbeitszeiterfassung und Korrekturen','/admin/worktime','Sonstiges',p.get('worktime',0)),
        ('reports','Monatsabrechnung und PDF-Versand','/admin/tf','Sonstiges',p.get('reports',0)),
        ('roster','Dienstplan','/admin/planning?readonly=1','Personalplanung',min(1,p.get('planning',0))),
        ('hours','Dienstzeit','/admin/tf/hours','Personalplanung',1 if p.get('planning',0) and (p.get('worktime',0) or p.get('reports',0)) else 0),
        ('email','Email','/admin/email','Sonstiges',p.get('email',0)),
        ('documents','Meine Dokumente','/documents','Mein Bereich',2),
        ('password','Mein Passwort ändern','/account','Mein Bereich',2),
    ]
    if user.role=='admin':definitions.extend([('phpmyadmin','phpMyAdmin','/phpmyadmin','Administration',3),('webmailer','Webmailer','/webmailer','Administration',3)])
    if user.role=='staff':definitions.append(('own_time','Meine Arbeitszeiten','/my/worktime','Mein Bereich',2))
    return [dict(id=id,label=label,url=url,group=group,level=level) for id,label,url,group,level in definitions if level]


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
        return dict(name=name,modules=start_modules(user,permissions(db,user)))
    return router

