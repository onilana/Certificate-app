import os
import re
import datetime
import copy
import json
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from path_utils import get_base_dir, get_asset_path

TEMPLATES_DIR = get_asset_path('assets', 'templates')
POSITIONS_FILE = os.path.join(get_base_dir(), 'custom_positions.json')

CERT_TYPES = {
    'provisional': {
        'name': 'Provisional Certificate',
        'template': os.path.join(TEMPLATES_DIR, 'provisional_template.png'),
    },
    'character': {
        'name': 'Character Certificate',
        'template': os.path.join(TEMPLATES_DIR, 'character_template.png'),
    },
    'transfer': {
        'name': 'Transfer Certificate',
        'template': os.path.join(TEMPLATES_DIR, 'transfer_template.png'),
    },
    'reading': {
        'name': 'Reading Certificate',
        'template': os.path.join(TEMPLATES_DIR, 'reading_template.png'),
    }
}

IMG_W = 3000.0
IMG_H = 2250.0

PAPER_SIZES = {
    "10.5x7.5": (10.5 * 72.0, 7.5 * 72.0),     # 756.0 x 540.0 pt (Certificate Standard)
    "10.0x7.5": (10.0 * 72.0, 7.5 * 72.0),     # 720.0 x 540.0 pt
    "A4": (841.89, 595.27),                     # 297 x 210 mm
    "Letter": (11.0 * 72.0, 8.5 * 72.0),       # 792.0 x 612.0 pt
    "Legal": (14.0 * 72.0, 8.5 * 72.0)         # 1008.0 x 612.0 pt
}

# Factory default baseline coordinates (x_start, y_baseline) on the 3000x2250 grid
DEFAULT_POSITIONS = {
    'provisional': {
        'sl_no': (535, 755),
        'student_name': (1060, 1068),
        'father_name': (540, 1155),
        'mother_name': (1630, 1155),
        'address': (720, 1242),
        'exam_year': (1085, 1329),
        'roll_no': (1770, 1329),
        'grade': (425, 1503),
        'dob': (1890, 1590),
        'reg_no': (1540, 1677),
        'result_date': (1580, 1764),
        'issue_date': (360, 2024),
        'aisse': (643, 1315, 795, 1315),
        'aissce': (815, 1315, 996, 1315),
    },
    'character': {
        'sl_no': (500, 834),
        'student_name': (480, 1310),
        'exam_year': (1185, 1415),
        'roll_no': (1410, 1519),
        'grade': (260, 1623),
        'session': (1310, 1728),
        'issue_date': (350, 1984),
        'aisse': (687, 1400, 860, 1400),
        'aissce': (880, 1400, 1081, 1400),
        'qualified': (2480, 1295, 2712, 1295),
        'disqualified': (251, 1400, 526, 1400)
    },
    'transfer': {
        'sl_no': (545, 706),
        'student_name': (1050, 969),
        'father_name': (540, 1051),
        'mother_name': (1640, 1051),
        'exam_year': (1815, 1133),
        'roll_no': (1220, 1214),
        'grade': (2375, 1214),
        'session': (1730, 1377),
        'dob': (1935, 1459),
        'reg_no': (1540, 1540),
        'left_date': (1050, 1622),
        'pen_no': (865, 1703),
        'issue_date': (1350, 2007),
        'aisse': (1385, 1120, 1540, 1120),
        'aissce': (1560, 1120, 1752, 1120),
        'qualified': (793, 1120, 985, 1120),
        'disqualified': (1000, 1120, 1292, 1120)
    },
    'reading': {
        'sl_no': (535, 755),
        'student_name': (1100, 1081),
        'father_name': (560, 1202),
        'mother_name': (1570, 1202),
        'address': (730, 1323),
        'class_name': (770, 1444),
        'stream': (1230, 1444),
        'section': (1715, 1444),
        'class_roll_no': (2410, 1444),
        'session': (1340, 1565),
        'dob': (1890, 1686),
        'issue_date': (360, 2024),
    }
}

def compute_sl_no(cert_type: str, reg_no: str = "", stream: str = "", section: str = "", class_roll: str = "") -> str:
    """
    Computes Sl. No. according to user rules:
    1. Provisional: exact last 3 digit of registration
    2. Character: exact last 3 digit of registration
    3. Transfer: exact last 3 digit of registration
    4. Reading Certificate: Exact from Stream (If Science take Sc, if Arts, take AR, if Commerce, take Co), Section & Class Roll (e.g. Sc/A/18)
    """
    ctype = str(cert_type or '').strip().lower()
    if ctype in ('provisional', 'character', 'transfer', 'all', ''):
        reg = str(reg_no or '').strip()
        if reg:
            import re
            digits = re.findall(r'\d+', reg)
            if digits:
                last = digits[-1]
                if len(last) >= 3:
                    return last[-3:]
                return last.zfill(3)
            return ""
        elif ctype in ('all', '') and (stream or section or class_roll):
            # Fallback to reading certificate format if registration is absent
            st = str(stream or '').strip().lower()
            if 'sci' in st:
                code = 'Sc'
            elif 'art' in st:
                code = 'AR'
            elif 'com' in st:
                code = 'Co'
            else:
                code = stream.strip()[:2].capitalize() if stream else 'Sc'
            sec = str(section or '').strip()
            roll = str(class_roll or '').strip()
            parts = [p for p in [code, sec, roll] if p]
            return "/".join(parts)
        return ""
    elif ctype == 'reading':
        st = str(stream or '').strip().lower()
        if 'sci' in st:
            code = 'Sc'
        elif 'art' in st:
            code = 'AR'
        elif 'com' in st:
            code = 'Co'
        else:
            code = stream.strip()[:2].capitalize() if stream else 'Sc'
        sec = str(section or '').strip()
        roll = str(class_roll or '').strip()
        parts = [p for p in [code, sec, roll] if p]
        return "/".join(parts)
    return ""

def load_positions() -> dict:
    pos = copy.deepcopy(DEFAULT_POSITIONS)
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                for cert_k, cert_fields in saved.items():
                    if cert_k in pos:
                        for field_k, coords in cert_fields.items():
                            if isinstance(coords, (list, tuple)):
                                pos[cert_k][field_k] = tuple(coords)
        except Exception as e:
            print(f"Error loading custom positions: {e}")
    return pos

def save_positions(positions: dict) -> bool:
    try:
        serializable = {}
        for cert_k, cert_fields in positions.items():
            serializable[cert_k] = {}
            for field_k, coords in cert_fields.items():
                serializable[cert_k][field_k] = list(coords) if isinstance(coords, (list, tuple)) else coords
        with open(POSITIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving positions: {e}")
        return False

def save_certificate_position(cert_type: str, cert_positions: dict) -> bool:
    """Saves alignment positions specifically for a single certificate type."""
    try:
        curr = load_positions()
        curr[cert_type] = copy.deepcopy(cert_positions)
        return save_positions(curr)
    except Exception as e:
        print(f"Error saving certificate position for {cert_type}: {e}")
        return False

def reset_positions(cert_type: str = None) -> dict:
    if cert_type:
        curr = load_positions()
        if cert_type in DEFAULT_POSITIONS:
            curr[cert_type] = copy.deepcopy(DEFAULT_POSITIONS[cert_type])
            save_positions(curr)
            return curr
    else:
        if os.path.exists(POSITIONS_FILE):
            try:
                os.remove(POSITIONS_FILE)
            except Exception:
                pass
        return copy.deepcopy(DEFAULT_POSITIONS)

# Live active positions
POSITIONS = load_positions()

# Field metadata for each certificate type
FIELD_METADATA = {
    'provisional': [
        ('sl_no', 'Sl. No. (Serial Number)', ''),
        ('student_name', 'Student Name', ''),
        ('father_name', "Father's Name (S/o, D/o Mr.)", ''),
        ('mother_name', "Mother's Name (& Mrs.)", ''),
        ('address', 'Address (an inhabitant of)', ''),
        ('exam_year', 'Examination Year (20...)', ''),
        ('roll_no', 'Board Roll Number', ''),
        ('grade', 'Division / Grade', ''),
        ('dob', 'Date of Birth', ''),
        ('reg_no', 'Registration Number', ''),
        ('result_date', 'Result Announced Date', ''),
        ('issue_date', 'Date of Issue (The...)', ''),
    ],
    'character': [
        ('sl_no', 'Sl. No. (Serial Number)', ''),
        ('student_name', 'Student Name (Mr/Miss)', ''),
        ('exam_year', 'Examination Year (20...)', ''),
        ('roll_no', 'Roll Number', ''),
        ('grade', 'Division / Grade', ''),
        ('session', 'Academic Session (20...)', ''),
        ('reg_no', 'Registration Number', ''),
        ('issue_date', 'Date of Issue (The...)', ''),
    ],
    'transfer': [
        ('sl_no', 'Sl. No. (Serial Number)', ''),
        ('student_name', 'Student Name (Mr/Miss)', ''),
        ('father_name', "Father's Name (Mr.)", ''),
        ('mother_name', "Mother's Name (& Mrs.)", ''),
        ('exam_year', 'Examination Year (20...)', ''),
        ('roll_no', 'Roll Number', ''),
        ('grade', 'Division / Grade', ''),
        ('session', 'Academic Session', ''),
        ('dob', 'Date of Birth', ''),
        ('reg_no', 'Registration Number', ''),
        ('left_date', 'Date of Leaving School', ''),
        ('pen_no', 'PEN Number', ''),
        ('issue_date', 'Date of Issue (The...)', ''),
    ],
    'reading': [
        ('sl_no', 'Sl. No. (Serial Number)', ''),
        ('student_name', 'Student Name (Mr/Miss)', ''),
        ('father_name', "Father's Name (Mr.)", ''),
        ('mother_name', "Mother's Name (& Mrs.)", ''),
        ('address', 'Address (an inhabitant of)', ''),
        ('class_name', 'Class (e.g. XII)', ''),
        ('stream', 'Stream (e.g. Science)', ''),
        ('section', 'Section (e.g. A)', ''),
        ('class_roll_no', 'Class Roll Number', ''),
        ('session', 'Academic Session (20...)', ''),
        ('dob', 'Date of Birth', ''),
        ('issue_date', 'Date of Issue (The...)', ''),
    ]
}

ADMIN_SAMPLE_DATA = {
    'provisional': {
        'sl_no': '001',
        'student_name': 'Candidate Name',
        'father_name': "Father's Name",
        'mother_name': "Mother's Name",
        'address': 'Address / Village Name',
        'exam_year': '24',
        'roll_no': '12345678',
        'grade': 'A1',
        'dob': '01/01/2006',
        'reg_no': 'R/1/24/1230048/0001',
        'result_date': '13th May, 2024',
        'issue_date': 'DD/MM/YYYY',
    },
    'character': {
        'sl_no': '001',
        'student_name': 'Candidate Name',
        'exam_year': '24',
        'roll_no': '12345678',
        'grade': 'A1',
        'session': '2023 - 2024',
        'reg_no': 'R/1/24/1230048/0001',
        'issue_date': 'DD/MM/YYYY',
    },
    'transfer': {
        'sl_no': '001',
        'student_name': 'Candidate Name',
        'father_name': "Father's Name",
        'mother_name': "Mother's Name",
        'exam_year': '24',
        'roll_no': '12345678',
        'grade': 'A1',
        'session': '2023 - 2024',
        'dob': '01/01/2006',
        'reg_no': 'R/1/24/1230048/0001',
        'left_date': '31/03/2024',
        'pen_no': 'PEN00000000',
        'issue_date': 'DD/MM/YYYY',
    },
    'reading': {
        'sl_no': 'Sc/A/01',
        'student_name': 'Candidate Name',
        'father_name': "Father's Name",
        'mother_name': "Mother's Name",
        'address': 'Address / Village Name',
        'class_name': 'XII',
        'stream': 'Science',
        'section': 'A',
        'class_roll_no': '01',
        'session': '2023 - 2024',
        'dob': '01/01/2006',
        'issue_date': 'DD/MM/YYYY',
    }
}

def to_sentence_case(val: str) -> str:
    """Formats all-caps or lowercase text into clean Sentence / Title Case for names and places."""
    if not val:
        return ''
    s = str(val).strip()
    words = s.split()
    res = []
    for w in words:
        if '.' in w:
            parts = w.split('.')
            w_cap = '.'.join(p.capitalize() if p else '' for p in parts)
            res.append(w_cap)
        elif '/' in w:
            parts = w.split('/')
            w_cap = '/'.join(p.capitalize() if p else '' for p in parts)
            res.append(w_cap)
        else:
            res.append(w.capitalize())
    return ' '.join(res)

def clean_date_str(val: any) -> str:
    """Strips trailing timestamps (e.g. '00:00:00') from dates and standardizes ISO dates to DD/MM/YYYY."""
    if not val:
        return ''
    import datetime
    if isinstance(val, (datetime.datetime, datetime.date)):
        return val.strftime('%d/%m/%Y')
    s = str(val).strip()
    if not s:
        return ''
    # Strip any trailing timestamp like ' 00:00:00', 'T00:00:00', ' 00:00', ' 12:00:00 AM', etc.
    s = re.sub(r'[\sT]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?.*$', '', s).strip()
    # If in YYYY-MM-DD or YYYY/MM/DD format, convert to standard DD/MM/YYYY
    m = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$', s)
    if m:
        year, month, day = m.group(1), m.group(2), m.group(3)
        return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    return s

def format_field_value(cert_key: str, key: str, value: any) -> str:
    """Formats values intelligently to prevent duplicate prefixes (e.g. '20' in year/session), strip timestamps from dates, and enforce Sentence Case."""
    val = str(value or '').strip()
    if not val:
        return ''

    # Clean date fields to strip any trailing 00:00:00 timestamp and ensure clean DD/MM/YYYY format
    if key in ('dob', 'result_date', 'left_date', 'issue_date') or key.endswith('_date'):
        val = clean_date_str(val)

    # Enforce sentence / title case for personal and location fields
    if key in ('student_name', 'father_name', 'mother_name', 'address'):
        val = to_sentence_case(val)
    
    # When template preprints '20', e.g. 'Examination 20..........'
    if key == 'exam_year':
        if val.startswith('20') and len(val) >= 4:
            return val[2:].lstrip()
        return val

    # When template preprints '20', e.g. 'academic session 20..........' (reading and character)
    if key == 'session' and cert_key in ('reading', 'character'):
        if val.startswith('20') and len(val) >= 4:
            return val[2:].lstrip()
        return val
        
    return val

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (0, 20, 120)

def hex_to_reportlab(hex_str):
    try:
        return HexColor(hex_str)
    except Exception:
        return HexColor('#001478')

def get_page_dimensions(config: dict = None) -> tuple[float, float]:
    cfg = config or {}
    # Check if custom explicit width and height points are provided from printer setup
    if cfg.get("custom_width_pt") and cfg.get("custom_height_pt"):
        return (float(cfg["custom_width_pt"]), float(cfg["custom_height_pt"]))
        
    psize = cfg.get("paper_size", "10.5x7.5")
    if psize in PAPER_SIZES:
        return PAPER_SIZES[psize]
    elif psize == "Custom":
        try:
            w_in = float(cfg.get("custom_width_in", 10.5))
            h_in = float(cfg.get("custom_height_in", 7.5))
            return (w_in * 72.0, h_in * 72.0)
        except Exception:
            return PAPER_SIZES["10.5x7.5"]
    return PAPER_SIZES["10.5x7.5"]

class CertificateRenderer:
    def __init__(self):
        self._load_fonts()
        
    def _load_fonts(self):
        windir = os.environ.get('WINDIR', 'C:\\Windows')
        fonts_dir = os.path.join(windir, 'Fonts')
        local_fonts = get_asset_path('assets', 'fonts')

        def find_font(fname):
            p1 = os.path.join(local_fonts, fname)
            if os.path.exists(p1): return p1
            p2 = os.path.join(fonts_dir, fname)
            if os.path.exists(p2): return p2
            # Case-insensitive search in local assets/fonts
            if os.path.exists(local_fonts):
                for f in os.listdir(local_fonts):
                    if f.lower() == fname.lower():
                        return os.path.join(local_fonts, f)
            return None

        self.font_times_bd = find_font('timesbd.ttf')
        self.font_times = find_font('times.ttf')
        self.font_souvenir_li = find_font('SOUVNRLI.TTF')
        self.font_souvenir_di = find_font('SOUVNRDI.TTF')
        self.font_souvenir_l = find_font('SOUVNRL.TTF')
        self.font_souvenir_d = find_font('SOUVNRD.TTF')
        self.font_commercial_script = find_font('COMSCRTN.TTF')

        # Register CommercialScriptBT & Souvenir fonts with ReportLab
        try:
            if self.font_commercial_script:
                for alias in ('CommercialScriptBT', 'CommercialScript BT', 'CommercialScriptBT Regular', 'Commercial Script BT', 'CommercialScript'):
                    if alias not in pdfmetrics.getRegisteredFontNames():
                        pdfmetrics.registerFont(TTFont(alias, self.font_commercial_script))

            if self.font_souvenir_li and 'Souvenir-Lt-Italic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Souvenir-Lt-Italic', self.font_souvenir_li))
            if self.font_souvenir_di and 'Souvenir-Demi-Italic' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Souvenir-Demi-Italic', self.font_souvenir_di))
            if self.font_souvenir_l and 'Souvenir-Lt' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Souvenir-Lt', self.font_souvenir_l))
            if self.font_souvenir_d and 'Souvenir-Demi' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Souvenir-Demi', self.font_souvenir_d))
        except Exception as e:
            print(f"Font registration warning: {e}")

    def get_pil_font(self, size=40, bold=False, italic=True, font_family=None):
        family = str(font_family or '').strip().lower()
        if 'commercial' in family or 'comscrt' in family:
            if self.font_commercial_script and os.path.exists(self.font_commercial_script):
                try:
                    return ImageFont.truetype(self.font_commercial_script, size)
                except Exception:
                    pass

        fpath = None
        if italic and bold and self.font_souvenir_di:
            fpath = self.font_souvenir_di
        elif italic and self.font_souvenir_li:
            fpath = self.font_souvenir_li
        elif bold and self.font_souvenir_d:
            fpath = self.font_souvenir_d
        elif self.font_souvenir_l:
            fpath = self.font_souvenir_l
        elif bold and self.font_times_bd:
            fpath = self.font_times_bd
        elif self.font_times:
            fpath = self.font_times

        if fpath and os.path.exists(fpath):
            try:
                return ImageFont.truetype(fpath, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def render_pil(self, data: dict, mode: str = "full", cert_type: str = "provisional", config: dict = None,
                   highlight_field: str = None, show_crosshairs: bool = False, custom_positions_override: dict = None) -> Image.Image:
        """
        Renders any of the 4 certificates as a high-resolution PIL Image.
        Uses exact baseline text alignment (`anchor='ls'`).
        Optionally highlights an active field with bounding box and crosshairs for alignment tuning.
        """
        cfg = config or {}
        cert_key = cert_type if cert_type in CERT_TYPES else 'provisional'
        active_positions = custom_positions_override or load_positions()
        pos_dict = active_positions.get(cert_key, DEFAULT_POSITIONS.get(cert_key, {}))
        t_info = CERT_TYPES.get(cert_key, CERT_TYPES['provisional'])

        w_pt, h_pt = get_page_dimensions(cfg)
        w_mm = (w_pt / 72.0) * 25.4
        px_per_mm = IMG_W / w_mm if w_mm > 0 else 11.24

        offset_x_px = cfg.get('offset_x_mm', 0.0) * px_per_mm
        offset_y_px = cfg.get('offset_y_mm', 0.0) * px_per_mm

        # Physical 1:1 point-to-pixel scale:
        # Canvas is IMG_W (3000px) over w_pt (756pt for 10.5" certificate)
        # 1 pt = (IMG_W / w_pt) pixels (~3.96825 px/pt)
        px_per_pt = IMG_W / w_pt if w_pt > 0 else 3.96825
        base_font_size = int(round(cfg.get('font_size', 18) * px_per_pt))
        font_color = hex_to_rgb(cfg.get('font_color', '#001478'))
        sl_color = hex_to_rgb(cfg.get('sl_no_color', '#b40000'))
        is_bold = cfg.get('is_bold', False)
        is_italic = cfg.get('is_italic', True)

        template_path = t_info['template']
        if mode == 'full' and os.path.exists(template_path):
            img = Image.open(template_path).convert('RGB')
        else:
            img = Image.new('RGB', (int(IMG_W), int(IMG_H)), (255, 255, 255))
            if mode == 'overlay':
                draw_tmp = ImageDraw.Draw(img)
                draw_tmp.rectangle([40, 40, int(IMG_W)-40, int(IMG_H)-40], outline=(220, 220, 220), width=3)

        draw = ImageDraw.Draw(img)
        font_family = cfg.get('font_family', 'CommercialScriptBT')
        font = self.get_pil_font(size=base_font_size, bold=is_bold, italic=is_italic, font_family=font_family)
        sl_font_size = int(round((cfg.get('font_size', 18) + 1.0) * px_per_pt))
        font_sl = self.get_pil_font(size=sl_font_size, bold=True, italic=True, font_family=font_family)

        def draw_field(key, text, color=font_color, custom_font=font):
            if not text or key not in pos_dict:
                return
            bx, by = pos_dict[key]
            x = bx + offset_x_px
            y = by + offset_y_px
            # Use left-baseline anchor for laser-accurate baseline positioning
            draw.text((x, y), str(text), fill=color, font=custom_font, anchor="ls")

        sl_val = data.get('sl_no', '')
        if cert_key in ('provisional', 'character', 'transfer'):
            reg = data.get('reg_no', '')
            if not sl_val or '/' in str(sl_val) or any(c.isalpha() for c in str(sl_val)):
                sl_val = compute_sl_no('provisional', reg_no=reg)
        elif cert_key == 'reading':
            if not sl_val or (str(sl_val).isdigit() and len(str(sl_val)) <= 4):
                sl_val = compute_sl_no('reading', stream=data.get('stream', ''),
                                       section=data.get('section', ''), class_roll=data.get('class_roll_no', ''))
        draw_field('sl_no', sl_val, color=sl_color, custom_font=font_sl)
        draw_field('student_name', format_field_value(cert_key, 'student_name', data.get('student_name', '')))
        draw_field('father_name', format_field_value(cert_key, 'father_name', data.get('father_name', '')))
        draw_field('mother_name', format_field_value(cert_key, 'mother_name', data.get('mother_name', '')))
        draw_field('address', format_field_value(cert_key, 'address', data.get('address', '')))
        draw_field('exam_year', format_field_value(cert_key, 'exam_year', data.get('exam_year', '')))
        draw_field('roll_no', format_field_value(cert_key, 'roll_no', data.get('roll_no', '')))
        draw_field('grade', format_field_value(cert_key, 'grade', data.get('grade', '')))
        draw_field('session', format_field_value(cert_key, 'session', data.get('session', '')))
        draw_field('dob', format_field_value(cert_key, 'dob', data.get('dob', '')))
        draw_field('reg_no', format_field_value(cert_key, 'reg_no', data.get('reg_no', '')))
        draw_field('result_date', format_field_value(cert_key, 'result_date', data.get('result_date', '')))
        draw_field('left_date', format_field_value(cert_key, 'left_date', data.get('left_date', '')))
        draw_field('pen_no', format_field_value(cert_key, 'pen_no', data.get('pen_no', '')))

        # Reading cert specific
        draw_field('class_name', format_field_value(cert_key, 'class_name', data.get('class_name', '')))
        draw_field('stream', format_field_value(cert_key, 'stream', data.get('stream', '')))
        draw_field('section', format_field_value(cert_key, 'section', data.get('section', '')))
        draw_field('class_roll_no', format_field_value(cert_key, 'class_roll_no', data.get('class_roll_no', '')))

        draw_field('issue_date', format_field_value(cert_key, 'issue_date', data.get('issue_date', '')))

        if cfg.get('strike_unused', False):
            exam = str(data.get('exam_name', '')).upper()
            if 'AISSE' in exam and 'aissce' in pos_dict:
                self._draw_strike_pil(draw, pos_dict['aissce'], offset_x_px, offset_y_px, font_color)
            elif 'AISSCE' in exam and 'aisse' in pos_dict:
                self._draw_strike_pil(draw, pos_dict['aisse'], offset_x_px, offset_y_px, font_color)

            status = str(data.get('status', '')).lower()
            if 'qualified' in status and 'disqualified' in pos_dict:
                self._draw_strike_pil(draw, pos_dict['disqualified'], offset_x_px, offset_y_px, font_color)
            elif 'disqualified' in status and 'qualified' in pos_dict:
                self._draw_strike_pil(draw, pos_dict['qualified'], offset_x_px, offset_y_px, font_color)

        # Draw highlight and crosshairs for visual alignment tuning in Admin Portal
        if highlight_field and highlight_field in pos_dict and len(pos_dict[highlight_field]) == 2:
            hx, hy = pos_dict[highlight_field]
            hx += offset_x_px
            hy += offset_y_px
            f_val = str(data.get(highlight_field, '') or highlight_field)
            f_to_use = font_sl if highlight_field == 'sl_no' else font
            bbox = draw.textbbox((hx, hy), f_val, font=f_to_use, anchor="ls")
            pad = 8
            box = [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad]

            if show_crosshairs:
                # Vertical guide line at starting X
                draw.line([(hx, 0), (hx, int(IMG_H))], fill=(255, 20, 147), width=3)
                # Horizontal guide line at baseline Y
                draw.line([(0, hy), (int(IMG_W), hy)], fill=(0, 200, 80), width=3)

            # Highlight border
            draw.rectangle(box, outline=(255, 20, 147), width=4)

            # Coordinate badge tag
            tag_text = f" {highlight_field.upper()}: X={int(hx)}, Y={int(hy)} "
            tag_font = self.get_pil_font(size=24, bold=True)
            tb = draw.textbbox((box[0], max(10, box[1] - 32)), tag_text, font=tag_font)
            draw.rectangle([tb[0]-2, tb[1]-2, tb[2]+2, tb[3]+2], fill=(255, 20, 147))
            draw.text((box[0], max(10, box[1] - 32)), tag_text, fill=(255, 255, 255), font=tag_font)

        return img

    def _draw_strike_pil(self, draw, coords, ox, oy, color):
        x1, y1, x2, y2 = coords
        draw.line([x1 + ox, y1 + oy, x2 + ox, y2 + oy], fill=color, width=4)

    def render_pdf(self, certificates_data: list, output_pdf_path: str, mode: str = "full", cert_type: str = "provisional",
                   selected_cert_types: list = None, config: dict = None, custom_positions_override: dict = None):
        """
        Generates an exact vector PDF for one or multiple selective certificates.
        selected_cert_types: list of keys (e.g. ['provisional', 'character', 'transfer', 'reading'])
        """
        cfg = config or {}
        w, h = get_page_dimensions(cfg)
        ox_pt = cfg.get('offset_x_mm', 0.0) * 2.83465
        oy_pt = cfg.get('offset_y_mm', 0.0) * 2.83465
        font_size = float(cfg.get('font_size', 18))
        font_color = hex_to_reportlab(cfg.get('font_color', '#001478'))
        sl_color = hex_to_reportlab(cfg.get('sl_no_color', '#b40000'))
        is_bold = cfg.get('is_bold', False)
        is_italic = cfg.get('is_italic', True)
        strike_unused = cfg.get('strike_unused', False)

        # Select font based on font_family configuration
        font_family = str(cfg.get('font_family', 'CommercialScriptBT')).strip()
        registered = pdfmetrics.getRegisteredFontNames()
        if any(k in font_family.lower() for k in ('commercial', 'comscrt')):
            font_name = 'CommercialScriptBT' if 'CommercialScriptBT' in registered else 'Times-Italic'
            sl_font_name = 'CommercialScriptBT' if 'CommercialScriptBT' in registered else 'Times-BoldItalic'
        elif is_italic and is_bold:
            font_name = 'Souvenir-Demi-Italic' if 'Souvenir-Demi-Italic' in registered else 'Times-BoldItalic'
            sl_font_name = 'Souvenir-Demi-Italic' if 'Souvenir-Demi-Italic' in registered else 'Times-BoldItalic'
        elif is_italic:
            font_name = 'Souvenir-Lt-Italic' if 'Souvenir-Lt-Italic' in registered else 'Times-Italic'
            sl_font_name = 'Souvenir-Demi-Italic' if 'Souvenir-Demi-Italic' in registered else 'Times-BoldItalic'
        elif is_bold:
            font_name = 'Souvenir-Demi' if 'Souvenir-Demi' in registered else 'Times-Bold'
            sl_font_name = 'Souvenir-Demi-Italic' if 'Souvenir-Demi-Italic' in registered else 'Times-BoldItalic'
        else:
            font_name = 'Souvenir-Lt' if 'Souvenir-Lt' in registered else 'Times-Roman'
            sl_font_name = 'Souvenir-Demi-Italic' if 'Souvenir-Demi-Italic' in registered else 'Times-BoldItalic'

        os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
        pdf = canvas.Canvas(output_pdf_path, pagesize=(w, h))

        def to_pdf_pt(img_x, img_y):
            px = (img_x / IMG_W) * w + ox_pt
            py = h - (img_y / IMG_H) * h - oy_pt
            return px, py

        # Determine which certificate types to generate
        types_to_render = selected_cert_types if selected_cert_types else [cert_type]
        active_positions = custom_positions_override or load_positions()

        for data in certificates_data:
            for c_key in types_to_render:
                pos_dict = active_positions.get(c_key, DEFAULT_POSITIONS.get(c_key, {}))
                t_info = CERT_TYPES.get(c_key, CERT_TYPES['provisional'])
                tmpl = t_info['template']

                if mode == 'full' and os.path.exists(tmpl):
                    pdf.drawImage(tmpl, 0, 0, width=w, height=h)

                def draw_str(key, text, font_override=None, color_override=None):
                    if not text or key not in pos_dict:
                        return
                    f = font_override or font_name
                    c = color_override or font_color
                    pdf.setFont(f, font_size)
                    pdf.setFillColor(c)
                    x, y = to_pdf_pt(*pos_dict[key])
                    pdf.drawString(x, y, str(text).strip())

                sl_val = data.get('sl_no', '')
                if c_key in ('provisional', 'character', 'transfer'):
                    reg = data.get('reg_no', '')
                    if not sl_val or '/' in str(sl_val) or any(c.isalpha() for c in str(sl_val)):
                        sl_val = compute_sl_no('provisional', reg_no=reg)
                elif c_key == 'reading':
                    if not sl_val or (str(sl_val).isdigit() and len(str(sl_val)) <= 4):
                        sl_val = compute_sl_no('reading', stream=data.get('stream', ''),
                                               section=data.get('section', ''), class_roll=data.get('class_roll_no', ''))

                if sl_val and 'sl_no' in pos_dict:
                    pdf.setFont(sl_font_name, font_size + 1)
                    pdf.setFillColor(sl_color)
                    x, y = to_pdf_pt(*pos_dict['sl_no'])
                    pdf.drawString(x, y, str(sl_val))

                draw_str('student_name', format_field_value(c_key, 'student_name', data.get('student_name', '')))
                draw_str('father_name', format_field_value(c_key, 'father_name', data.get('father_name', '')))
                draw_str('mother_name', format_field_value(c_key, 'mother_name', data.get('mother_name', '')))
                draw_str('address', format_field_value(c_key, 'address', data.get('address', '')))
                draw_str('exam_year', format_field_value(c_key, 'exam_year', data.get('exam_year', '')))
                draw_str('roll_no', format_field_value(c_key, 'roll_no', data.get('roll_no', '')))
                draw_str('grade', format_field_value(c_key, 'grade', data.get('grade', '')))
                draw_str('session', format_field_value(c_key, 'session', data.get('session', '')))
                draw_str('dob', format_field_value(c_key, 'dob', data.get('dob', '')))
                draw_str('reg_no', format_field_value(c_key, 'reg_no', data.get('reg_no', '')))
                draw_str('result_date', format_field_value(c_key, 'result_date', data.get('result_date', '')))
                draw_str('left_date', format_field_value(c_key, 'left_date', data.get('left_date', '')))
                draw_str('pen_no', format_field_value(c_key, 'pen_no', data.get('pen_no', '')))

                draw_str('class_name', format_field_value(c_key, 'class_name', data.get('class_name', '')))
                draw_str('stream', format_field_value(c_key, 'stream', data.get('stream', '')))
                draw_str('section', format_field_value(c_key, 'section', data.get('section', '')))
                draw_str('class_roll_no', format_field_value(c_key, 'class_roll_no', data.get('class_roll_no', '')))

                draw_str('issue_date', format_field_value(c_key, 'issue_date', data.get('issue_date', '')))

                if strike_unused:
                    pdf.setStrokeColor(font_color)
                    pdf.setLineWidth(1.2)

                    def strike_coords(coords):
                        x1, y1, x2, y2 = coords
                        px1, py1 = to_pdf_pt(x1, y1)
                        px2, py2 = to_pdf_pt(x2, y2)
                        pdf.line(px1, py1, px2, py2)

                    exam = str(data.get('exam_name', '')).upper()
                    if 'AISSE' in exam and 'aissce' in pos_dict:
                        strike_coords(pos_dict['aissce'])
                    elif 'AISSCE' in exam and 'aisse' in pos_dict:
                        strike_coords(pos_dict['aisse'])

                    status = str(data.get('status', '')).lower()
                    if 'qualified' in status and 'disqualified' in pos_dict:
                        strike_coords(pos_dict['disqualified'])
                    elif 'disqualified' in status and 'qualified' in pos_dict:
                        strike_coords(pos_dict['qualified'])

                pdf.showPage()

        pdf.save()
        return output_pdf_path

    def render_calibration_sheet(self, output_pdf_path: str, cert_type: str = "provisional", config: dict = None, custom_positions_override: dict = None):
        cfg = config or {}
        w, h = get_page_dimensions(cfg)
        cert_key = cert_type if cert_type in CERT_TYPES else 'provisional'
        active_positions = custom_positions_override or load_positions()
        pos_dict = active_positions.get(cert_key, DEFAULT_POSITIONS.get(cert_key, {}))
        pdf = canvas.Canvas(output_pdf_path, pagesize=(w, h))
        
        pdf.setStrokeColor(HexColor('#000000'))
        pdf.setLineWidth(0.5)
        pdf.line(w/2, 0, w/2, h)
        pdf.line(0, h/2, w, h/2)
        
        m = 10 * 2.83465
        pdf.rect(m, m, w - 2*m, h - 2*m)
        
        pdf.setFont('Helvetica-Bold', 12)
        pdf.drawString(m + 10, h - m - 20, f"MOUNT EVEREST HR. SEC. SCHOOL - {CERT_TYPES[cert_key]['name'].upper()} ({w/72:.1f}\" x {h/72:.1f}\")")
        pdf.setFont('Helvetica', 9)
        pdf.drawString(m + 10, h - m - 35, "1. Print this page at 100% Scale (Actual Size / No scaling).")
        pdf.drawString(m + 10, h - m - 48, "2. Place your pre-printed certificate under or over this sheet against the light.")
        pdf.drawString(m + 10, h - m - 61, "3. Measure horizontal (X) and vertical (Y) offset in millimeters, then adjust in Settings.")
        
        pdf.setStrokeColor(HexColor('#cc0000'))
        pdf.setFillColor(HexColor('#cc0000'))
        for name, val in pos_dict.items():
            if len(val) == 2:
                bx, by = val
                px = (bx / IMG_W) * w
                py = h - (by / IMG_H) * h
                pdf.circle(px, py, 2, fill=1)
                pdf.drawString(px + 4, py - 3, f"{name}")

        pdf.showPage()
        pdf.save()
        return output_pdf_path
