"""Transactional audit of authenticated employee changes; no public listing endpoint."""
import hashlib,json,re
from datetime import date,datetime
from sqlalchemy import event,inspect
from sqlalchemy.orm import Session
from .models import SystemChangeLog,StaffProfile,TfProfile

SKIP={'system_change_log','system_migrations','planning_note_backup','session_tokens','account_audits','plan_changes','plan_duty_audits','work_time_changes'}
SECRET=re.compile(r'password|secret|token|credential|encrypted|private_key',re.I)
def safe(value,key=''):
    if SECRET.search(key):return '[geschützt]'
    if isinstance(value,str) and key.endswith('_json'):
        try:return safe(json.loads(value))
        except (ValueError,TypeError):pass
    if isinstance(value,bytes):return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
    if isinstance(value,(date,datetime)):return value.isoformat()
    if isinstance(value,dict):return {str(k):safe(v,str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)
def bind_actor(db,user,request):
    if db.info.get('change_actor'):return
    profile=db.get(TfProfile if user.role=='tf' else StaffProfile,user.id)
    name=f'{profile.first_name} {profile.last_name}' if profile else user.username
    path=request.url.path
    if '/plan/' in path or '/planning/' in path:module='Arbeitszeitplanung'
    elif '/work-reports' in path:module='Arbeitsbericht'
    else:
        labels=[('app-defaults','App Grundwerte'),('loco-handover','Lokübergabebuch'),('vehicles','Triebfahrzeuge'),('leasing','Lok-Leasing'),('documents','Dokumentenverwaltung'),('stations','Bahnhöfe'),('email','Email'),('worktime','Arbeitszeit'),('shifts','Schichtplan'),('account','Benutzerkonto'),('/admin/staff','Verwaltungsmitarbeiter'),('/admin/tf','TF-Stammdaten')]
        module=next((label for key,label in labels if key in path),path.removeprefix('/api/v1/')[:255])
    db.info['change_actor']={'employee_id':user.id,'employee':name,'module':module,'username':user.username}

def add_record(db,actor,change):
    db.add(SystemChangeLog(employee_id=actor['employee_id'],employee=actor['employee'],module=actor['module'],change=json.dumps(safe(change),ensure_ascii=False,default=str)))

@event.listens_for(Session,'before_flush')
def capture(db,context,instances):
    actor=db.info.get('change_actor')
    if not actor:return
    pending=db.info.setdefault('change_pending',[])
    for obj in list(db.new)+list(db.dirty)+list(db.deleted):
        state=inspect(obj);table=state.mapper.local_table.name
        if table in SKIP:continue
        action='löschen' if obj in db.deleted else 'anlegen' if obj in db.new else 'ändern'
        values={}
        for column in state.mapper.column_attrs:
            history=state.attrs[column.key].history
            if action=='ändern' and not history.has_changes():continue
            if action=='löschen':values[column.key]={'vorher':safe(getattr(obj,column.key),column.key),'nachher':None}
            else:values[column.key]={'vorher':safe(history.deleted[0],column.key) if history.deleted else None,'nachher':safe(getattr(obj,column.key),column.key)}
        if values:pending.append((obj,dict(actor),{'tabelle':table,'aktion':action,'felder':values}))

@event.listens_for(Session,'after_flush_postexec')
def persist(db,context):
    for obj,actor,change in db.info.pop('change_pending',[]):
        change['datensatz']=list(inspect(obj).identity or [])
        if change['aktion']=='anlegen':
            for key,value in change['felder'].items():value['nachher']=safe(getattr(obj,key),key)
        add_record(db,actor,change)

@event.listens_for(Session,'after_soft_rollback')
def discard(db,previous):db.info.pop('change_pending',None)

@event.listens_for(Session,'do_orm_execute',retval=True)
def bulk_changes(state):
    actor=state.session.info.get('change_actor')
    typed=state.is_update or state.is_delete or state.is_insert
    from sqlalchemy.sql.elements import TextClause
    raw=re.match(r'\s*(UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+[`"]?(\w+)',str(state.statement),re.I) if isinstance(state.statement,TextClause) else None
    if not actor or not (typed or raw):return state.invoke_statement()
    table=getattr(getattr(state.statement,'table',None),'name','') or (raw.group(2) if raw else '')
    result=state.invoke_statement()
    if table and table not in SKIP:
        change={'tabelle':table,'aktion':'Sammeländerung','betroffene_zeilen':getattr(result,'rowcount',None)}
        if typed:change['parameter']=safe(state.statement.compile().params)
        add_record(state.session,actor,change)
    return result
