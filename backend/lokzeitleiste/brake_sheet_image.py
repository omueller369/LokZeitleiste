"""Deterministic raster preview on the clean bilingual international form template."""
import io,os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image,ImageDraw,ImageFont
import reportlab

TEMPLATE=Path(__file__).parent/'assets'/'brake-sheet-template.png'
@lru_cache(maxsize=48)
def font(size):
    root=Path(os.getenv('LOKZEITLEISTE_FONT_DIR','/usr/share/fonts/truetype/dejavu'))
    path=root/'DejaVuSans.ttf'
    if not path.exists():path=Path(reportlab.__file__).parent/'fonts'/'Vera.ttf'
    return ImageFont.truetype(str(path),size)

def formatted(value):
    if value is None:return ''
    if isinstance(value,str):return value
    return format(Decimal(str(value)).normalize(),'f').replace('.',',')

def render(sheet,result,created_at,created_by):
    with Image.open(TEMPLATE) as source:image=source.convert('RGB')
    draw=ImageDraw.Draw(image);sx=image.width/1335;sy=image.height/1888
    def box(rect,value,size=18,align='center',minimum=6,valign='center'):
        text=formatted(value)
        if not text:return
        x1,y1,x2,y2=rect;x1=round(x1*sx);x2=round(x2*sx);y1=round(y1*sy);y2=round(y2*sy)
        width=x2-x1-6;height=y2-y1-4
        for logical in range(size,minimum-1,-1):
            f=font(max(8,round(logical*sy)));lines=[]
            for paragraph in text.split('\n'):
                current=''
                for word in paragraph.split(' '):
                    proposed=(current+' '+word).strip()
                    if draw.textlength(proposed,font=f)<=width:current=proposed;continue
                    if current:lines.append(current);current=''
                    for char in word:
                        if current and draw.textlength(current+char,font=f)>width:lines.append(current);current=''
                        current+=char
                lines.append(current)
            step=round(logical*sy*1.22)
            if len(lines)*step<=height and all(draw.textlength(line,font=f)<=width for line in lines):break
        else:raise ValueError('Text passt nicht in das Formularfeld. Bitte die Eingabe kürzen.')
        top=y1+2 if valign=='top' else y1+(height-len(lines)*step)//2+2
        for line in lines:
            left=x1+3 if align=='left' else x1+(x2-x1-draw.textlength(line,font=f))/2
            draw.text((left,top),line,font=f,fill='black',anchor='lt');top+=step
    def cross(x,y):
        x*=sx;y*=sy;d=6*sx
        draw.line((x-d,y-d,x+d,y+d),fill='black',width=max(2,round(1.7*sx)))
        draw.line((x-d,y+d,x+d,y-d),fill='black',width=max(2,round(1.7*sx)))
    date=sheet.departure_date.strftime('%d.%m.%Y')
    box((860,30,939,56),sheet.train_numbers[0],14)
    box((1172,29,1269,57),date,13)
    box((12,157,203,182),sheet.issuer)
    box((210,157,380,183),' / '.join(n for n in sheet.train_numbers if n),16)
    box((387,157,619,182),date)
    box((12,210,316,236),sheet.station_from,15)
    box((323,210,619,236),sheet.station_to,15)
    columns=[(806,966),(973,1051),(1059,1129),(1138,1206)]
    for country,(left,right) in zip(sheet.countries,columns):
        if not country.country:continue
        box((left,102,right,133),country.country)
        box((left,141,right,181),country.category)
        box((left,190,right,235),country.vmax)
    # ETCS (1212..1304), the second section and verification fields are untouched.
    box((16,303,574,591),sheet.remarks,17,'left',valign='top')
    box((590,303,1295,591),sheet.special,17,'left',valign='top')
    for active,y in [(sheet.dangerous,619),(sheet.exceptional,649),(sheet.restrictions,697),(sheet.waste,768)]:
        if active:cross(27,y)
    box((381,627,598,654),sheet.station_from,14)
    box((607,627,833,654),sheet.station_to,14)
    def vehicle(number):return f'{number[:2]} {number[2:4]} {number[4:8]} {number[8:11]}-{number[11:]}'
    box((382,701,598,732),vehicle(sheet.first_vehicle),15)
    box((608,701,833,732),vehicle(sheet.last_vehicle),15)
    xs=[(382,527),(534,691),(698,835)];ys=[(860,896),(905,939),(947,992),(1002,1037),(1047,1081)]
    for key,(top,bottom) in zip(['count','length','holding','brake','weight'],ys):
        for values,(left,right) in zip([result['a'],result['b'],result['total']],xs):box((left,top,right,bottom),values[key],20)
    if sheet.holding_unit:cross(169 if sheet.holding_unit=='t' else 212,980)
    de=f'DE: {sheet.class_de} – 22,5 t';pl=f'PL: {sheet.class_pl} – '+('20,5 t' if sheet.class_pl=='C' else '22,5 t')
    box((15,1149,190,1233),de+'\n'+pl,14)
    cross(237,{'G':1139,'P':1159,'G+P':1179,'LL+P':1199,'R':1219}[sheet.brake_mode])
    for value,(top,bottom) in zip([result['available'],sheet.required_percent,result['missing'],'/'],[(1090,1131),(1140,1181),(1190,1235),(1245,1322)]):box((699,top,834,bottom),value,23)
    bounds=[(90,380),(388,471),(480,559),(568,663),(673,755),(765,833),(843,905),(915,975),(985,1049),(1061,1298)]
    used_units=set()
    for i,line in enumerate(result['lines']):
        top=1510+i*40;bottom=top+32
        values=[line['vehicle_number'],line['series'],line['axle_count'],line['length_m'],line['weight_kg'],line['brake_shoe'],line['position'],line['brake_weight'],str(line['spring_brake'])+' '+line['spring_unit'],line['note']]
        for value,(left,right) in zip(values,bounds):box((left,top,right,bottom),value,16)
        used_units.add(line['spring_unit'])
    for unit in used_units:cross(1001 if unit=='t' else 1042,1488)
    local=created_at.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Berlin'))
    box((15,1751,259,1771),local.strftime('%d.%m.%Y'),14)
    box((269,1751,493,1771),local.strftime('%H:%M'),14)
    box((502,1751,885,1771),created_by,14)
    output=io.BytesIO();image.save(output,format='PNG',optimize=True);return output.getvalue()
