"""Sharp vector A5 national freight brake sheet plus matching image preview."""
from .localization import source as _text_source
import io,os
from decimal import Decimal
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR=Path(os.getenv('LOKZEITLEISTE_FONT_DIR','/usr/share/fonts/truetype/dejavu'))
def font_path(bold=False):
    path=FONT_DIR/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    if not path.is_file():
        import reportlab
        path=Path(reportlab.__file__).parent/'fonts'/('VeraBd.ttf' if bold else 'Vera.ttf')
    return str(path)
def fmt(v):
    if v is None:return ''
    if isinstance(v,(int,Decimal,float)):return format(Decimal(str(v)).normalize(),'f').replace('.',',')
    return str(v)
class Drawing:
    def __init__(self,image):
        self.image=image;self.buffer=io.BytesIO();self.scale=4
        for name,bold in [(_text_source('server_national_brake_image.text_865b30e2fae6'),False),('NationalBold',True)]:
            if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,font_path(bold)))
        if image:self.im=Image.new('RGB',(1680,2380),'white');self.d=ImageDraw.Draw(self.im)
        else:
            for name,bold in [(_text_source('server_national_brake_image.text_865b30e2fae6'),False),('NationalBold',True)]:
                if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,font_path(bold)))
            self.c=canvas.Canvas(self.buffer,pagesize=(420,595),invariant=1);self.c.setTitle(_text_source('server_national_brake_image.text_e476dac82992'))
    def line(self,x1,y1,x2,y2,width=.5):
        if self.image:self.d.line([(round(x1*4),round(y1*4)),(round(x2*4),round(y2*4))],fill='black',width=max(1,round(width*4)))
        else:self.c.setLineWidth(width);self.c.line(x1,595-y1,x2,595-y2)
    def strike(self,x,y,w,h):self.line(x+2,y+h-2,x+w-2,y+2,.6)
    def text(self,x,y,text,size=7,bold=False,maxwidth=None,color="black"):
        text=fmt(text)
        if not text:return
        while True:
            if self.image:
                font=ImageFont.truetype(font_path(bold),round(size*4));width=self.d.textlength(text,font=font)/4
            else:width=pdfmetrics.stringWidth(text,'NationalBold' if bold else _text_source('server_national_brake_image.text_865b30e2fae6'),size)
            if maxwidth is None or width<=maxwidth:break
            size-=.25
            if size<4.5:raise ValueError(_text_source('server_national_brake_image.text_aede3a2dff2a'))
        if self.image:self.d.text((round(x*4),round(y*4)),text,fill=color,font=font,anchor='lt')
        else:self.c.setFillColor(color);self.c.setFont('NationalBold' if bold else _text_source('server_national_brake_image.text_865b30e2fae6'),size);self.c.drawString(x,595-y-size*.8,text)
    def centered(self,x,y,w,h,value,size=7,bold=False,color="black"):
        text=fmt(value)
        if not text:return
        name='NationalBold' if bold else _text_source('server_national_brake_image.text_865b30e2fae6')
        while pdfmetrics.stringWidth(text,name,size)>w-4:
            size-=.25
            if size<4.5:raise ValueError(_text_source('server_national_brake_image.text_aede3a2dff2a'))
        if self.image:
            font=ImageFont.truetype(font_path(bold),round(size*4))
            box=self.d.textbbox((0,0),text,font=font,anchor='lt')
            self.d.text(((x+w/2)*4-(box[0]+box[2])/2,(y+h/2)*4-(box[1]+box[3])/2),text,font=font,fill=color,anchor='lt')
        else:
            ascent,descent=pdfmetrics.getAscentDescent(name,size)
            self.c.setFillColor(color);self.c.setFont(name,size)
            self.c.drawCentredString(x+w/2,595-(y+h/2)-(ascent+descent)/2,text)
    def finish(self):
        if self.image:self.im.save(self.buffer,format='PNG',dpi=(288,288))
        else:self.c.showPage();self.c.save()
        return self.buffer.getvalue()

def render(sheet,result,creator,image=False):
    d=Drawing(image);left,right=12,408;xs=[12,62,82,278,320,364,408]
    d.line(left,10,right,10,1);d.line(left,10,left,85,1);d.line(right,10,right,85,1)
    d.text(17,17,_text_source('server_national_brake_image.text_3309282eccb7'),14,True);d.text(183,20,_text_source('server_national_brake_image.text_b5119e0b2ad5')+sheet.departure_date.strftime('%d.%m.%Y'),7)
    trains=[t for t in sheet.trains if t.number]
    d.line(left,36,right,36)
    if len(trains)<=3:
        d.centered(12,36,278,13,'Zugnummer(n)',7,True);d.centered(290,36,118,13,_text_source('server_national_brake_image.text_672de87511ac'),7,True);d.line(290,36,290,85)
    else:d.text(17,40,_text_source('server_national_brake_image.text_22cc39a34733'),7,True)
    # Keep each DS100 paired with its train; up to 20 pairs fit as four compact columns.
    if len(trains)<=3:
        for i,t in enumerate(trains):
            height=34/max(1,len(trains));d.centered(12,51+i*height,278,height,t.number);d.centered(290,51+i*height,118,height,t.station)
    else:
        for i,t in enumerate(trains):
            col=i//5;row=i%5;x=17+col*97
            d.centered(x,49+row*7,93,7,t.number+' / '+t.station)
    d.line(left,85,right,85,1)
    top=90
    for x in xs:
        if x in (320,364):
            d.line(x,top,x,226)
            if x==320:d.line(x,243,x,397)
            else:d.line(x,313,x,329);d.line(x,367,x,397)
        else:d.line(x,top,x,397)
    d.line(left,top,right,top,1);d.line(left,126,right,126,1)
    for i,x in enumerate(xs[:-1]):d.centered(x,90,xs[i+1]-x,12,str(i+1),6,True)
    d.text(64,108,_text_source('server_national_brake_image.text_e3ee87b136fa'),6.5,True);d.text(148,108,_text_source('server_national_brake_image.text_97d1e68526b8'),8,True)
    d.text(282,108,_text_source('server_national_brake_image.text_c22504e9564e'),6.2,True);d.text(324,103,'arbeitende',6,True);d.text(326,112,'Tfz',7,True);d.text(369,108,_text_source('server_national_brake_image.text_0b75a53fad39'),6.1,True)
    rows=[(1,15,_text_source('server_national_brake_image.text_9559e903c4ee')),(2,15,_text_source('server_national_brake_image.text_a84d71a5cbfd')),(3,15,_text_source('server_national_brake_image.text_443a09f661c4')),(4,16,_text_source('server_national_brake_image.text_9d41b1c4a1cb')),(5,23,_text_source('server_national_brake_image.text_aeceac05fbf6')),(6,16,_text_source('server_national_brake_image.text_94b0726e381e')),(7,17,_text_source('server_national_brake_image.text_f6e2718d68cc')),(8,14,_text_source('server_national_brake_image.text_f26b10d7ac23')),(9,14,_text_source('server_national_brake_image.text_0df5a6fc6c73')),(10,14,_text_source('server_national_brake_image.text_1b7c4bf1906a')),(11,14,_text_source('server_national_brake_image.text_c762850a1b7b')),(12,14,_text_source('server_national_brake_image.text_5bffe19bb2c8')),(13,16,_text_source('server_national_brake_image.text_654d02ead73c')),(14,16,_text_source('server_national_brake_image.text_d11df5663405')),(15,22,_text_source('server_national_brake_image.text_3ecdf76da764')),(16,30,_text_source('server_national_brake_image.text_d4cc95b9a53b'))]
    pos={};y=126
    for n,h,title in rows:
        pos[n]=(y,h);d.centered(62,y,20,h,n);d.text(85,y+4,title,6.8,maxwidth=190)
        if n==5:d.text(86,y+14,_text_source('server_national_brake_image.text_a77a6afee523'),5.7)
        if n==15:d.text(86,y+14,_text_source('server_national_brake_image.text_1171ab5fab12'),6)
        if n==16:d.text(86,y+14,_text_source('server_national_brake_image.text_1e27a0941d9d'),6.8)
        y+=h
        if n in (4,5):d.line(62,y,278,y);d.line(364,y,right,y)
        else:d.line(62,y,320 if n in (8,9,10,11,14) else right,y)
    end=y
    d.line(left,end,right,end,1);d.text(16,139,_text_source('server_national_brake_image.text_f0c017b40dbf'),6.6,True,maxwidth=43);d.text(16,149,_text_source('server_national_brake_image.text_960b300d2482'),6.6,True);d.text(16,159,_text_source('server_national_brake_image.text_4e94049e05ed'),6.6,True)
    for n,key in [(1,'weight'),(2,'brake'),(3,'axles'),(13,'length')]:
        yy,h=pos[n]
        for x,w,col in [(278,42,'wagon'),(320,44,'loco'),(364,44,'total')]:d.centered(x,yy,w,h,result[col][key])
    for n,v in [(4,sheet.required_percent),(5,result['available']),(6,result['missing'])]:d.centered(364,pos[n][0],44,pos[n][1],v,color='#c40000' if n==6 and isinstance(v,(int,float,Decimal)) else 'black')
    if isinstance(result['missing'],int) and result['missing']<0:d.text(401,pos[6][0]+5,'*)',5)
    y4=pos[4][0];y6=pos[6][0]+pos[6][1]
    for x1,x2 in [(278,320),(320,364)]:d.line(x1,y6,x2,y4)
    last=sheet.last_vehicle
    if last:last=f'{last[:2]} {last[2:4]} {last[4:8]} {last[8:11]}-{last[11]}'
    d.centered(278,pos[7][0],130,pos[7][1],last)
    if not last:d.strike(278,pos[7][0],130,pos[7][1])
    for n,value in [(8,sheet.brakes_single),(9,sheet.brakes_multi),(10,sheet.brakes_d),(11,sheet.brakes_k),(12,sheet.brakes_matrossow),(14,sheet.braked_axles),(15,result['required_axles'])]:d.centered(278,pos[n][0],42,pos[n][1],value) if value is not None else d.strike(278,pos[n][0],42,pos[n][1])
    for i,s in enumerate(sheet.speeds):
        x=[282,324,368][i];yy=pos[16][0]
        d.text(x,yy+3,'ja' if s.lower else 'nein',7)
        if s.lower:d.centered([278,320,364][i],yy+13,[42,44,44][i],17,str(s.value)+' km/h')
        else:d.strike([278,320,364][i],yy+13,[42,44,44][i],17)
    travel_top=end;travel_end=travel_top+117
    for x in [12,62,82,278,320,408]:d.line(x,travel_top,x,travel_end)
    labels=[(21,_text_source('server_national_brake_image.text_a49543af0aed')),(22,_text_source('server_national_brake_image.text_0b07d7df9da3')),(23,_text_source('server_national_brake_image.text_13fab6be4879')),(24,_text_source('server_national_brake_image.text_9e9c7ea68ed6')),(25,'TB 0'),(26,''),(27,_text_source('server_national_brake_image.text_14b136fa23b5')),(28,_text_source('server_national_brake_image.text_edc7b0419e92')),(29,'')]
    for i,(n,title) in enumerate(labels):
        yy=travel_top+i*13;d.centered(62,yy,20,13,n,6.5);d.text(86,yy+3,title,6,maxwidth=188);d.text(281,yy+3,_text_source('server_national_brake_image.text_1f81524a386b'),6.5,maxwidth=36);d.line(62,yy+13,320,yy+13)
    d.text(16,travel_top+7,_text_source('server_national_brake_image.text_f0c017b40dbf'),6.4,True);d.text(16,travel_top+17,_text_source('server_national_brake_image.text_ef8dbf86d6f9'),6.4,True)
    # Strike only row-number/description cells: lower-left of 29 to upper-right of 21.
    d.line(62,travel_end,320,travel_top,1.2)
    d.line(left,travel_top,left,travel_end);d.line(right,travel_top,right,travel_end)
    d.line(left,travel_end,right,travel_end,1)
    yy=travel_end
    for n,h in [(31,20),(32,22)]:
        for x in [12,62,82,278,408]:d.line(x,yy,x,yy+h)
        d.centered(62,yy,20,h,n)
        if n==31:
            d.text(85,yy+4,_text_source('server_national_brake_image.text_63c7d324edc6'),6.5);d.text(85,yy+12,_text_source('server_national_brake_image.text_9f0bbec4fe3d'),6.5);d.text(284,yy+7,'ja' if sheet.dangerous else 'nein',7)
        elif sheet.extra:
            text=sheet.extra_text
            # Wrap optional note in two lines, fail visibly rather than truncate.
            if not text:d.strike(82,yy,196,h)
            words=text.split();lines=['']
            for word in words:
                candidate=(lines[-1]+' '+word).strip()
                if len(candidate)>70 and lines[-1]:lines.append(word)
                else:lines[-1]=candidate
            if len(lines)>4:raise ValueError(_text_source('server_national_brake_image.text_d3498c2c5d40'))
            for i,line in enumerate(lines):d.text(85,yy+2+i*5,line,5,maxwidth=187)
            d.text(284,yy+7,'ja' if sheet.extra else 'nein',7)
        d.line(62 if n==31 else left,yy+h,right,yy+h);yy+=h
    d.text(16,travel_end+6,_text_source('server_national_brake_image.text_f0c017b40dbf'),6.3,True);d.text(16,travel_end+16,_text_source('server_national_brake_image.text_4e94049e05ed'),6.3,True)
    d.line(left,yy+4,right,yy+4,1);d.line(left,yy+4,left,yy+27);d.line(right,yy+4,right,yy+27);d.line(left,yy+27,right,yy+27,1)
    d.text(17,yy+8,_text_source('server_national_brake_image.text_375afc8aa556'),7,True);d.text(17,yy+18,creator,7,maxwidth=254)
    d.line(278,yy+4,278,yy+27)
    for i,line in enumerate([_text_source('server_national_brake_image.text_72e6602e1387'),_text_source('server_national_brake_image.text_3c33c81a1821')]):d.text(283,yy+9+i*8,line,6.1,maxwidth=120)
    return d.finish()
