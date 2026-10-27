"""Rebuild the clean bilingual brake-sheet background without moving fill rectangles.

Run from repository root. Requires ReportLab, DejaVu Sans and pdftoppm only for
asset authoring; production previews use the generated PNG and Pillow.
"""
from pathlib import Path
import os,subprocess
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]/'lokzeitleiste'/'assets'
FONT=Path(os.getenv('LOKZEITLEISTE_FONT_DIR','/usr/share/fonts/truetype/dejavu'))
pdfmetrics.registerFont(TTFont('BrakeLabel',str(FONT/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('BrakeBold',str(FONT/'DejaVuSans-Bold.ttf')))
W,H=1335,1888
ROOT.mkdir(parents=True,exist_ok=True)
pdf=ROOT/'brake-sheet-template.pdf'
c=canvas.Canvas(str(pdf),pagesize=A4,pageCompression=1,invariant=1)
c.setTitle('Internationaler Bremszettel für Güterzüge / Międzynarodowa Karta Próby Hamulca')
c.setAuthor('CTL-Software')
c.scale(A4[0]/W,A4[1]/H)
c.setLineCap(0);c.setLineJoin(0)
def line(x1,y1,x2,y2,width=1.5,dash=None):
    c.saveState();c.setLineWidth(width)
    if dash:c.setDash(*dash)
    c.line(x1,H-y1,x2,H-y2);c.restoreState()
def rect(x1,y1,x2,y2,width=2):
    c.setLineWidth(width);c.rect(x1,H-y2,x2-x1,y2-y1,stroke=1,fill=0)
def text(value,x,y,size=14,bold=False,center=False,width=None):
    font='BrakeBold' if bold else 'BrakeLabel'
    if width:
        while pdfmetrics.stringWidth(value,font,size)>width and size>9:size-=.25
    c.setFont(font,size)
    if center:c.drawCentredString(x,H-y,value)
    else:c.drawString(x,H-y,value)
def labels(values,x,ys,size=13,center=False,width=None):
    for value,y in zip(values,ys):text(value,x,y,size,center=center,width=width)
def check(x,y):rect(x-9,y-9,x+9,y+9,1.5)

# Title and repeated identifiers.
text('Międzynarodowa Karta Próby Hamulca',365,65,27,True,True,width=620)
text('Internationaler Bremszettel für Güterzüge',365,100,26,True,True,width=660)
text('Zugnummer / Nr poc.:',697,51,14,width=159);line(860,54,939,54,1)
text('Abfahrtsdatum / Data odj.:',974,51,14,width=191);line(1172,54,1270,54,1)
# Country header and three data rows.
rect(804,72,1304,238,2.5);line(804,100,1210,100);line(804,136,1304,136,2)
line(1210,72,1210,238,2)
for x in [970,1055,1134]:line(x,100,x,238)
text('5. Ländercode / Kod kraju',1007,91,16,True,True,width=390)
text('ETCS',1257,111,18,True,True)
# Main upper block.
rect(9,136,1304,238,2.5)
line(9,186,1304,186,2)
for x in [207,383]:line(x,136,x,186,2)
line(623,136,623,238,2);line(804,136,804,238,2);line(319,186,319,238,2)
for value,x,width in [('1. Aussteller-EVU / Wystawca',14,188),('2. Zugnummer / Nr poc.',212,166),('3. Abfahrtsdatum / Data odjazdu',388,230)]:text(value,x,152,13,width=width)
labels(['6. Zugkategorie','Rodzaj pociągu'],713,[155,174],15,True,width=170)
text('7. Vmax, km/h',713,206,15,center=True,width=170)
text('4a. Gültig ab Bahnhof / Ważna od st. kol.',14,204,13,width=300)
text('4b. Gültig bis Bahnhof / Ważna do st. kol.',324,204,13,width=294)
text('Zugparameter / Dane pociągu',11,262,18,True)
rect(9,271,1304,602,2.5);line(582,271,582,602,2)
text('8. Bemerkungen während der Fahrt / Uwagi dotyczące biegu pociągu',15,289,13,width=559)
text('9. Besonderheiten des Zuges / Informacje dodatkowe odnośnie pociągu',589,289,13,width=706)
# Flags and validity sections.
rect(9,602,1304,1085,2.5);line(377,602,377,1327,2.5)
for flag_y in [619,649,697,768]:check(27,flag_y)
text('10. Gefahrgut im Zug / Ładunek niebezp.',47,624,14,width=323)
labels(['11. Außergewöhnliche Sendung im Zug','Przesyłka nadzwyczajna'],47,[655,674],14,width=323)
labels(['12. Zusätzliche Dokumente über','Einschränkungen hinzugefügt','Załączono dodatkowe dokumenty','dotyczące ograniczeń'],47,[703,722,741,758],13,width=323)
labels(['13. Abfalltransporte im Zug','Przewóz odpadów'],47,[774,794],14,width=323)
line(377,659,1304,659,2);line(377,737,1304,737,2)
for x in [603,838,1074]:line(x,602,x,737,2)
for x,number,caption in [(382,'16a','Gültig ab Bahnhof / Ważna od st.'),(608,'16b','Gültig bis Bahnhof / Ważna do st.'),(843,'16c','Gültig ab Bahnhof / Ważna od st.'),(1079,'16d','Gültig bis Bahnhof / Ważna do st.')]:text(number+'. '+caption,x,619,12,width=214)
for x,number,de,pl,width in [(382,'17a','Nr. des ersten Fahrzeugs','Nr pierwszego wagonu',215),(608,'18a','Nr. des letzten Fahrzeugs','Nr ostatniego wagonu',225),(843,'17c','Nr. des ersten Fahrzeugs','Nr pierwszego wagonu',225),(1079,'18b','Nr. des letzten Fahrzeugs','Nr ostatniego wagonu',217)]:
    text(number+'. '+de,x,677,13,width=width);text(pl,x,694,12,width=width)
# Column headers and numerical totals.
xs=[377,530,694,838,1001,1143,1304]
for x in xs[1:-1]:line(x,737,x,1085,1.8)
line(377,757,1304,757,1.5);line(9,855,1304,855,2.5)
for i,value in enumerate(['a','b','a+b','c','d','c+d']):text(value,(xs[i]+xs[i+1])/2,752,16,True,True)
for left,right in [(377,530),(838,1001)]:labels(['Arbeitende','Triebfahrzeuge','Lokomotywy czynne'],(left+right)/2,[790,811,838],14,True,width=right-left-10)
for left,right in [(530,694),(1001,1143)]:labels(['Wagen und nicht','arbeitende','Triebfahrzeuge','Wagony i nieczynne','lokomotywy'],(left+right)/2,[777,795,813,833,849],12.5,True,width=right-left-10)
for left,right in [(694,838),(1143,1304)]:text('Gesamt / Razem',(left+right)/2,846,14,True,True,width=right-left-10)
for y in [900,942,997,1042]:
    line(9,y,377,y,1.8);line(377,y,1304,y,1.2,(2,2))
text('19. Anzahl der Fahrzeuge / Liczba pojazdów',14,883,14,width=355)
text('20. Länge, m / Długość, m',14,927,14,width=355)
text('21. Anrechenbare Festhaltekraft der',14,960,14,width=355)
text('Feststellbremsen, in',14,983,14,width=140);check(169,980);text('t',182,986,14);check(212,980);text('kN *',226,986,14)
labels(['22. Bremsgewicht nach Abzügen, t','Masa hamująca'],14,[1017,1035],14,width=355)
text('23. Gesamtgewicht, t / Masa brutto',14,1068,14,width=355)
# Route class and selected brake position.
rect(9,1085,377,1240,2.5);line(196,1085,196,1240,1.8)
labels(['14. Erforderliche','Streckenklasse','Wymagana klasa linii'],15,[1105,1124,1141],14,width=174)
labels(['15. Bremsstellung','Nastawienie hamulca'],202,[1105,1124],14,width=169)
for value,y in [('G',1139),('P',1159),('G+P',1179),('LL+P',1199),('R',1219)]:check(237,y);text(value,255,y+5,15)
# Brake percentage tables, first and second section.
rect(377,1085,1304,1327,2.5)
for x in [694,838,1143]:line(x,1085,x,1327,1.8)
for y in [1135,1185,1240]:line(377,y,1304,y,1.8)
for left,right in [(377,694),(838,1143)]:
    x=(left+right)/2
    labels(['24. Vorhandene Bremshundertstel:','Rzeczywisty % masy hamującej:'],x,[1106,1127],14,True,width=right-left-10)
    labels(['25. Erforderliche Bremshundertstel:','Wymagany % masy hamującej:'],x,[1157,1177],14,True,width=right-left-10)
    labels(['26. Fehlende Bremshundertstel:','Brakujący % masy hamującej:'],x,[1208,1229],14,True,width=right-left-10)
    labels(['27. Anteil des durch Graugusssohlen','gebremsten Bremsgewichts:','% masy hamowanej żeliwnymi wstawkami'],x,[1267,1287,1310],13,True,width=right-left-10)
# Working locomotive table: exact overlay column and row geometry.
text('Arbeitende Triebfahrzeuge im Zug / Lokomotywy czynne w pociągu',11,1348,18,True)
columns=[9,87,383,475,563,668,760,838,910,980,1054,1304]
rect(9,1362,1304,1707,2.5)
for x in columns[1:-1]:line(x,1362,x,1707,1.8)
line(9,1391,1304,1391,1.5)
for y in [1507,1547,1587,1627,1667]:line(9,y,1304,y,1.8)
for i,value in enumerate(['28.','29.','30.','31.','32.','33.','34.','35.','36.','36a. **','37.']):text(value,(columns[i]+columns[i+1])/2,1383,16,True,True,width=columns[i+1]-columns[i]-6)
labels(['Pos. /','Poz.'],48,[1418,1440],15,True)
labels(['Fahrzeugnummer /','Numer pojazdu'],94,[1418,1440],15,width=280)
labels(['Baureihe /','Typ / Seria'],429,[1418,1440],14,True,width=83)
def vertical(value,x,y,size=14):
    c.saveState();c.translate(x,H-y);c.rotate(90);c.setFont('BrakeLabel',size);c.drawCentredString(0,0,value);c.restoreState()
vertical('Anzahl Radsätze',505,1450,12.5);vertical('Liczba osi',537,1450,13)
labels(['Länge über','Puffer, m','Długość po','zderzakach, m'],615,[1418,1440,1462,1484],14,True,width=96)
labels(['Gesamt-','gewicht, kg','Masa','całk., kg'],714,[1418,1440,1462,1484],14,True,width=82)
vertical('Bremssohlenart',791,1450,13);vertical('Typ wst. ham.',818,1450,12)
vertical('Bremsstellung',865,1450,13);vertical('Nast. ham.',893,1450,12)
labels(['Brems-','gewicht,','t','Masa','ham., t'],945,[1415,1434,1453,1472,1491],13,True,width=62)
labels(['Festhalte-','kraft der','Feststell-','bremsen'],1017,[1415,1434,1453,1472],13,True,width=66)
text('t',986,1493,13);check(1001,1488);text('kN',1015,1493,13);check(1042,1488)
labels(['Bemerkungen /','Uwagi'],1062,[1418,1440],15,width=232)
for i in range(5):text(str(i+1),48,1535+40*i,17,True,True)
# Creation / verification areas.
rect(9,1730,889,1775,2.5);rect(9,1775,1304,1823,2.5)
for x in [263,498]:line(x,1730,x,1823,1.8)
line(889,1775,889,1823,1.8)
for x,value,width in [(14,'38. Erstelldatum / Data wystawienia',244),(268,'39. Erstellungszeit / Godz. wyst.',225),(503,'40. Erstellt von / Wystawiono przez:',195)]:text(value,x,1746,13,width=width)
for x,value,width in [(14,'41. Überprüfungsdatum / Data zatw.',244),(268,'42. Überprüfungszeit / Godz. zatw.',225),(503,'43. Überprüft von / Zatwierdzone przez:',380),(894,'44. Anmerkung / Uwagi',404)]:text(value,x,1794,13,width=width)
text('* Siła utrzymująca hamulca postojowego t / kN.',13,1845,12)
text('** Siła hamulca postojowego.',13,1863,12)
c.showPage();c.save()
subprocess.run(['/usr/bin/pdftoppm','-png','-singlefile','-scale-to-x','2481','-scale-to-y','3507',str(pdf),str(ROOT/'brake-sheet-template')],check=True)
with Image.open(ROOT/'brake-sheet-template.png') as image:
    clean=image.convert('L')
clean.save(ROOT/'brake-sheet-template.png',optimize=True,compress_level=9,dpi=(300,300))
print(pdf)
