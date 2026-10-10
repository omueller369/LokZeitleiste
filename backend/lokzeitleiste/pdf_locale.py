"""Unicode fonts and localized ReportLab text, including Arabic shaping."""
import os
import re
from html import escape, unescape
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph as BaseParagraph
from .i18n import display, translate, request_language
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


def register_fonts(prefix):
    directory=Path(os.getenv('LOKZEITLEISTE_FONT_DIR','/usr/share/fonts/truetype/dejavu'))
    regular=directory/'DejaVuSans.ttf'
    fallback=Path(reportlab.__file__).parent/'fonts'
    variants=[('', 'DejaVuSans.ttf','Vera.ttf'),('-Bold','DejaVuSans-Bold.ttf','VeraBd.ttf'),('-Italic','DejaVuSans-Oblique.ttf','VeraIt.ttf'),('-BoldItalic','DejaVuSans-BoldOblique.ttf','VeraBI.ttf')]
    for suffix,filename,old in variants:
        path=directory/filename
        if regular.exists():
            if not path.exists():path=regular
        else:path=fallback/old
        pdfmetrics.registerFont(TTFont(prefix+suffix,str(path)))
    pdfmetrics.registerFontFamily(prefix,normal=prefix,bold=prefix+'-Bold',italic=prefix+'-Italic',boldItalic=prefix+'-BoldItalic')


def markup(value,lang=None):
    # Preserve ReportLab markup; shape only visible text, never markup syntax.
    return ''.join(part if part.startswith('<') else escape(display(unescape(part),lang)) for part in re.split(r'(<[^>]*>)',str(value)))


class LocalizedParagraph(BaseParagraph):
    def __init__(self,text,style,*args,**kwargs):
        if request_language.get()=='ar' and style.alignment!=TA_CENTER:
            style=style.clone(style.name+'-rtl',alignment=TA_RIGHT)
        super().__init__(markup(text),style,*args,**kwargs)
