"""One-time removal of current TF planning notes, retaining a private backup."""
from sqlalchemy import select
from ..models import PlanDay,PlanMonth,SystemMigration,PlanningNoteBackup,SystemChangeLog
import json
KEY='clear-planning-notes-20261025-v1'
def migrate(db):
    if db.get(SystemMigration,KEY):return 0
    count=0;periods=set()
    for day,month in db.execute(select(PlanDay,PlanMonth).join(PlanMonth,PlanDay.plan_month_id==PlanMonth.id).where(PlanDay.note!='')):
        old=day.note;db.add(PlanningNoteBackup(plan_day_id=day.id,tf_id=month.tf_user_id,day=day.day,note=old))
        db.add(SystemChangeLog(module='Arbeitszeitplanung · Update',employee_id=None,employee='System (Update)',change=json.dumps({'aktion':'Alte Planungsnotiz löschen','tf_id':month.tf_user_id,'datum':day.day.isoformat(),'vorher':old,'nachher':''},ensure_ascii=False)))
        day.note='';periods.add(month);count+=1
    for month in periods:month.revision+=1
    db.add(SystemMigration(key=KEY));db.flush();return count
