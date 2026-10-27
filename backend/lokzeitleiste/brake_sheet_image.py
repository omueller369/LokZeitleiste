"""Deterministic raster preview on the clean bilingual international form template."""
import io,os,re
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
    path=root/'DejaVuSans-Bold.ttf'
    if not path.exists():path=Path(reportlab.__file__).parent/'fonts'/'VeraBd.ttf'
    return ImageFont.truetype(str(path),size)

def formatted(value):
    if value is None:return ''
    if isinstance(value,str):return value
    return format(Decimal(str(value)).normalize(),'f').replace('.',',')

def station_name(value):
    """Hide the DS100 prefix in output, retaining manually entered station names."""
    text=value.strip()
    match=re.fullmatch(r'[A-Za-z0-9]{1,10}\s*·\s*(.+)',text)
    return match.group(1).strip() if match else text

def field40_name(image,name):
    """Identical left-aligned name layout for the drawing guide and final form."""
    draw=ImageDraw.Draw(image);sx=image.width/1335;sy=image.height/1888;logical=14
    while logical>6 and draw.textlength(name,font=font(round(logical*sy)))>196*sx-6:logical-=1
    f=font(round(logical*sy));step=round(logical*sy*1.22)
    x=round(502*sx)+3;y=round(1751*sy)+(round(1771*sy)-round(1751*sy)-4-step)//2+2
    draw.text((x,y),name,font=f,fill='black',anchor='lt')
    tail_width=draw.textlength(name[-3:],font=f)
    end=x+draw.textlength(name,font=f)
    return max(502,(end-tail_width)/sx-5)

def render(sheet,result,created_at,created_by,transparent=False,signature=None,signature_position=None):
    with Image.open(TEMPLATE) as source:
        image=Image.new('RGBA',source.size,(255,255,255,0)) if transparent else source.convert('RGB')
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
            left=x1+3 if align=='left' else x2-3-draw.textlength(line,font=f) if align=='right' else x1+(x2-x1-draw.textlength(line,font=f))/2
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
    box((12,210,316,236),station_name(sheet.station_from),15)
    box((323,210,619,236),station_name(sheet.station_to),15)
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
    box((381,627,598,654),station_name(sheet.station_from),14)
    box((607,627,833,654),station_name(sheet.station_to),14)
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
    if signature:
        # Field 40: printed name left; transparent signature right with a small inset.
        field40_name(image,created_by)
        with Image.open(io.BytesIO(signature)) as source:ink=source.convert('RGBA')
        bounds=ink.getchannel('A').getbbox()
        if bounds:ink=ink.crop(bounds)
        if signature_position:
            x,y,w,h=signature_position
            ink=ink.resize((max(1,round(w*sx)),max(1,round(h*sy))),Image.Resampling.LANCZOS)
            destination=(round(x*sx),round(y*sy))
        else:
            left,top,right,bottom=[round(v*scale) for v,scale in [(702,sx),(1732,sy),(886,sx),(1773,sy)]]
            scale=min((right-left)/ink.width,(bottom-top)/ink.height)
            ink=ink.resize((max(1,round(ink.width*scale)),max(1,round(ink.height*scale))),Image.Resampling.LANCZOS)
            destination=(right-ink.width,top+(bottom-top-ink.height)//2)
        if image.mode=='RGBA':image.alpha_composite(ink,destination)
        else:image.paste(ink,destination,ink)
    else:box((502,1751,885,1771),created_by,14)
    output=io.BytesIO();image.save(output,format='PNG',optimize=True);return output.getvalue()


def render_pdf(sheet,result,created_at,created_by,signature=None,signature_position=None):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from pypdf import PdfReader,PdfWriter
    overlay=io.BytesIO();document=canvas.Canvas(overlay,pagesize=A4,invariant=1,pageCompression=1)
    pixels=render(sheet,result,created_at,created_by,transparent=True,signature=signature,signature_position=signature_position)
    document.drawImage(ImageReader(io.BytesIO(pixels)),0,0,width=A4[0],height=A4[1],mask='auto')
    document.showPage();document.save();overlay.seek(0)
    source=PdfReader(TEMPLATE.with_suffix('.pdf'));writer=PdfWriter();writer.clone_document_from_reader(source)
    writer.pages[0].merge_page(PdfReader(overlay).pages[0])
    writer.add_metadata({'/Title':'Bremszettel '+sheet.train_numbers[0],'/Author':created_by,'/CreationDate':created_at.strftime('D:%Y%m%d%H%M%SZ')})
    output=io.BytesIO();writer.write(output);return output.getvalue()
