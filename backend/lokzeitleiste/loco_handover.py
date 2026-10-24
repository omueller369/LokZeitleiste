"""Lokübergabebuch: read-only vehicle overview, backed by the vehicle master data."""
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .db import database_session
from .models import RailwayVehicle
from .vehicles import find_vehicles, VEHICLE_STATUSES
from .tf_portal import driver_dependency
from .leasing import assigned_company


def create_router(require_admin, require_account):
    router = APIRouter()
    require_driver = driver_dependency(require_account)

    @router.get('/admin/loco-handover')
    def page():
        return FileResponse(Path(__file__).parent/'static'/'loco-handover.html', headers={'Cache-Control':'no-cache'})

    @router.get('/tf/handover-protocols.js')
    def protocols_script():
        return FileResponse(Path(__file__).parent/'static'/'handover-protocols.js',media_type='text/javascript',headers={'Cache-Control':'no-cache'})

    @router.get('/tf/loco-handover.js')
    @router.get('/admin/loco-handover.js')
    def script():
        return FileResponse(Path(__file__).parent/'static'/'loco-handover.js', media_type='text/javascript', headers={'Cache-Control':'no-cache'})

    @router.get('/api/v1/tf/loco-handover/vehicles', dependencies=[Depends(require_driver)])
    @router.get('/api/v1/admin/loco-handover/vehicles', dependencies=[Depends(require_admin)])
    def listing(q:str=Query(default='',max_length=200), status:Literal['ready','unavailable','limited']|None=None,
                db:Session=Depends(database_session)):
        return [dict(id=row.id, vehicle_number=row.vehicle_number, name=row.name, status=row.status,
                     status_label=VEHICLE_STATUSES[row.status][0], status_note=row.status_note)
                for row in find_vehicles(db,q,status)]

    @router.get('/api/v1/tf/loco-handover/vehicles/{vehicle_id}', dependencies=[Depends(require_driver)])
    @router.get('/api/v1/admin/loco-handover/vehicles/{vehicle_id}', dependencies=[Depends(require_admin)])
    def details(vehicle_id:int, db:Session=Depends(database_session)):
        row=db.get(RailwayVehicle,vehicle_id)
        if not row:raise HTTPException(404,'Triebfahrzeug nicht gefunden.')
        label,color=VEHICLE_STATUSES[row.status]
        company=assigned_company(db,row.id)
        return dict(id=row.id,vehicle_number=row.vehicle_number,name=row.name,series=row.series,
                    status=row.status,status_label=label,status_color=color,
                    status_note=row.status_note if row.status!='ready' else '',
                    leasing_company=company.company if company else row.lessor,
                    leasing_email=company.email if company else '',
                    hotline=company.hotline if company else row.hotline)

    return router
