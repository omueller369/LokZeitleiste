"""Modulrechte: 0=keine, 1=lesen, 2=lesen/schreiben, 3=administrieren."""
import re
from fastapi import HTTPException
from sqlalchemy import select
from ..models import AccountPolicy, ModulePermission, User

MODULES = {"employees":"Mitarbeiter-Stammdaten", "planning":"Ruhetags- und Urlaubsplanung",
           "worktime":"Arbeitszeiterfassung und Korrekturen", "reports":"Monatsabrechnung und PDF-Versand",
           "staff":"Verwaltungsmitarbeiter und Berechtigungen", "directory":"Verwaltung: alle Mitarbeiter",
           "shifts":"Schichtmodelle und Zuweisungen", "email":"Tf-E-Mail-Postfächer"}


def password_required(db, user):
    policy = db.get(AccountPolicy, user.id)
    return bool(policy and policy.must_change_password)


def ready(db, user):
    if password_required(db, user):
        raise HTTPException(403, "Bitte zuerst Ihr Initialpasswort ändern.")


def permissions(db, user):
    if user.role == "admin":
        return {module:3 for module in MODULES}
    if user.role != "staff":
        return {module:0 for module in MODULES}
    stored = {p.module:p.level for p in db.scalars(select(ModulePermission).where(ModulePermission.user_id == user.id))}
    return {module:stored.get(module,0) for module in MODULES}


def demand(db, user, module, level):
    ready(db,user)
    if permissions(db,user).get(module,0) < level:
        raise HTTPException(403, "Keine ausreichende Freigabe für dieses Modul.")


def redact_plan(db,user,summary):
    if not permissions(db,user)['planning']:
        summary['planning'] = {key:value for key,value in summary['planning'].items() if key != 'days'}
    return summary


def authorize_route(db, user, request):
    path, method = request.url.path.rstrip('/'), request.method
    if path == '/api/v1/admin/logout':
        return
    ready(db,user)
    if path in ('/api/v1/admin/me','/api/v1/admin/modules'):
        return
    if path == '/api/v1/admin/tf' and method == 'GET':
        if not any(permissions(db,user)[m] for m in ('employees','planning','worktime','reports','directory','shifts','email')):
            raise HTTPException(403, "Keine Mitarbeiter-Module freigegeben.")
        return
    if path == '/api/v1/admin/directory' and method == 'GET':
        return demand(db,user,'directory',1)
    if path.startswith('/api/v1/admin/shifts/'):
        demand(db,user,'shifts',1 if method=='GET' else 2)
        if path.endswith(('/assign','/preview')):
            demand(db,user,'planning',2 if path.endswith('/assign') else 1)
        return
    if path.startswith('/api/v1/admin/email/'):
        return demand(db,user,'email',3 if path.endswith('/config') and method=='PUT' else 1 if method=='GET' else 2)
    if path == '/api/v1/admin/tf' and method == 'POST':
        return demand(db,user,'employees',3)
    if re.fullmatch(r'/api/v1/admin/tf/\d+/hours/\d+',path) and method == 'GET':
        levels = permissions(db,user)
        if not (levels['planning'] and (levels['worktime'] or levels['reports'])):
            raise HTTPException(403, 'Planung und Arbeitszeit oder Berichte müssen zum Lesen freigegeben sein.')
        return
    if re.fullmatch(r'/api/v1/admin/tf/\d+/photo',path):
        return demand(db,user,'employees',1 if method=='GET' else 2)
    if re.fullmatch(r'/api/v1/admin/staff/\d+/photo',path):
        return demand(db,user,'staff',1 if method=='GET' else 2)
    if path.startswith('/api/v1/admin/worktime/'):
        return demand(db,user,'worktime',1 if method=='GET' else 2)
    if path.startswith('/api/v1/admin/staff'):
        return demand(db,user,'staff',1 if method == 'GET' else 2 if method == 'PUT' else 3)
    if re.fullmatch(r'/api/v1/admin/accounts/\d+/reset-password',path) and method == 'POST':
        target = db.get(User,int(path.split('/')[-2]))
        if not target:
            raise HTTPException(404, "Konto nicht gefunden")
        return demand(db,user,'employees' if target.role == 'tf' else 'staff',3)
    if re.fullmatch(r'/api/v1/admin/tf/\d+',path) and method=='PUT':
        return demand(db,user,'employees',2)
    if re.fullmatch(r'/api/v1/admin/tf/\d+/delivery',path):
        return demand(db,user,'employees',1 if method == 'GET' else 2)
    if re.fullmatch(r'/api/v1/admin/tf/\d+/reports',path):
        return demand(db,user,'reports',1)
    if re.match(r'/api/v1/admin/tf/\d+/plan/',path):
        return demand(db,user,'planning',1 if method == 'GET' else 2)
    if re.match(r'/api/v1/admin/tf/\d+/worktime/',path):
        return demand(db,user,'worktime',1 if method == 'GET' else 2)
    if re.fullmatch(r'/api/v1/admin/tf/\d+/months(?:/\d+/\d+/(?:entries|summary))?',path) and method == 'GET':
        levels = permissions(db,user)
        if not (levels['worktime'] or levels['reports']):
            raise HTTPException(403, "Keine Freigabe für Monatsdaten.")
        return
    # Neue Endpunkte sind gesperrt, bis sie einem Modul zugeordnet wurden.
    raise HTTPException(403, "Endpunkt hat keine Modulfreigabe.")


def check_delegation(db, actor, requested, target=None):
    if actor.role == 'admin':
        return
    ceiling = permissions(db,actor)
    if target and (target.role != 'staff' or target.id == actor.id):
        raise HTTPException(403, "Dieses Konto darf nur ein Administrator verwalten.")
    if target and any(level > ceiling[module] for module,level in permissions(db,target).items()):
        raise HTTPException(403, "Das Konto hat Rechte außerhalb Ihrer Verwaltungsfreigabe.")
    if any(level > ceiling[module] for module,level in requested.items()):
        raise HTTPException(403, "Sie dürfen keine höheren Rechte als Ihre eigenen vergeben.")
