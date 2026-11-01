"""Conservative GPS stop detection. Missing fixes never imply a stop."""
import math

MAX_GAP=30_000
MAX_ACCURACY=50

def distance(a,b):
    lat1,lat2=map(math.radians,[a['lat'],b['lat']]);dl=math.radians(b['lon']-a['lon']);dp=lat2-lat1
    h=math.sin(dp/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dl/2)**2
    return 6371000*2*math.asin(min(1,math.sqrt(h)))

def bearing(a,b):
    p,q=map(math.radians,[a['lat'],b['lat']]);d=math.radians(b['lon']-a['lon'])
    return math.degrees(math.atan2(math.sin(d)*math.cos(q),math.cos(p)*math.sin(q)-math.sin(p)*math.cos(q)*math.cos(d)))%360

def analyse(points,preserved_starts=(),legacy=False,version2=False):
    rows=[];gaps=[];run=[];last=None
    def finish():
        if len(run)>1 and (run[-1]['t']-run[0]['t']>300_000 if legacy else run[-1]['t']-run[0]['t']>=240_000):
            rows.append(dict(key='s'+str(len(rows)),kind='Halt',start=run[0]['t'],end=run[-1]['t'],lat=run[0]['lat'],lon=run[0]['lon'],index=points.index(run[0])))
        run.clear()
    for index,point in enumerate(points):
        if last and point['t']-last['t']>MAX_GAP:
            finish();gaps.append(dict(start=last['t'],end=point['t'],reason='GPS-Lücke'))
        if point['accuracy']>MAX_ACCURACY:
            finish();gaps.append(dict(start=point['t'],end=point['t'],reason='GPS ungenau'));last=point;continue
        if version2 and run and 'live-'+str(point['t']) in preserved_starts:finish()
        speed=point.get('speed')
        if speed is None and last and last['accuracy']<=MAX_ACCURACY and 0<point['t']-last['t']<=MAX_GAP:
            speed=distance(last,point)/((point['t']-last['t'])/1000)
        if legacy:
            if speed is not None and speed*3.6<3:run.append(point)
            else:finish()
        elif run:
            if distance(run[0],point)<=100+1e-6:run.append(point)
            elif speed is not None and speed*3.6>5:finish()
        elif speed is not None and speed*3.6<3:run.append(point)
        last=point
    finish()
    good=[(i,p) for i,p in enumerate(points) if p['accuracy']<=MAX_ACCURACY]
    if good:
        first,last=good[0],good[-1]
        rows=[dict(key='start',kind='Start',start=first[1]['t'],end=first[1]['t'],lat=first[1]['lat'],lon=first[1]['lon'],index=first[0])]+rows+[dict(key='end',kind='Ende',start=last[1]['t'],end=last[1]['t'],lat=last[1]['lat'],lon=last[1]['lon'],index=last[0])]
    for row in rows:
        index=row.pop('index');origin=points[index];previous=next((p for p in reversed(points[:index]) if p['accuracy']<=MAX_ACCURACY and distance(p,origin)>=50),None)
        following=next((p for p in points[index+1:] if p['accuracy']<=MAX_ACCURACY and distance(origin,p)>=50),None)
        row['direction']=bearing(previous,origin) if previous else bearing(origin,following) if following else None
    return dict(rows=rows,gaps=gaps,points=len(points))

def candidates(row,stations):
    result=[]
    for station in stations:
        meters=distance(row,station)
        if meters<=5000:
            result.append(dict(station,distance_m=round(meters),direction_known=row['direction'] is not None))
    return sorted(result,key=lambda r:distance(row,r))[:1]
