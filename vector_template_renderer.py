# -*- coding: utf-8 -*-
"""
Vector Template Renderer
Renders high-resolution, fully customizable vector certificates for both:
1. PIL (Live GUI preview on canvas)
2. ReportLab (Vector PDF print / export)

Eliminates reliance on static PNG templates while maintaining pixel-perfect
alignment with existing user coordinates.
"""

import os
from PIL import Image, ImageDraw, ImageFont
from path_utils import get_asset_path
from template_manager import load_template_config

IMG_W = 3000.0
IMG_H = 2250.0

# Content boundaries inside the 0.5-inch inner border (161 to 2839 px)
# Providing clean ~69 px padding on both sides for justified layout
LEFT_X = 230
RIGHT_X = 2770

def _draw_dotted_line_pil(draw, x1, y1, x2, y2, color=(40, 40, 40), dot_spacing=14, dot_size=4):
    """Draws a clean dotted baseline guide in PIL."""
    cur_x = x1
    while cur_x <= x2:
        draw.ellipse([cur_x, y1 - dot_size, cur_x + dot_size, y1], fill=color)
        cur_x += dot_spacing

def _draw_dotted_line_pdf(pdf, x1, y1, x2, y2, color_obj=None, dot_spacing=3.5, dot_size=1.0):
    """Draws a clean dotted baseline guide in ReportLab PDF."""
    pdf.saveState()
    if color_obj:
        pdf.setFillColor(color_obj)
    else:
        pdf.setFillColorRGB(0.15, 0.15, 0.15)
    cur_x = x1
    while cur_x <= x2:
        pdf.circle(cur_x, y1, dot_size, fill=1, stroke=0)
        cur_x += dot_spacing
    pdf.restoreState()

def draw_justified_pil(draw, text, x_left, x_right, y, font, color=(15, 23, 42)):
    """Distributes words evenly between x_left and x_right."""
    words = str(text).split()
    if not words: return
    if len(words) == 1:
        draw.text((x_left, y), text, fill=color, font=font, anchor="ls")
        return
    word_widths = [draw.textbbox((0, 0), w, font=font)[2] - draw.textbbox((0, 0), w, font=font)[0] for w in words]
    total_word_width = sum(word_widths)
    available_space = (x_right - x_left) - total_word_width
    
    # Calculate single normal space width
    sp_bb = draw.textbbox((0, 0), "A A", font=font)
    a_bb = draw.textbbox((0, 0), "AA", font=font)
    normal_space = max(10, (sp_bb[2] - sp_bb[0]) - (a_bb[2] - a_bb[0]))
    
    if available_space <= 0 or (available_space / (len(words) - 1)) < normal_space:
        space_width = normal_space
    else:
        space_width = available_space / (len(words) - 1)
        
    cur_x = float(x_left)
    for i, word in enumerate(words):
        draw.text((cur_x, y), word, fill=color, font=font, anchor="ls")
        cur_x += word_widths[i] + space_width

def draw_right_aligned_pil(draw, text, x_right, y, font, color=(15, 23, 42)):
    """Draws text aligned flush with x_right and returns its left edge coordinate."""
    bbox = draw.textbbox((0, 0), str(text), font=font)
    tw = bbox[2] - bbox[0]
    lx = x_right - tw
    draw.text((lx, y), str(text), fill=color, font=font, anchor="ls")
    return lx

def get_default_template_positions(cert_key: str) -> dict:
    """Returns default (x, y) coordinates for all draggable vector template elements."""
    pos = {
        'tmpl_office': (1500, 160),
        'tmpl_school': (1500, 235),
        'tmpl_sub': (1500, 355),
        'tmpl_affiliation': (1500, 425),
        'tmpl_affiliation_no': (1500, 525),
        'tmpl_sl_label': (LEFT_X, 755),
        'tmpl_title': (1500, 660),
        'tmpl_date_block': (1246, 1940) if cert_key == 'transfer' else (LEFT_X, 1940),
        'tmpl_principal_block': (2460, 1940),
    }
    row_defaults = {
        'provisional': [1068, 1155, 1242, 1329, 1416, 1503, 1590, 1677, 1764],
        'character': [1205, 1310, 1415, 1519, 1623],
        'transfer': [969, 1051, 1133, 1214, 1295, 1377, 1459, 1540, 1622, 1703],
        'reading': [1081, 1202, 1323, 1444, 1565, 1686, 1807],
    }
    for i, ry in enumerate(row_defaults.get(cert_key, []), start=1):
        pos[f'tmpl_row_{i}'] = (LEFT_X, ry)
    if cert_key == 'transfer':
        pos['tmpl_wish'] = (1500, 1775)
        pos['tmpl_reasons'] = (LEFT_X, 1835)
    return pos

def get_template_element_labels(cert_key: str) -> list:
    """Returns ordered list of (elem_key, human_label) for the template element selector."""
    items = [
        ('tmpl_office', '[Template] 1. Office Header'),
        ('tmpl_school', '[Template] 2. School Name'),
        ('tmpl_sub', '[Template] 3. Address Line'),
        ('tmpl_affiliation', '[Template] 4. Affiliation Line'),
        ('tmpl_affiliation_no', '[Template] 5. Affiliation No.'),
        ('tmpl_title', '[Template] 6. Certificate Title'),
        ('tmpl_sl_label', '[Template] 7. Sl. No. Label'),
    ]
    row_counts = {'provisional': 9, 'character': 5, 'transfer': 10, 'reading': 7}
    for i in range(1, row_counts.get(cert_key, 0) + 1):
        items.append((f'tmpl_row_{i}', f'[Template] Body Line {i}'))
    if cert_key == 'transfer':
        items.append(('tmpl_wish', '[Template] Wish Line'))
        items.append(('tmpl_reasons', '[Template] Reasons Block'))
    items.append(('tmpl_date_block', '[Template] Footer Date Block'))
    items.append(('tmpl_principal_block', '[Template] Footer Principal Block'))
    return items

def get_template_element_positions(cfg: dict, cert_key: str) -> dict:
    """Merges saved template element positions from cfg over defaults for cert_key."""
    pos = get_default_template_positions(cert_key)
    hp = cfg.get('header_positions', {})
    if isinstance(hp, dict):
        for k, v in hp.items():
            if k in pos and isinstance(v, (list, tuple)) and len(v) == 2:
                pos[k] = (int(v[0]), int(v[1]))
    fp = cfg.get('footer_positions', {})
    if isinstance(fp, dict):
        for k, v in fp.items():
            if k in pos and isinstance(v, (list, tuple)) and len(v) == 2:
                pos[k] = (int(v[0]), int(v[1]))
    cp = cfg.get('certificates', {}).get(cert_key, {}).get('positions', {})
    if isinstance(cp, dict):
        for k, v in cp.items():
            if k in pos and isinstance(v, (list, tuple)) and len(v) == 2:
                pos[k] = (int(v[0]), int(v[1]))
    return pos

def set_template_element_position(cfg: dict, cert_key: str, elem_key: str, x: int, y: int):
    """Stores a dragged template element's (x, y) into cfg."""
    coord = [int(x), int(y)]
    if elem_key in ('tmpl_office', 'tmpl_school', 'tmpl_sub', 'tmpl_affiliation', 'tmpl_affiliation_no', 'tmpl_sl_label'):
        cfg.setdefault('header_positions', {})[elem_key] = coord
    elif elem_key == 'tmpl_principal_block' or (elem_key == 'tmpl_date_block' and cert_key != 'transfer'):
        cfg.setdefault('footer_positions', {})[elem_key] = coord
    else:
        cfg.setdefault('certificates', {}).setdefault(cert_key, {}).setdefault('positions', {})[elem_key] = coord

_BG_PIL_CACHE = None
BG_PAD_PX = 30
BG_X1 = 143 - BG_PAD_PX   # 113
BG_Y1 = 150 - BG_PAD_PX   # 120
BG_W = (2857 + BG_PAD_PX) - BG_X1  # 2774
BG_H = (2100 + BG_PAD_PX) - BG_Y1  # 2010

def _get_bg_pil():
    global _BG_PIL_CACHE
    if _BG_PIL_CACHE is not None and _BG_PIL_CACHE.size == (BG_W, BG_H):
        return _BG_PIL_CACHE
    bg_path = get_asset_path('assets', 'certificate_bg.jpg')
    if os.path.exists(bg_path):
        try:
            _BG_PIL_CACHE = Image.open(bg_path).convert('RGB').resize((BG_W, BG_H), Image.Resampling.LANCZOS)
            return _BG_PIL_CACHE
        except Exception as e:
            print(f"Background image load warning: {e}")
    return None

def render_vector_template_pil(cert_key: str, renderer_instance, custom_tmpl_cfg: dict = None,
                               highlight_element: str = None) -> Image.Image:
    """Renders the complete editable certificate background as a PIL image (3000x2250)."""
    cfg = custom_tmpl_cfg or load_template_config()
    header = cfg.get('header', {})
    footer = cfg.get('footer', {})
    cert_info = cfg.get('certificates', {}).get(cert_key, {})
    epos = get_template_element_positions(cfg, cert_key)
    elem_boxes = {}

    img = Image.new('RGB', (int(IMG_W), int(IMG_H)), (255, 255, 255))
    bg_im = _get_bg_pil()
    if bg_im is not None:
        img.paste(bg_im, (BG_X1, BG_Y1))
    draw = ImageDraw.Draw(img)

    # 1. Elegant Certificate Double Border: Exact 0.5 inches on all 4 sides
    # 10.5 in -> 3000 px => 0.5 in = 143 px; 7.5 in -> 2250 px => 0.5 in = 150 px
    border_col = (15, 30, 60)
    draw.rectangle([143, 150, 2857, 2100], outline=border_col, width=6)
    draw.rectangle([161, 168, 2839, 2082], outline=border_col, width=2)
    # Corner accent squares
    for cx in (143, 2839):
        for cy in (150, 2082):
            draw.rectangle([cx, cy, cx + 18, cy + 18], fill=border_col)

    # 2. Watermark Emblem in Center
    logo_path = get_asset_path('assets', 'app_icon.png')
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert('RGBA')
            logo = logo.resize((820, 820), Image.Resampling.LANCZOS)
            # Create subtle watermark with 10% opacity
            alpha = logo.split()[3]
            alpha = alpha.point(lambda p: int(p * 0.10))
            logo.putalpha(alpha)
            paste_x = int((IMG_W - 820) / 2)
            paste_y = int((IMG_H - 820) / 2) + 60
            img.paste(logo, (paste_x, paste_y), mask=logo)
        except Exception as e:
            print(f"Emblem watermark warning: {e}")

    # Font helpers
    px_per_pt = IMG_W / 756.0

    def get_font(size, bold=False, italic=False, family=None):
        return renderer_instance.get_pil_font(size=size, bold=bold, italic=italic, font_family=family)

    def draw_centered(text, y, font, color=(11, 37, 69), cx=1500, elem_key=None):
        if not text: return
        bbox = draw.textbbox((0, 0), str(text), font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = cx - tw / 2
        draw.text((x, y), str(text), fill=color, font=font, anchor="la")
        if elem_key:
            elem_boxes[elem_key] = [x - 10, y, x + tw + 10, y + th + 20]

    # 3. School Header (Per-line customizable text, font family, font size, and position)
    off_x, off_y = epos['tmpl_office']
    off_font = header.get('office_font', 'Times New Roman')
    off_sz = int(round(float(header.get('office_size', 11)) * px_per_pt))
    f_off = get_font(size=off_sz, bold=True, italic=False, family=off_font)
    draw_centered(header.get('office_title', 'OFFICE OF THE PRINCIPAL'), off_y, f_off, (11, 37, 69), cx=off_x, elem_key='tmpl_office')

    sch_x, sch_y = epos['tmpl_school']
    sch_font = header.get('school_font', 'Times New Roman')
    sch_sz = int(round(float(header.get('school_size', 22)) * px_per_pt))
    f_school = get_font(size=sch_sz, bold=True, italic=False, family=sch_font)
    draw_centered(header.get('school_name', 'MOUNT EVEREST HIGHER SECONDARY SCHOOL'), sch_y, f_school, (11, 37, 69), cx=sch_x, elem_key='tmpl_school')

    sub_x, sub_y = epos['tmpl_sub']
    sub_font = header.get('sub_font', 'Times New Roman')
    sub_sz = int(round(float(header.get('sub_size', 10)) * px_per_pt))
    f_addr = get_font(size=sub_sz, bold=False, italic=True, family=sub_font)
    draw_centered(header.get('sub_title', 'Taphou, Senapati - 795106, Manipur'), sub_y, f_addr, (51, 65, 85), cx=sub_x, elem_key='tmpl_sub')

    aff_x, aff_y = epos['tmpl_affiliation']
    aff_font = header.get('affiliation_font', 'CommercialScriptBT')
    aff_sz = int(round(float(header.get('affiliation_size', 16)) * px_per_pt))
    f_aff = get_font(size=aff_sz, bold=False, italic=True, family=aff_font)
    draw_centered(header.get('affiliation_line', 'Affiliated to Central Board of Secondary Education, New Delhi'), aff_y, f_aff, (0, 20, 120), cx=aff_x, elem_key='tmpl_affiliation')

    aff_no_x, aff_no_y = epos['tmpl_affiliation_no']
    aff_no_font = header.get('affiliation_no_font', 'Times New Roman')
    aff_no_sz = int(round(float(header.get('affiliation_no_size', 12)) * px_per_pt))
    f_aff_no = get_font(size=aff_no_sz, bold=True, italic=False, family=aff_no_font)
    draw_centered(header.get('affiliation_no', 'Affiliation No. 1230048'), aff_no_y, f_aff_no, (11, 37, 69), cx=aff_no_x, elem_key='tmpl_affiliation_no')

    # 4. Certificate Title (Underlined)
    title_x, title_y = epos['tmpl_title']
    cert_title = cert_info.get('title', cert_key.capitalize() + ' Certificate')
    t_font = cert_info.get('title_font', 'Times New Roman')
    t_sz = int(round(float(cert_info.get('title_size', 18)) * px_per_pt))
    f_title = get_font(size=t_sz, bold=True, italic=False, family=t_font)
    draw_centered(cert_title, title_y, f_title, (0, 30, 98), cx=title_x, elem_key='tmpl_title')
    if cert_title:
        t_bbox = draw.textbbox((0, 0), str(cert_title), font=f_title)
        ref_bbox = draw.textbbox((0, 0), str(cert_title) + "g", font=f_title)
        t_w = t_bbox[2] - t_bbox[0]
        t_x = title_x - t_w / 2
        t_ul_y = title_y + (ref_bbox[3] - ref_bbox[1]) + 14
        draw.line([(t_x, t_ul_y), (t_x + t_w, t_ul_y)], fill=(0, 30, 98), width=5)

    # 5. Sl. No. Label (on left margin)
    sl_x, sl_y = epos['tmpl_sl_label']
    b_font = cfg.get('body_font', 'Times New Roman')
    b_sz = int(round(float(cfg.get('body_size', 11)) * px_per_pt))
    f_body = get_font(size=b_sz, bold=False, italic=False, family=b_font)
    f_sl = get_font(size=int(round((float(cfg.get('body_size', 11)) + 1.0) * px_per_pt)), bold=True, italic=True, family=b_font)
    draw.text((sl_x, sl_y), header.get('sl_label', 'Sl. No.'), fill=(11, 37, 69), font=f_sl, anchor="ls")
    sl_w = draw.textbbox((0, 0), header.get('sl_label', 'Sl. No.'), font=f_sl)[2]
    _draw_dotted_line_pil(draw, sl_x + sl_w + 15, sl_y, sl_x + 600, sl_y)
    elem_boxes['tmpl_sl_label'] = [sl_x - 8, sl_y - 50, sl_x + 600, sl_y + 12]

    # 6. Static Body Text & Dotted Lines per Certificate - Justified Layout
    def draw_txt(text, x, y, font=f_body, color=(15, 23, 42)):
        draw.text((x, y), text, fill=color, font=font, anchor="ls")
        bb = draw.textbbox((x, y), text, font=font, anchor="ls")
        return bb[2]  # right edge

    if cert_key == 'provisional':
        def row_xy(idx):
            px, py = epos[f'tmpl_row_{idx}']
            elem_boxes[f'tmpl_row_{idx}'] = [px - 8, py - 48, RIGHT_X + (px - LEFT_X) + 8, py + 12]
            return px, py, px - LEFT_X

        x1, y1, dx1 = row_xy(1)
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        _draw_dotted_line_pil(draw, rx + 15, y1, RIGHT_X + dx1, y1)

        x2, y2, dx2 = row_xy(2)
        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        _draw_dotted_line_pil(draw, rx1 + 15, y2, 1525 + dx2, y2)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        _draw_dotted_line_pil(draw, rx2 + 15, y2, RIGHT_X + dx2, y2)

        x3, y3, dx3 = row_xy(3)
        rx = draw_txt(cert_info.get('line_inhabitant', 'an inhabitant of'), x3, y3)
        _draw_dotted_line_pil(draw, rx + 15, y3, RIGHT_X + dx3, y3)

        x4, y4, dx4 = row_xy(4)
        rx = draw_txt(cert_info.get('line_exam', 'appeared the  AISSE/AISSCE  20'), x4, y4)
        _draw_dotted_line_pil(draw, rx + 15, y4, 1205 + dx4, y4)
        rx2 = draw_txt(cert_info.get('line_roll', 'bearing Roll No.'), 1225 + dx4, y4)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of'), RIGHT_X + dx4, y4, font=f_body)
        _draw_dotted_line_pil(draw, rx2 + 15, y4, board_lx - 15, y4)

        x5, y5, dx5 = row_xy(5)
        draw_justified_pil(draw, cert_info.get('line_decl', 'Secondary Education, New Delhi was declared to have qualified the said Examination and was placed in the'), x5, RIGHT_X + dx5, y5, font=f_body)

        x6, y6, dx6 = row_xy(6)
        rx = draw_txt(cert_info.get('line_grade', 'grade'), x6, y6)
        nic_lx = draw_right_aligned_pil(draw, cert_info.get('line_nic', 'as per CBSE result uploaded by National Informatics Centre (NIC), New Delhi.'), RIGHT_X + dx6, y6, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, y6, nic_lx - 20, y6)

        x7, y7, dx7 = row_xy(7)
        rx = draw_txt(cert_info.get('line_dob', 'His/her date of birth according to the school admission record is'), x7, y7)
        _draw_dotted_line_pil(draw, rx + 15, y7, RIGHT_X + dx7, y7)

        x8, y8, dx8 = row_xy(8)
        rx = draw_txt(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), x8, y8)
        _draw_dotted_line_pil(draw, rx + 15, y8, RIGHT_X + dx8, y8)

        x9, y9, dx9 = row_xy(9)
        rx = draw_txt(cert_info.get('line_result', 'The result of the said Examination was announced on'), x9, y9)
        _draw_dotted_line_pil(draw, rx + 15, y9, RIGHT_X + dx9, y9)

    elif cert_key == 'character':
        def row_xy(idx):
            px, py = epos[f'tmpl_row_{idx}']
            elem_boxes[f'tmpl_row_{idx}'] = [px - 8, py - 48, RIGHT_X + (px - LEFT_X) + 8, py + 12]
            return px, py, px - LEFT_X

        x1, y1, dx1 = row_xy(1)
        conduct_txt = cert_info.get('line_conduct', 'This is to certify that the conduct and character of').strip()
        prefix_txt = cert_info.get('line_student_prefix', 'Mr./Miss').strip()
        first_line_txt = f"{conduct_txt} {prefix_txt}".strip()
        rx = draw_txt(first_line_txt, x1, y1)
        _draw_dotted_line_pil(draw, rx + 15, y1, RIGHT_X + dx1, y1)

        x2, y2, dx2 = row_xy(2)
        status_txt = cert_info.get('line_status', 'qualified/disqualified the AISSE/AISSCE, 20').strip()
        if not status_txt.lower().startswith('qualified/'):
            status_txt = f"qualified/{status_txt}"
        rx = draw_txt(status_txt, x2, y2)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of Secondary Education, New Delhi'), RIGHT_X + dx2, y2, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, y2, board_lx - 15, y2)

        x3, y3, dx3 = row_xy(3)
        rx = draw_txt('bearing Roll No.', x3, y3)
        placed_lx = draw_right_aligned_pil(draw, cert_info.get('line_placed', 'was placed in the grade'), RIGHT_X + dx3, y3, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, y3, placed_lx - 15, y3)

        x4, y4, dx4 = row_xy(4)
        draw_justified_pil(draw, cert_info.get('line_nic', 'by National Informatics Centre (NIC), New Delhi is found satisfactory during the'), x4, RIGHT_X + dx4, y4, font=f_body)

        x5, y5, dx5 = row_xy(5)
        rx = draw_txt(cert_info.get('line_satisfactory', 'academic session 20'), x5, y5)
        _draw_dotted_line_pil(draw, rx + 15, y5, 1550 + dx5, y5)

    elif cert_key == 'transfer':
        def row_xy(idx):
            px, py = epos[f'tmpl_row_{idx}']
            elem_boxes[f'tmpl_row_{idx}'] = [px - 8, py - 48, RIGHT_X + (px - LEFT_X) + 8, py + 12]
            return px, py, px - LEFT_X

        x1, y1, dx1 = row_xy(1)
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        _draw_dotted_line_pil(draw, rx + 15, y1, RIGHT_X + dx1, y1)

        x2, y2, dx2 = row_xy(2)
        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        _draw_dotted_line_pil(draw, rx1 + 15, y2, 1525 + dx2, y2)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        _draw_dotted_line_pil(draw, rx2 + 15, y2, RIGHT_X + dx2, y2)

        x3, y3, dx3 = row_xy(3)
        rx = draw_txt(cert_info.get('line_status', 'was declared to have qualified/disqualified the AISSE/AISSCE, 20'), x3, y3)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of Secondary'), RIGHT_X + dx3, y3, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, y3, board_lx - 15, y3)

        x4, y4, dx4 = row_xy(4)
        rx = draw_txt(cert_info.get('line_roll', 'Education, New Delhi, bearing Roll No.'), x4, y4)
        _draw_dotted_line_pil(draw, rx + 15, y4, 1605 + dx4, y4)
        rx2 = draw_txt(cert_info.get('line_placed', 'was placed in the grade'), 1625 + dx4, y4)
        _draw_dotted_line_pil(draw, rx2 + 15, y4, RIGHT_X + dx4, y4)

        x5, y5, dx5 = row_xy(5)
        draw_justified_pil(draw, cert_info.get('line_nic', 'as per CBSE result list uploaded by National Informatics Centre (NIC), New Delhi. He/She has cleared'), x5, RIGHT_X + dx5, y5, font=f_body)

        x6, y6, dx6 = row_xy(6)
        rx = draw_txt(cert_info.get('line_dues', 'fees/dues payable to this institute during the academic session'), x6, y6)
        _draw_dotted_line_pil(draw, rx + 15, y6, RIGHT_X + dx6, y6)

        x7, y7, dx7 = row_xy(7)
        rx = draw_txt(cert_info.get('line_dob', 'His/Her date of birth according to the school admission record is'), x7, y7)
        _draw_dotted_line_pil(draw, rx + 15, y7, RIGHT_X + dx7, y7)

        x8, y8, dx8 = row_xy(8)
        rx = draw_txt(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), x8, y8)
        _draw_dotted_line_pil(draw, rx + 15, y8, RIGHT_X + dx8, y8)

        x9, y9, dx9 = row_xy(9)
        rx = draw_txt(cert_info.get('line_left', 'He/She left this school on'), x9, y9)
        _draw_dotted_line_pil(draw, rx + 15, y9, RIGHT_X + dx9, y9)

        x10, y10, dx10 = row_xy(10)
        rx = draw_txt(cert_info.get('line_pen', 'His/Her PEN No.'), x10, y10)
        _draw_dotted_line_pil(draw, rx + 15, y10, 1850 + dx10, y10)

        wx, wy = epos['tmpl_wish']
        draw_centered(cert_info.get('wish_text', 'We wish him/her a bright future.'), wy, get_font(size=38, italic=True), (11, 37, 69), cx=wx, elem_key='tmpl_wish')

        rsx, rsy = epos['tmpl_reasons']
        draw_txt(cert_info.get('reasons_title', 'REASONS OF LEAVING:'), rsx, rsy, font=get_font(size=32, bold=True))
        f_reasons = get_font(size=28, bold=False)
        draw_txt("i)   Completion of Course.", rsx, rsy + 40, font=f_reasons)
        draw_txt("ii)  Ill Health", rsx, rsy + 78, font=f_reasons)
        draw_txt("iii) Change of Residence", rsx, rsy + 116, font=f_reasons)
        draw_txt("iv)  Student’s Choice/Parent’s Choice", rsx, rsy + 154, font=f_reasons)
        draw_txt("v)   Other Reasons", rsx, rsy + 192, font=f_reasons)
        elem_boxes['tmpl_reasons'] = [rsx - 8, rsy - 36, rsx + 680, rsy + 205]

    elif cert_key == 'reading':
        def row_xy(idx):
            px, py = epos[f'tmpl_row_{idx}']
            elem_boxes[f'tmpl_row_{idx}'] = [px - 8, py - 48, RIGHT_X + (px - LEFT_X) + 8, py + 12]
            return px, py, px - LEFT_X

        x1, y1, dx1 = row_xy(1)
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        _draw_dotted_line_pil(draw, rx + 15, y1, RIGHT_X + dx1, y1)

        x2, y2, dx2 = row_xy(2)
        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        _draw_dotted_line_pil(draw, rx1 + 15, y2, 1525 + dx2, y2)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        _draw_dotted_line_pil(draw, rx2 + 15, y2, RIGHT_X + dx2, y2)

        x3, y3, dx3 = row_xy(3)
        rx = draw_txt(cert_info.get('line_inhabitant', 'an inhabitant of'), x3, y3)
        _draw_dotted_line_pil(draw, rx + 15, y3, RIGHT_X + dx3, y3)

        x4, y4, dx4 = row_xy(4)
        rx = draw_txt(cert_info.get('line_reading', 'is reading in class'), x4, y4)
        _draw_dotted_line_pil(draw, rx + 15, y4, 1000 + dx4, y4)
        rx2 = draw_txt(cert_info.get('line_stream', 'Stream'), 1020 + dx4, y4)
        _draw_dotted_line_pil(draw, rx2 + 15, y4, 1500 + dx4, y4)
        rx3 = draw_txt(cert_info.get('line_section', 'Section'), 1520 + dx4, y4)
        _draw_dotted_line_pil(draw, rx3 + 15, y4, 1920 + dx4, y4)
        rx4 = draw_txt(cert_info.get('line_roll', 'bearing class Roll No.'), 1940 + dx4, y4)
        _draw_dotted_line_pil(draw, rx4 + 15, y4, RIGHT_X + dx4, y4)

        x5, y5, dx5 = row_xy(5)
        rx = draw_txt(cert_info.get('line_session', 'of this School during the academic session 20'), x5, y5)
        _draw_dotted_line_pil(draw, rx + 15, y5, 1800 + dx5, y5)

        x6, y6, dx6 = row_xy(6)
        rx = draw_txt(cert_info.get('line_dob', 'His/Her date of birth as recorded in the school registered is'), x6, y6)
        _draw_dotted_line_pil(draw, rx + 15, y6, RIGHT_X + dx6, y6)

        x7, y7, dx7 = row_xy(7)
        draw_txt(cert_info.get('line_character', 'He/She bears a good moral character.'), x7, y7)

    # 7. Common Footer (Common font, size & draggable positions)
    foot_font = footer.get('footer_font', 'Times New Roman')
    foot_sz = int(round(float(footer.get('footer_size', 11)) * px_per_pt))
    f_foot = get_font(size=foot_sz, bold=False, italic=False, family=foot_font)
    f_princ = get_font(size=int(round((float(footer.get('footer_size', 11)) + 1.0) * px_per_pt)), bold=True, family=foot_font)
    f_sch_f = get_font(size=foot_sz, bold=False, family=foot_font)

    df_x, df_y = epos['tmpl_date_block']
    draw.text((df_x, df_y), footer.get('date_prefix', 'Dated, Senapati'), fill=(15, 23, 42), font=f_foot, anchor="ls")
    draw.text((df_x, df_y + 84), footer.get('date_label', 'The'), fill=(15, 23, 42), font=f_foot, anchor="ls")
    _draw_dotted_line_pil(draw, df_x + 90, df_y + 84, df_x + 580, df_y + 84)
    elem_boxes['tmpl_date_block'] = [df_x - 8, df_y - 45, df_x + 585, df_y + 96]

    pr_x, pr_y = epos['tmpl_principal_block']
    draw.text((pr_x, pr_y), footer.get('principal_title', 'Principal,'), fill=(11, 37, 69), font=f_princ, anchor="ms")
    draw.text((pr_x, pr_y + 84), footer.get('school_footer', 'Mount Everest Hr. Sec. School'), fill=(11, 37, 69), font=f_sch_f, anchor="ms")
    elem_boxes['tmpl_principal_block'] = [pr_x - 280, pr_y - 45, pr_x + 280, pr_y + 98]

    # Highlight active dragged/selected template element
    if highlight_element and highlight_element in epos:
        hx, hy = epos[highlight_element]
        # Vertical & horizontal alignment crosshairs
        draw.line([(hx, 0), (hx, int(IMG_H))], fill=(37, 99, 235), width=3)
        draw.line([(0, hy), (int(IMG_W), hy)], fill=(16, 185, 129), width=3)
        box = elem_boxes.get(highlight_element, [hx - 120, hy - 40, hx + 120, hy + 40])
        draw.rectangle(box, outline=(37, 99, 235), width=4)
        tag_text = f" {highlight_element.replace('tmpl_', '').upper()}: X={int(hx)}, Y={int(hy)} "
        tag_font = get_font(size=24, bold=True)
        ty = max(10, box[1] - 32)
        tb = draw.textbbox((max(10, box[0]), ty), tag_text, font=tag_font)
        draw.rectangle([tb[0] - 4, tb[1] - 4, tb[2] + 4, tb[3] + 4], fill=(37, 99, 235))
        draw.text((max(10, box[0]), ty), tag_text, fill=(255, 255, 255), font=tag_font)

    return img


def draw_vector_template_pdf(pdf, cert_key: str, renderer_instance, w: float, h: float, to_pdf_pt_func, custom_tmpl_cfg: dict = None):
    """Draws the complete editable certificate background vectorially in ReportLab PDF."""
    from reportlab.lib.colors import HexColor

    cfg = custom_tmpl_cfg or load_template_config()
    header = cfg.get('header', {})
    footer = cfg.get('footer', {})
    cert_info = cfg.get('certificates', {}).get(cert_key, {})
    epos = get_template_element_positions(cfg, cert_key)

    col_border = HexColor('#0F1E3C')
    col_navy = HexColor('#0B2545')
    col_dark = HexColor('#0F172A')
    col_title = HexColor('#001E62')
    col_blue = HexColor('#001478')

    # 0. Security Pattern Background (just beyond the outer border)
    bg_path = get_asset_path('assets', 'certificate_bg.jpg')
    if os.path.exists(bg_path):
        try:
            bg_x_pt = (BG_X1 / IMG_W) * w
            bg_y_pt = (BG_Y1 / IMG_H) * h
            bg_w_pt = (BG_W / IMG_W) * w
            bg_h_pt = (BG_H / IMG_H) * h
            pdf.drawImage(bg_path, bg_x_pt, bg_y_pt, width=bg_w_pt, height=bg_h_pt)
        except Exception as e:
            print(f"PDF background warning: {e}")

    # 1. Elegant Certificate Double Border: Exact 0.5 inches space on all sides (36.0 pt)
    pdf.saveState()
    pdf.setStrokeColor(col_border)
    pdf.setLineWidth(2.2)
    pdf.rect(36.0, 36.0, w - 72.0, h - 72.0)

    pdf.setLineWidth(0.8)
    pdf.rect(40.5, 40.5, w - 81.0, h - 81.0)

    # Corner accent blocks
    pdf.setFillColor(col_border)
    for cx in (36.0, w - 40.5):
        for cy in (36.0, h - 40.5):
            pdf.rect(cx, cy, 4.5, 4.5, fill=1, stroke=0)
    pdf.restoreState()

    # 2. Watermark Emblem
    logo_path = get_asset_path('assets', 'app_icon.png')
    if os.path.exists(logo_path):
        try:
            pdf.saveState()
            ew = (820 / IMG_W) * w
            eh = (820 / IMG_H) * h
            ex = (w - ew) / 2
            ey = (h - eh) / 2 - (60 / IMG_H) * h
            try:
                pdf.setFillAlpha(0.10)
            except Exception:
                pass
            pdf.drawImage(logo_path, ex, ey, width=ew, height=eh, mask='auto', preserveAspectRatio=True)
            pdf.restoreState()
        except Exception:
            pass

    # Helper functions for PDF text
    def draw_center_pdf(text, img_y, font_name, font_pt, color_obj, img_x=1500):
        if not text: return
        px, py = to_pdf_pt_func(img_x, img_y)
        pdf.saveState()
        pdf.setFont(font_name, font_pt)
        pdf.setFillColor(color_obj)
        pdf.drawCentredString(px, py, str(text))
        pdf.restoreState()

    def draw_txt_pdf(text, img_x, img_y, font_name=None, font_pt=None, color_obj=col_dark):
        fn = font_name or renderer_instance.get_reportlab_font(cfg.get('body_font', 'Times New Roman'), bold=False)
        fpt = float(font_pt or cfg.get('body_size', 11.5))
        px, py = to_pdf_pt_func(img_x, img_y)
        pdf.saveState()
        pdf.setFont(fn, fpt)
        pdf.setFillColor(color_obj)
        pdf.drawString(px, py, str(text))
        sw = pdf.stringWidth(str(text), fn, fpt)
        pdf.restoreState()
        # Return right edge in image coordinates
        return img_x + (sw / w) * IMG_W

    def draw_justified_pdf(text, img_x_left, img_x_right, img_y, font_name=None, font_pt=None, color_obj=col_dark):
        words = str(text).split()
        if not words: return
        fn = font_name or renderer_instance.get_reportlab_font(cfg.get('body_font', 'Times New Roman'), bold=False)
        fpt = float(font_pt or cfg.get('body_size', 11.5))
        px_left, py = to_pdf_pt_func(img_x_left, img_y)
        px_right, _ = to_pdf_pt_func(img_x_right, img_y)
        line_width = px_right - px_left

        pdf.saveState()
        pdf.setFont(fn, fpt)
        pdf.setFillColor(color_obj)

        if len(words) == 1:
            pdf.drawString(px_left, py, text)
            pdf.restoreState()
            return

        word_widths = [pdf.stringWidth(w_str, fn, fpt) for w_str in words]
        total_word_width = sum(word_widths)
        available_space = line_width - total_word_width
        normal_space = max(2.5, pdf.stringWidth(" ", fn, fpt))

        if available_space <= 0 or (available_space / (len(words) - 1)) < normal_space:
            space_width = normal_space
        else:
            space_width = available_space / (len(words) - 1)

        cur_x = px_left
        for i, word in enumerate(words):
            pdf.drawString(cur_x, py, word)
            cur_x += word_widths[i] + space_width

        pdf.restoreState()

    def draw_right_pdf(text, img_x_right, img_y, font_name=None, font_pt=None, color_obj=col_dark):
        fn = font_name or renderer_instance.get_reportlab_font(cfg.get('body_font', 'Times New Roman'), bold=False)
        fpt = float(font_pt or cfg.get('body_size', 11.5))
        px_right, py = to_pdf_pt_func(img_x_right, img_y)
        sw = pdf.stringWidth(str(text), fn, fpt)
        pdf.saveState()
        pdf.setFont(fn, fpt)
        pdf.setFillColor(color_obj)
        pdf.drawRightString(px_right, py, str(text))
        pdf.restoreState()
        return img_x_right - (sw / w) * IMG_W

    def draw_dotted_pdf(img_x1, img_y, img_x2):
        px1, py = to_pdf_pt_func(img_x1, img_y)
        px2, _ = to_pdf_pt_func(img_x2, img_y)
        _draw_dotted_line_pdf(pdf, px1, py, px2, py)

    # 3. Headers (Per-line customizable font, size & position in PDF)
    off_x, off_y = epos['tmpl_office']
    off_fn = renderer_instance.get_reportlab_font(header.get('office_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('office_title', 'OFFICE OF THE PRINCIPAL'), off_y + 30, off_fn, float(header.get('office_size', 10.5)), col_navy, img_x=off_x)

    sch_x, sch_y = epos['tmpl_school']
    sch_fn = renderer_instance.get_reportlab_font(header.get('school_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('school_name', 'MOUNT EVEREST HIGHER SECONDARY SCHOOL'), sch_y + 60, sch_fn, float(header.get('school_size', 21.0)), col_navy, img_x=sch_x)

    sub_x, sub_y = epos['tmpl_sub']
    sub_fn = renderer_instance.get_reportlab_font(header.get('sub_font', 'Times New Roman'), italic=True)
    draw_center_pdf(header.get('sub_title', 'Taphou, Senapati - 795106, Manipur'), sub_y + 25, sub_fn, float(header.get('sub_size', 9.5)), HexColor('#334155'), img_x=sub_x)

    aff_x, aff_y = epos['tmpl_affiliation']
    aff_fn = renderer_instance.get_reportlab_font(header.get('affiliation_font', 'CommercialScriptBT'), italic=True)
    draw_center_pdf(header.get('affiliation_line', 'Affiliated to Central Board of Secondary Education, New Delhi'), aff_y + 40, aff_fn, float(header.get('affiliation_size', 16.0)), col_blue, img_x=aff_x)

    aff_no_x, aff_no_y = epos['tmpl_affiliation_no']
    aff_no_fn = renderer_instance.get_reportlab_font(header.get('affiliation_no_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('affiliation_no', 'Affiliation No. 1230048'), aff_no_y + 25, aff_no_fn, float(header.get('affiliation_no_size', 11.5)), col_navy, img_x=aff_no_x)

    # 4. Title (Underlined)
    title_x, title_y = epos['tmpl_title']
    cert_title = cert_info.get('title', cert_key.capitalize() + ' Certificate')
    t_fn = renderer_instance.get_reportlab_font(cert_info.get('title_font', 'Times New Roman'), bold=True)
    t_pt = float(cert_info.get('title_size', 18.0))
    draw_center_pdf(cert_title, title_y + 55, t_fn, t_pt, col_title, img_x=title_x)
    if cert_title:
        px_title, py_title = to_pdf_pt_func(title_x, title_y + 55)
        sw_title = pdf.stringWidth(str(cert_title), t_fn, t_pt)
        pdf.saveState()
        pdf.setStrokeColor(col_title)
        pdf.setLineWidth(1.4)
        pdf.line(px_title - sw_title / 2.0, py_title - 3.5, px_title + sw_title / 2.0, py_title - 3.5)
        pdf.restoreState()

    # 5. Sl. No. Label (on left margin)
    sl_x, sl_y = epos['tmpl_sl_label']
    sl_fn = renderer_instance.get_reportlab_font(cfg.get('body_font', 'Times New Roman'), bold=True, italic=True)
    sl_rx = draw_txt_pdf(header.get('sl_label', 'Sl. No.'), sl_x, sl_y, sl_fn, float(cfg.get('body_size', 11.5)) + 1, col_navy)
    draw_dotted_pdf(sl_rx + 15, sl_y, sl_x + 600)

    # 6. Body Text per certificate - Justified Layout
    def row_xy_pdf(idx):
        px, py = epos[f'tmpl_row_{idx}']
        return px, py, px - LEFT_X

    if cert_key == 'provisional':
        x1, y1, dx1 = row_xy_pdf(1)
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        draw_dotted_pdf(rx + 15, y1, RIGHT_X + dx1)

        x2, y2, dx2 = row_xy_pdf(2)
        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        draw_dotted_pdf(rx1 + 15, y2, 1525 + dx2)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        draw_dotted_pdf(rx2 + 15, y2, RIGHT_X + dx2)

        x3, y3, dx3 = row_xy_pdf(3)
        rx = draw_txt_pdf(cert_info.get('line_inhabitant', 'an inhabitant of'), x3, y3)
        draw_dotted_pdf(rx + 15, y3, RIGHT_X + dx3)

        x4, y4, dx4 = row_xy_pdf(4)
        rx = draw_txt_pdf(cert_info.get('line_exam', 'appeared the  AISSE/AISSCE  20'), x4, y4)
        draw_dotted_pdf(rx + 15, y4, 1205 + dx4)
        rx2 = draw_txt_pdf(cert_info.get('line_roll', 'bearing Roll No.'), 1225 + dx4, y4)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of'), RIGHT_X + dx4, y4)
        draw_dotted_pdf(rx2 + 15, y4, board_lx - 15)

        x5, y5, dx5 = row_xy_pdf(5)
        draw_justified_pdf(cert_info.get('line_decl', 'Secondary Education, New Delhi was declared to have qualified the said Examination and was placed in the'), x5, RIGHT_X + dx5, y5)

        x6, y6, dx6 = row_xy_pdf(6)
        rx = draw_txt_pdf(cert_info.get('line_grade', 'grade'), x6, y6)
        nic_lx = draw_right_pdf(cert_info.get('line_nic', 'as per CBSE result uploaded by National Informatics Centre (NIC), New Delhi.'), RIGHT_X + dx6, y6)
        draw_dotted_pdf(rx + 15, y6, nic_lx - 20)

        x7, y7, dx7 = row_xy_pdf(7)
        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/her date of birth according to the school admission record is'), x7, y7)
        draw_dotted_pdf(rx + 15, y7, RIGHT_X + dx7)

        x8, y8, dx8 = row_xy_pdf(8)
        rx = draw_txt_pdf(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), x8, y8)
        draw_dotted_pdf(rx + 15, y8, RIGHT_X + dx8)

        x9, y9, dx9 = row_xy_pdf(9)
        rx = draw_txt_pdf(cert_info.get('line_result', 'The result of the said Examination was announced on'), x9, y9)
        draw_dotted_pdf(rx + 15, y9, RIGHT_X + dx9)

    elif cert_key == 'character':
        x1, y1, dx1 = row_xy_pdf(1)
        conduct_txt = cert_info.get('line_conduct', 'This is to certify that the conduct and character of').strip()
        prefix_txt = cert_info.get('line_student_prefix', 'Mr./Miss').strip()
        first_line_txt = f"{conduct_txt} {prefix_txt}".strip()
        rx = draw_txt_pdf(first_line_txt, x1, y1)
        draw_dotted_pdf(rx + 15, y1, RIGHT_X + dx1)

        x2, y2, dx2 = row_xy_pdf(2)
        status_txt = cert_info.get('line_status', 'qualified/disqualified the AISSE/AISSCE, 20').strip()
        if not status_txt.lower().startswith('qualified/'):
            status_txt = f"qualified/{status_txt}"
        rx = draw_txt_pdf(status_txt, x2, y2)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of Secondary Education, New Delhi'), RIGHT_X + dx2, y2)
        draw_dotted_pdf(rx + 15, y2, board_lx - 15)

        x3, y3, dx3 = row_xy_pdf(3)
        rx = draw_txt_pdf('bearing Roll No.', x3, y3)
        placed_lx = draw_right_pdf(cert_info.get('line_placed', 'was placed in the grade'), RIGHT_X + dx3, y3)
        draw_dotted_pdf(rx + 15, y3, placed_lx - 15)

        x4, y4, dx4 = row_xy_pdf(4)
        draw_justified_pdf(cert_info.get('line_nic', 'by National Informatics Centre (NIC), New Delhi is found satisfactory during the'), x4, RIGHT_X + dx4, y4)

        x5, y5, dx5 = row_xy_pdf(5)
        rx = draw_txt_pdf(cert_info.get('line_satisfactory', 'academic session 20'), x5, y5)
        draw_dotted_pdf(rx + 15, y5, 1550 + dx5)

    elif cert_key == 'transfer':
        x1, y1, dx1 = row_xy_pdf(1)
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        draw_dotted_pdf(rx + 15, y1, RIGHT_X + dx1)

        x2, y2, dx2 = row_xy_pdf(2)
        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        draw_dotted_pdf(rx1 + 15, y2, 1525 + dx2)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        draw_dotted_pdf(rx2 + 15, y2, RIGHT_X + dx2)

        x3, y3, dx3 = row_xy_pdf(3)
        rx = draw_txt_pdf(cert_info.get('line_status', 'was declared to have qualified/disqualified the AISSE/AISSCE, 20'), x3, y3)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of Secondary'), RIGHT_X + dx3, y3)
        draw_dotted_pdf(rx + 15, y3, board_lx - 15)

        x4, y4, dx4 = row_xy_pdf(4)
        rx = draw_txt_pdf(cert_info.get('line_roll', 'Education, New Delhi, bearing Roll No.'), x4, y4)
        draw_dotted_pdf(rx + 15, y4, 1605 + dx4)
        rx2 = draw_txt_pdf(cert_info.get('line_placed', 'was placed in the grade'), 1625 + dx4, y4)
        draw_dotted_pdf(rx2 + 15, y4, RIGHT_X + dx4)

        x5, y5, dx5 = row_xy_pdf(5)
        draw_justified_pdf(cert_info.get('line_nic', 'as per CBSE result list uploaded by National Informatics Centre (NIC), New Delhi. He/She has cleared'), x5, RIGHT_X + dx5, y5)

        x6, y6, dx6 = row_xy_pdf(6)
        rx = draw_txt_pdf(cert_info.get('line_dues', 'fees/dues payable to this institute during the academic session'), x6, y6)
        draw_dotted_pdf(rx + 15, y6, RIGHT_X + dx6)

        x7, y7, dx7 = row_xy_pdf(7)
        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/Her date of birth according to the school admission record is'), x7, y7)
        draw_dotted_pdf(rx + 15, y7, RIGHT_X + dx7)

        x8, y8, dx8 = row_xy_pdf(8)
        rx = draw_txt_pdf(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), x8, y8)
        draw_dotted_pdf(rx + 15, y8, RIGHT_X + dx8)

        x9, y9, dx9 = row_xy_pdf(9)
        rx = draw_txt_pdf(cert_info.get('line_left', 'He/She left this school on'), x9, y9)
        draw_dotted_pdf(rx + 15, y9, RIGHT_X + dx9)

        x10, y10, dx10 = row_xy_pdf(10)
        rx = draw_txt_pdf(cert_info.get('line_pen', 'His/Her PEN No.'), x10, y10)
        draw_dotted_pdf(rx + 15, y10, 1850 + dx10)

        wx, wy = epos['tmpl_wish']
        draw_center_pdf(cert_info.get('wish_text', 'We wish him/her a bright future.'), wy, "Times-Italic", 9.5, col_navy, img_x=wx)

        rsx, rsy = epos['tmpl_reasons']
        draw_txt_pdf(cert_info.get('reasons_title', 'REASONS OF LEAVING:'), rsx, rsy, "Times-Bold", 8.5)
        draw_txt_pdf("i)   Completion of Course.", rsx, rsy + 40, "Times-Roman", 8)
        draw_txt_pdf("ii)  Ill Health", rsx, rsy + 78, "Times-Roman", 8)
        draw_txt_pdf("iii) Change of Residence", rsx, rsy + 116, "Times-Roman", 8)
        draw_txt_pdf("iv)  Student’s Choice/Parent’s Choice", rsx, rsy + 154, "Times-Roman", 8)
        draw_txt_pdf("v)   Other Reasons", rsx, rsy + 192, "Times-Roman", 8)

    elif cert_key == 'reading':
        x1, y1, dx1 = row_xy_pdf(1)
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), x1, y1)
        draw_dotted_pdf(rx + 15, y1, RIGHT_X + dx1)

        x2, y2, dx2 = row_xy_pdf(2)
        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), x2, y2)
        draw_dotted_pdf(rx1 + 15, y2, 1525 + dx2)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545 + dx2, y2)
        draw_dotted_pdf(rx2 + 15, y2, RIGHT_X + dx2)

        x3, y3, dx3 = row_xy_pdf(3)
        rx = draw_txt_pdf(cert_info.get('line_inhabitant', 'an inhabitant of'), x3, y3)
        draw_dotted_pdf(rx + 15, y3, RIGHT_X + dx3)

        x4, y4, dx4 = row_xy_pdf(4)
        rx = draw_txt_pdf(cert_info.get('line_reading', 'is reading in class'), x4, y4)
        draw_dotted_pdf(rx + 15, y4, 1000 + dx4)
        rx2 = draw_txt_pdf(cert_info.get('line_stream', 'Stream'), 1020 + dx4, y4)
        draw_dotted_pdf(rx2 + 15, y4, 1500 + dx4)
        rx3 = draw_txt_pdf(cert_info.get('line_section', 'Section'), 1520 + dx4, y4)
        draw_dotted_pdf(rx3 + 15, y4, 1920 + dx4)
        rx4 = draw_txt_pdf(cert_info.get('line_roll', 'bearing class Roll No.'), 1940 + dx4, y4)
        draw_dotted_pdf(rx4 + 15, y4, RIGHT_X + dx4)

        x5, y5, dx5 = row_xy_pdf(5)
        rx = draw_txt_pdf(cert_info.get('line_session', 'of this School during the academic session 20'), x5, y5)
        draw_dotted_pdf(rx + 15, y5, 1800 + dx5)

        x6, y6, dx6 = row_xy_pdf(6)
        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/Her date of birth as recorded in the school registered is'), x6, y6)
        draw_dotted_pdf(rx + 15, y6, RIGHT_X + dx6)

        x7, y7, dx7 = row_xy_pdf(7)
        draw_txt_pdf(cert_info.get('line_character', 'He/She bears a good moral character.'), x7, y7)

    # 7. Footer (Common font, size & draggable positions in PDF)
    foot_fn = renderer_instance.get_reportlab_font(footer.get('footer_font', 'Times New Roman'), bold=False)
    foot_princ_fn = renderer_instance.get_reportlab_font(footer.get('footer_font', 'Times New Roman'), bold=True)
    foot_pt = float(footer.get('footer_size', 10.5))

    df_x, df_y = epos['tmpl_date_block']
    draw_txt_pdf(footer.get('date_prefix', 'Dated, Senapati'), df_x, df_y, font_name=foot_fn, font_pt=foot_pt)
    draw_txt_pdf(footer.get('date_label', 'The'), df_x, df_y + 84, font_name=foot_fn, font_pt=foot_pt)
    draw_dotted_pdf(df_x + 90, df_y + 84, df_x + 580)

    pr_x, pr_y = epos['tmpl_principal_block']
    px_r, _ = to_pdf_pt_func(pr_x, pr_y)
    pdf.saveState()
    pdf.setFont(foot_princ_fn, foot_pt + 1.0)
    pdf.setFillColor(col_navy)
    pdf.drawCentredString(px_r, to_pdf_pt_func(pr_x, pr_y)[1], footer.get('principal_title', 'Principal,'))
    pdf.setFont(foot_fn, foot_pt)
    pdf.drawCentredString(px_r, to_pdf_pt_func(pr_x, pr_y + 84)[1], footer.get('school_footer', 'Mount Everest Hr. Sec. School'))
    pdf.restoreState()
