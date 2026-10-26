"""Sharp vector A5 national freight brake sheet plus matching image preview."""
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
        if image:self.im=Image.new('RGB',(1680,2380),'white');self.d=ImageDraw.Draw(self.im)
        else:
            for name,bold in [('National',False),('NationalBold',True)]:
                if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,font_path(bold)))
            self.c=canvas.Canvas(self.buffer,pagesize=(420,595),invariant=1);self.c.setTitle('Bremszettel für Güterzüge - Deutschland')
    def line(self,x1,y1,x2,y2,width=.5):
        if self.image:self.d.line([(round(x1*4),round(y1*4)),(round(x2*4),round(y2*4))],fill='black',width=max(1,round(width*4)))
        else:self.c.setLineWidth(width);self.c.line(x1,595-y1,x2,595-y2)
    def strike(self,x,y,w,h):self.line(x+2,y+h-2,x+w-2,y+2,.6)
    def text(self,x,y,text,size=7,bold=False,maxwidth=None):
        text=fmt(text)
        if not text:return
        while True:
            if self.image:
                font=ImageFont.truetype(font_path(bold),round(size*4));width=self.d.textlength(text,font=font)/4
            else:width=pdfmetrics.stringWidth(text,'NationalBold' if bold else 'National',size)
            if maxwidth is None or width<=maxwidth:break
            size-=.25
            if size<4.5:raise ValueError('Text ist für den Bremszettel zu lang. Bitte Eingabe kürzen.')
        if self.image:self.d.text((round(x*4),round(y*4)),text,fill='black',font=font,anchor='lt')
        else:self.c.setFont('NationalBold' if bold else 'National',size);self.c.drawString(x,595-y-size*.8,text)
    def finish(self):
        if self.image:self.im.save(self.buffer,format='PNG',dpi=(288,288))
        else:self.c.showPage();self.c.save()
        return self.buffer.getvalue()

def render(sheet,result,creator,image=False):
    d=Drawing(image);left,right=12,408;xs=[12,62,82,278,320,364,408]
    d.line(left,10,right,10,1);d.line(left,10,left,85,1);d.line(right,10,right,85,1)
    d.text(17,17,'Bremszettel',14,True);d.text(183,20,'Datum: '+sheet.departure_date.strftime('%d.%m.%Y'),9)
    trains=[t for t in sheet.trains if t.number]
    d.line(left,36,right,36)
    if len(trains)<=3:
        d.text(25,40,'Zugnummer(n)',7,True);d.text(301,40,'ab Betriebsstelle',7,True);d.line(290,36,290,85)
    else:d.text(17,40,'Zugnummer / ab Betriebsstelle (DS100)',7,True)
    # Keep each DS100 paired with its train; up to 20 pairs fit as four compact columns.
    if len(trains)<=3:
        for i,t in enumerate(trains):d.text(22,51+i*10,t.number,9);d.text(301,51+i*10,t.station,8,maxwidth=100)
    else:
        for i,t in enumerate(trains):
            col=i//5;row=i%5;x=17+col*97
            d.text(x,50+row*6.4,t.number+' / '+t.station,5.8,maxwidth=92)
    d.line(left,85,right,85,1)
    if len(trains)<3:d.strike(12,51+len(trains)*10,278,34-len(trains)*10);d.strike(290,51+len(trains)*10,118,34-len(trains)*10)
    top=90
    for x in xs:
        if x in (320,364):
            d.line(x,top,x,226)
            if x==320:d.line(x,243,x,397)
            else:d.line(x,313,x,329);d.line(x,367,x,397)
        else:d.line(x,top,x,397)
    d.line(left,top,right,top,1);d.line(left,126,right,126,1)
    for i,x in enumerate(xs[:-1]):d.text(x+3,93,str(i+1),6,True)
    d.text(64,108,'Zeile',6.5,True);d.text(148,108,'Bezeichnung',8,True)
    d.text(282,108,'Wagenzug',6.2,True);d.text(324,103,'arbeitende',6,True);d.text(326,112,'Tfz',7,True);d.text(369,108,'Gesamtzug',6.1,True)
    rows=[(1,15,'Gewicht (t)'),(2,15,'Bremsgewicht (t)'),(3,15,'Zahl der Achsen'),(4,16,'Mindestbremshundertstel'),(5,23,'Vorhandene Bremshundertstel'),(6,16,'Fehlende Bremshundertstel'),(7,17,'Nummer des letzten Fahrzeuges'),(8,14,'Zahl der einlösigen Bremsen'),(9,14,'Zahl der mehrlösigen Bremsen'),(10,14,'Zahl der Bremsen mit D'),(11,14,'Zahl der Bremsen mit K, L und LL'),(12,14,'Zahl der Matrossow-Bremsen'),(13,16,'Länge (m)'),(14,16,'Zahl der gebremsten Achsen'),(15,22,'Zahl der erforderlich gebremsten Achsen'),(16,30,'Zulässige Geschwindigkeit niedriger')]
    pos={};y=126
    for n,h,title in rows:
        pos[n]=(y,h);d.text(68,y+5,n,7);d.text(85,y+4,title,6.8,maxwidth=190)
        if n==5:d.text(86,y+14,'Zeile 2, Sp. 6 × 100 / Zeile 1, Sp. 6',5.7)
        if n==15:d.text(86,y+14,'Zeile 3, Sp. 4 × 9 / 10',6)
        if n==16:d.text(86,y+14,'als gemäß Fahrplanangaben',6.8)
        y+=h;d.line(62,y,right,y)
    end=y
    d.line(left,end,right,end,1);d.text(16,139,'Angaben für',6.6,True,maxwidth=43);d.text(16,149,'Reise- und',6.6,True);d.text(16,159,'Güterzüge',6.6,True)
    for n,key in [(1,'weight'),(2,'brake'),(3,'axles'),(13,'length')]:
        yy,h=pos[n]
        for x,col in [(282,'wagon'),(324,'loco'),(368,'total')]:d.text(x,yy+5,result[col][key],7,maxwidth=36)
    for n,v in [(4,sheet.required_percent),(5,result['available']),(6,result['missing'])]:d.text(368,pos[n][0]+5,v,8,maxwidth=36)
    if isinstance(result['missing'],int) and result['missing']<0:d.text(401,pos[6][0]+5,'*)',5)
    y4=pos[4][0];y6=pos[6][0]+pos[6][1]
    for x1,x2 in [(278,320),(320,364)]:d.line(x1,y6,x2,y4)
    last=sheet.last_vehicle
    if last:last=f'{last[:2]} {last[2:4]} {last[4:8]} {last[8:11]}-{last[11]}'
    d.text(282,pos[7][0]+5,last,7,maxwidth=122)
    if not last:d.strike(278,pos[7][0],130,pos[7][1])
    d.strike(320,pos[8][0],88,pos[8][1])
    for n in [9,10,11,12,14,15]:d.strike(320,pos[n][0],88,pos[n][1])
    for n,value in [(8,sheet.brakes_single),(9,sheet.brakes_multi),(10,sheet.brakes_d),(11,sheet.brakes_k),(12,sheet.brakes_matrossow),(14,sheet.braked_axles),(15,result['required_axles'])]:d.text(282,pos[n][0]+4,value,7) if value is not None else d.strike(278,pos[n][0],42,pos[n][1])
    for i,s in enumerate(sheet.speeds):
        x=[282,324,368][i];yy=pos[16][0]
        d.text(x,yy+3,'ja' if s.lower else 'nein',7)
        if s.lower:d.text(x,yy+16,str(s.value)+' km/h',6.4,maxwidth=36)
        else:d.strike([278,320,364][i],yy+13,[42,44,44][i],17)
    travel_top=end;travel_end=travel_top+117
    for x in xs:d.line(x,travel_top,x,travel_end)
    labels=[(21,'NBÜ/ep-Bremsen an allen Fahrzeugen vorhanden'),(22,'Notbremsüberbrückung wirksam'),(23,'Kennbuchstaben h, z oder ee'),(24,'Kennbuchstaben n oder y'),(25,'TB 0'),(26,''),(27,'o. Zub'),(28,'Kennbuchstaben a'),(29,'')]
    for i,(n,title) in enumerate(labels):
        yy=travel_top+i*13;d.text(67,yy+3,n,6.5);d.text(86,yy+3,title,6,maxwidth=188);d.line(62,yy+13,right,yy+13)
    d.text(16,travel_top+7,'Angaben für',6.4,True);d.text(16,travel_top+17,'Reisezüge',6.4,True)
    # The entire passenger section is struck from bottom-left to top-right.
    d.line(left,travel_end,right,travel_top,1.2)
    d.line(left,travel_top,left,travel_end);d.line(right,travel_top,right,travel_end)
    d.line(left,travel_end,right,travel_end,1)
    yy=travel_end
    for n,h in [(31,20),(32,22)]:
        for x in [12,62,82,278,408]:d.line(x,yy,x,yy+h)
        d.text(67,yy+5,n,7)
        if n==31:
            d.text(85,yy+4,'Im Wagenzug sind Fahrzeuge mit',6.5);d.text(85,yy+12,'gefährlichen Gütern',6.5);d.text(284,yy+7,'ja' if sheet.dangerous else 'nein',8)
        else:
            text=sheet.extra_text if sheet.extra else ''
            # Wrap optional note in two lines, fail visibly rather than truncate.
            if not text:d.strike(82,yy,196,h)
            words=text.split();lines=['']
            for word in words:
                candidate=(lines[-1]+' '+word).strip()
                if len(candidate)>70 and lines[-1]:lines.append(word)
                else:lines[-1]=candidate
            if len(lines)>4:raise ValueError('Angabe in Zeile 32 bitte für vier Druckzeilen kürzen.')
            for i,line in enumerate(lines):d.text(85,yy+2+i*5,line,5,maxwidth=187)
            d.text(284,yy+7,'ja' if sheet.extra else 'nein',8)
        d.line(62 if n==31 else left,yy+h,right,yy+h);yy+=h
    d.text(16,travel_end+6,'Angaben für',6.3,True);d.text(16,travel_end+16,'Güterzüge',6.3,True)
    d.line(left,yy+4,right,yy+4,1);d.line(left,yy+4,left,yy+27);d.line(right,yy+4,right,yy+27);d.line(left,yy+27,right,yy+27,1)
    d.text(17,yy+8,'Bremszettel ausgefertigt (Name)',7,True);d.text(17,yy+18,creator,8,maxwidth=254)
    d.line(278,yy+4,278,yy+27)
    for i,line in enumerate(['*) betriebsleitende Stelle','des EVU verständigen']):d.text(283,yy+9+i*8,line,6.1,maxwidth=120)
    return d.finish()
