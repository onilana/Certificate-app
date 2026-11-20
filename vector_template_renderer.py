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

def _draw_dotted_line_pil(draw, x1, y1, x2, y2, color=(160, 160, 160), dot_spacing=14, dot_size=3):
    """Draws a clean dotted baseline guide in PIL."""
    cur_x = x1
    while cur_x <= x2:
        draw.ellipse([cur_x, y1 - dot_size, cur_x + dot_size, y1], fill=color)
        cur_x += dot_spacing

def _draw_dotted_line_pdf(pdf, x1, y1, x2, y2, color_obj=None, dot_spacing=3.5, dot_size=0.8):
    """Draws a clean dotted baseline guide in ReportLab PDF."""
    pdf.saveState()
    if color_obj:
        pdf.setFillColor(color_obj)
    else:
        pdf.setFillColorRGB(0.65, 0.65, 0.65)
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

def render_vector_template_pil(cert_key: str, renderer_instance, custom_tmpl_cfg: dict = None) -> Image.Image:
    """Renders the complete editable certificate background as a PIL image (3000x2250)."""
    cfg = custom_tmpl_cfg or load_template_config()
    header = cfg.get('header', {})
    footer = cfg.get('footer', {})
    cert_info = cfg.get('certificates', {}).get(cert_key, {})

    img = Image.new('RGB', (int(IMG_W), int(IMG_H)), (255, 255, 255))
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

    def draw_centered(text, y, font, color=(11, 37, 69)):
        if not text: return
        bbox = draw.textbbox((0, 0), str(text), font=font)
        tw = bbox[2] - bbox[0]
        x = (IMG_W - tw) / 2
        draw.text((x, y), str(text), fill=color, font=font, anchor="la")

    # 3. School Header (Per-line customizable text, font family, and font size)
    off_font = header.get('office_font', 'Times New Roman')
    off_sz = int(round(float(header.get('office_size', 11)) * px_per_pt))
    f_off = get_font(size=off_sz, bold=True, italic=False, family=off_font)
    draw_centered(header.get('office_title', 'OFFICE OF THE PRINCIPAL'), 160, f_off, (11, 37, 69))

    sch_font = header.get('school_font', 'Times New Roman')
    sch_sz = int(round(float(header.get('school_size', 22)) * px_per_pt))
    f_school = get_font(size=sch_sz, bold=True, italic=False, family=sch_font)
    draw_centered(header.get('school_name', 'MOUNT EVEREST HIGHER SECONDARY SCHOOL'), 235, f_school, (11, 37, 69))

    sub_font = header.get('sub_font', 'Times New Roman')
    sub_sz = int(round(float(header.get('sub_size', 10)) * px_per_pt))
    f_addr = get_font(size=sub_sz, bold=False, italic=True, family=sub_font)
    draw_centered(header.get('sub_title', 'Taphou, Senapati - 795106, Manipur'), 355, f_addr, (51, 65, 85))

    aff_font = header.get('affiliation_font', 'CommercialScriptBT')
    aff_sz = int(round(float(header.get('affiliation_size', 16)) * px_per_pt))
    f_aff = get_font(size=aff_sz, bold=False, italic=True, family=aff_font)
    draw_centered(header.get('affiliation_line', 'Affiliated to Central Board of Secondary Education, New Delhi'), 425, f_aff, (0, 20, 120))

    aff_no_font = header.get('affiliation_no_font', 'Times New Roman')
    aff_no_sz = int(round(float(header.get('affiliation_no_size', 12)) * px_per_pt))
    f_aff_no = get_font(size=aff_no_sz, bold=True, italic=False, family=aff_no_font)
    draw_centered(header.get('affiliation_no', 'Affiliation No. 1230048'), 525, f_aff_no, (11, 37, 69))

    # 4. Certificate Title
    cert_title = cert_info.get('title', cert_key.capitalize() + ' Certificate')
    t_font = cert_info.get('title_font', 'Times New Roman')
    t_sz = int(round(float(cert_info.get('title_size', 18)) * px_per_pt))
    f_title = get_font(size=t_sz, bold=True, italic=False, family=t_font)
    draw_centered(cert_title, 660, f_title, (0, 30, 98))

    # 5. Sl. No. Label (on left margin)
    b_font = cfg.get('body_font', 'Times New Roman')
    b_sz = int(round(float(cfg.get('body_size', 11)) * px_per_pt))
    f_body = get_font(size=b_sz, bold=False, italic=False, family=b_font)
    f_sl = get_font(size=int(round((float(cfg.get('body_size', 11)) + 1.0) * px_per_pt)), bold=True, italic=True, family=b_font)
    draw.text((LEFT_X, 755), header.get('sl_label', 'Sl. No.'), fill=(11, 37, 69), font=f_sl, anchor="ls")
    sl_w = draw.textbbox((0, 0), header.get('sl_label', 'Sl. No.'), font=f_sl)[2]
    _draw_dotted_line_pil(draw, LEFT_X + sl_w + 15, 755, LEFT_X + 600, 755)

    # 6. Static Body Text & Dotted Lines per Certificate - Justified Layout
    def draw_txt(text, x, y, font=f_body, color=(15, 23, 42)):
        draw.text((x, y), text, fill=color, font=font, anchor="ls")
        bb = draw.textbbox((x, y), text, font=font, anchor="ls")
        return bb[2]  # right edge

    if cert_key == 'provisional':
        # Y=1068: This is to certify that Mr/Miss .......................
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 1068)
        _draw_dotted_line_pil(draw, rx + 15, 1068, RIGHT_X, 1068)

        # Y=1155: S/o, D/o Mr. ......... & Mrs. .........
        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1155)
        _draw_dotted_line_pil(draw, rx1 + 15, 1155, 1525, 1155)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545, 1155)
        _draw_dotted_line_pil(draw, rx2 + 15, 1155, RIGHT_X, 1155)

        # Y=1242: an inhabitant of .........
        rx = draw_txt(cert_info.get('line_inhabitant', 'an inhabitant of'), LEFT_X, 1242)
        _draw_dotted_line_pil(draw, rx + 15, 1242, RIGHT_X, 1242)

        # Y=1329: appeared the AISSE/AISSCE 20...... bearing Roll No. ...... of Central Board of
        rx = draw_txt(cert_info.get('line_exam', 'appeared the  AISSE/AISSCE  20'), LEFT_X, 1329)
        _draw_dotted_line_pil(draw, rx + 15, 1329, 1205, 1329)
        rx2 = draw_txt(cert_info.get('line_roll', 'bearing Roll No.'), 1225, 1329)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of'), RIGHT_X, 1329, font=f_body)
        _draw_dotted_line_pil(draw, rx2 + 15, 1329, board_lx - 15, 1329)

        # Y=1416: Secondary Education... (Justified across entire line)
        draw_justified_pil(draw, cert_info.get('line_decl', 'Secondary Education, New Delhi was declared to have qualified the said Examination and was placed in the'), LEFT_X, RIGHT_X, 1416, font=f_body)

        # Y=1503: grade ...... as per CBSE result uploaded by NIC, New Delhi.
        rx = draw_txt(cert_info.get('line_grade', 'grade'), LEFT_X, 1503)
        nic_lx = draw_right_aligned_pil(draw, cert_info.get('line_nic', 'as per CBSE result uploaded by National Informatics Centre (NIC), New Delhi.'), RIGHT_X, 1503, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, 1503, nic_lx - 20, 1503)

        # Y=1590: His/her date of birth according to the school admission record is ......
        rx = draw_txt(cert_info.get('line_dob', 'His/her date of birth according to the school admission record is'), LEFT_X, 1590)
        _draw_dotted_line_pil(draw, rx + 15, 1590, RIGHT_X, 1590)

        # Y=1677: His/Her Registration Number with the CBSE is ......
        rx = draw_txt(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), LEFT_X, 1677)
        _draw_dotted_line_pil(draw, rx + 15, 1677, RIGHT_X, 1677)

        # Y=1764: The result of the said Examination was announced on ......
        rx = draw_txt(cert_info.get('line_result', 'The result of the said Examination was announced on'), LEFT_X, 1764)
        _draw_dotted_line_pil(draw, rx + 15, 1764, RIGHT_X, 1764)

    elif cert_key == 'character':
        draw_txt(cert_info.get('line_conduct', 'This is to certify that the conduct and character of'), LEFT_X, 1205)

        rx = draw_txt(cert_info.get('line_student_prefix', 'Mr./Miss'), LEFT_X, 1310)
        qual_lx = draw_right_aligned_pil(draw, 'qualified/', RIGHT_X, 1310, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, 1310, qual_lx - 15, 1310)

        rx = draw_txt(cert_info.get('line_status', 'disqualified the AISSE/AISSCE, 20'), LEFT_X, 1415)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of Secondary Education, New Delhi'), RIGHT_X, 1415, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, 1415, board_lx - 15, 1415)

        rx = draw_txt('bearing Roll No.', LEFT_X, 1519)
        placed_lx = draw_right_aligned_pil(draw, cert_info.get('line_placed', 'was placed in the grade'), RIGHT_X, 1519, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, 1519, placed_lx - 15, 1519)

        _draw_dotted_line_pil(draw, LEFT_X, 1623, 480, 1623)
        draw_right_aligned_pil(draw, cert_info.get('line_nic', 'As per CBSE result uploaded by National Informatics Centre (NIC), New Delhi is found'), RIGHT_X, 1623, font=f_body)

        rx = draw_txt(cert_info.get('line_satisfactory', 'satisfactory during the academic session 20'), LEFT_X, 1728)
        _draw_dotted_line_pil(draw, rx + 15, 1728, 1800, 1728)

    elif cert_key == 'transfer':
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 969)
        _draw_dotted_line_pil(draw, rx + 15, 969, RIGHT_X, 969)

        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1051)
        _draw_dotted_line_pil(draw, rx1 + 15, 1051, 1525, 1051)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545, 1051)
        _draw_dotted_line_pil(draw, rx2 + 15, 1051, RIGHT_X, 1051)

        rx = draw_txt(cert_info.get('line_status', 'was declared to have qualified/disqualified the AISSE/AISSCE, 20'), LEFT_X, 1133)
        board_lx = draw_right_aligned_pil(draw, cert_info.get('line_board', 'of Central Board of Secondary'), RIGHT_X, 1133, font=f_body)
        _draw_dotted_line_pil(draw, rx + 15, 1133, board_lx - 15, 1133)

        rx = draw_txt(cert_info.get('line_roll', 'Education, New Delhi, bearing Roll No.'), LEFT_X, 1214)
        _draw_dotted_line_pil(draw, rx + 15, 1214, 1605, 1214)
        rx2 = draw_txt(cert_info.get('line_placed', 'was placed in the grade'), 1625, 1214)
        _draw_dotted_line_pil(draw, rx2 + 15, 1214, RIGHT_X, 1214)

        # Justified across entire width
        draw_justified_pil(draw, cert_info.get('line_nic', 'as per CBSE result list uploaded by National Informatics Centre (NIC), New Delhi. He/She has cleared'), LEFT_X, RIGHT_X, 1295, font=f_body)

        rx = draw_txt(cert_info.get('line_dues', 'fees/dues payable to this institute during the academic session'), LEFT_X, 1377)
        _draw_dotted_line_pil(draw, rx + 15, 1377, RIGHT_X, 1377)

        rx = draw_txt(cert_info.get('line_dob', 'His/Her date of birth according to the school admission record is'), LEFT_X, 1459)
        _draw_dotted_line_pil(draw, rx + 15, 1459, RIGHT_X, 1459)

        rx = draw_txt(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), LEFT_X, 1540)
        _draw_dotted_line_pil(draw, rx + 15, 1540, RIGHT_X, 1540)

        rx = draw_txt(cert_info.get('line_left', 'He/She left this school on'), LEFT_X, 1622)
        _draw_dotted_line_pil(draw, rx + 15, 1622, RIGHT_X, 1622)

        rx = draw_txt(cert_info.get('line_pen', 'His/Her PEN No.'), LEFT_X, 1703)
        _draw_dotted_line_pil(draw, rx + 15, 1703, 1850, 1703)

        # Wish text centered between PEN No and Reasons
        draw_centered(cert_info.get('wish_text', 'We wish him/her a bright future.'), 1775, get_font(size=38, italic=True), (11, 37, 69))

        # Reasons list in Left Column
        draw_txt(cert_info.get('reasons_title', 'REASONS OF LEAVING:'), LEFT_X, 1835, font=get_font(size=32, bold=True))
        f_reasons = get_font(size=28, bold=False)
        draw_txt("i)   Completion of Course.", LEFT_X, 1875, font=f_reasons)
        draw_txt("ii)  Ill Health", LEFT_X, 1913, font=f_reasons)
        draw_txt("iii) Change of Residence", LEFT_X, 1951, font=f_reasons)
        draw_txt("iv)  Student’s Choice/Parent’s Choice", LEFT_X, 1989, font=f_reasons)
        draw_txt("v)   Other Reasons", LEFT_X, 2027, font=f_reasons)

    elif cert_key == 'reading':
        rx = draw_txt(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 1081)
        _draw_dotted_line_pil(draw, rx + 15, 1081, RIGHT_X, 1081)

        rx1 = draw_txt(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1202)
        _draw_dotted_line_pil(draw, rx1 + 15, 1202, 1525, 1202)
        rx2 = draw_txt(cert_info.get('line_mother', '& Mrs.'), 1545, 1202)
        _draw_dotted_line_pil(draw, rx2 + 15, 1202, RIGHT_X, 1202)

        rx = draw_txt(cert_info.get('line_inhabitant', 'an inhabitant of'), LEFT_X, 1323)
        _draw_dotted_line_pil(draw, rx + 15, 1323, RIGHT_X, 1323)

        rx = draw_txt(cert_info.get('line_reading', 'is reading in class'), LEFT_X, 1444)
        _draw_dotted_line_pil(draw, rx + 15, 1444, 1000, 1444)
        rx2 = draw_txt(cert_info.get('line_stream', 'Stream'), 1020, 1444)
        _draw_dotted_line_pil(draw, rx2 + 15, 1444, 1500, 1444)
        rx3 = draw_txt(cert_info.get('line_section', 'Section'), 1520, 1444)
        _draw_dotted_line_pil(draw, rx3 + 15, 1444, 1920, 1444)
        rx4 = draw_txt(cert_info.get('line_roll', 'bearing class Roll No.'), 1940, 1444)
        _draw_dotted_line_pil(draw, rx4 + 15, 1444, RIGHT_X, 1444)

        rx = draw_txt(cert_info.get('line_session', 'of this School during the academic session 20'), LEFT_X, 1565)
        _draw_dotted_line_pil(draw, rx + 15, 1565, 1800, 1565)

        rx = draw_txt(cert_info.get('line_dob', 'His/Her date of birth as recorded in the school registered is'), LEFT_X, 1686)
        _draw_dotted_line_pil(draw, rx + 15, 1686, RIGHT_X, 1686)

        draw_txt(cert_info.get('line_character', 'He/She bears a good moral character.'), LEFT_X, 1807)

    # 7. Common Footer (Common font & size for footer)
    foot_font = footer.get('footer_font', 'Times New Roman')
    foot_sz = int(round(float(footer.get('footer_size', 11)) * px_per_pt))
    f_foot = get_font(size=foot_sz, bold=False, italic=False, family=foot_font)
    f_princ = get_font(size=int(round((float(footer.get('footer_size', 11)) + 1.0) * px_per_pt)), bold=True, family=foot_font)
    f_sch_f = get_font(size=foot_sz, bold=False, family=foot_font)

    if cert_key == 'transfer':
        # Center Date Column for Transfer Certificate (calibrated to issue_date X=1363, Y=1985)
        draw.text((1246, 1940), footer.get('date_prefix', 'Dated, Senapati'), fill=(15, 23, 42), font=f_foot, anchor="ls")
        draw.text((1246, 2024), footer.get('date_label', 'The'), fill=(15, 23, 42), font=f_foot, anchor="ls")
        _draw_dotted_line_pil(draw, 1340, 2024, 1820, 2024)
    else:
        # Date on Left Margin for Provisional, Character, Reading
        draw.text((LEFT_X, 1940), footer.get('date_prefix', 'Dated, Senapati'), fill=(15, 23, 42), font=f_foot, anchor="ls")
        draw.text((LEFT_X, 2024), footer.get('date_label', 'The'), fill=(15, 23, 42), font=f_foot, anchor="ls")
        _draw_dotted_line_pil(draw, LEFT_X + 90, 2024, LEFT_X + 600, 2024)

    # Principal on Right
    draw.text((2460, 1940), footer.get('principal_title', 'Principal,'), fill=(11, 37, 69), font=f_princ, anchor="ms")
    draw.text((2460, 2024), footer.get('school_footer', 'Mount Everest Hr. Sec. School'), fill=(11, 37, 69), font=f_sch_f, anchor="ms")

    return img


def draw_vector_template_pdf(pdf, cert_key: str, renderer_instance, w: float, h: float, to_pdf_pt_func, custom_tmpl_cfg: dict = None):
    """Draws the complete editable certificate background vectorially in ReportLab PDF."""
    from reportlab.lib.colors import HexColor

    cfg = custom_tmpl_cfg or load_template_config()
    header = cfg.get('header', {})
    footer = cfg.get('footer', {})
    cert_info = cfg.get('certificates', {}).get(cert_key, {})

    col_border = HexColor('#0F1E3C')
    col_navy = HexColor('#0B2545')
    col_dark = HexColor('#0F172A')
    col_title = HexColor('#001E62')
    col_blue = HexColor('#001478')

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
    def draw_center_pdf(text, img_y, font_name, font_pt, color_obj):
        if not text: return
        _, py = to_pdf_pt_func(1500, img_y)
        pdf.saveState()
        pdf.setFont(font_name, font_pt)
        pdf.setFillColor(color_obj)
        pdf.drawCentredString(w / 2.0, py, str(text))
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

    # 3. Headers (Per-line customizable font and size in PDF)
    off_fn = renderer_instance.get_reportlab_font(header.get('office_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('office_title', 'OFFICE OF THE PRINCIPAL'), 190, off_fn, float(header.get('office_size', 10.5)), col_navy)

    sch_fn = renderer_instance.get_reportlab_font(header.get('school_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('school_name', 'MOUNT EVEREST HIGHER SECONDARY SCHOOL'), 295, sch_fn, float(header.get('school_size', 21.0)), col_navy)

    sub_fn = renderer_instance.get_reportlab_font(header.get('sub_font', 'Times New Roman'), italic=True)
    draw_center_pdf(header.get('sub_title', 'Taphou, Senapati - 795106, Manipur'), 380, sub_fn, float(header.get('sub_size', 9.5)), HexColor('#334155'))

    aff_fn = renderer_instance.get_reportlab_font(header.get('affiliation_font', 'CommercialScriptBT'), italic=True)
    draw_center_pdf(header.get('affiliation_line', 'Affiliated to Central Board of Secondary Education, New Delhi'), 465, aff_fn, float(header.get('affiliation_size', 16.0)), col_blue)

    aff_no_fn = renderer_instance.get_reportlab_font(header.get('affiliation_no_font', 'Times New Roman'), bold=True)
    draw_center_pdf(header.get('affiliation_no', 'Affiliation No. 1230048'), 550, aff_no_fn, float(header.get('affiliation_no_size', 11.5)), col_navy)

    # 4. Title
    cert_title = cert_info.get('title', cert_key.capitalize() + ' Certificate')
    t_fn = renderer_instance.get_reportlab_font(cert_info.get('title_font', 'Times New Roman'), bold=True)
    draw_center_pdf(cert_title, 715, t_fn, float(cert_info.get('title_size', 18.0)), col_title)

    # 5. Sl. No. Label (on left margin)
    sl_fn = renderer_instance.get_reportlab_font(cfg.get('body_font', 'Times New Roman'), bold=True, italic=True)
    sl_rx = draw_txt_pdf(header.get('sl_label', 'Sl. No.'), LEFT_X, 755, sl_fn, float(cfg.get('body_size', 11.5)) + 1, col_navy)
    draw_dotted_pdf(sl_rx + 15, 755, LEFT_X + 600)

    # 6. Body Text per certificate - Justified Layout
    if cert_key == 'provisional':
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 1068)
        draw_dotted_pdf(rx + 15, 1068, RIGHT_X)

        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1155)
        draw_dotted_pdf(rx1 + 15, 1155, 1525)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545, 1155)
        draw_dotted_pdf(rx2 + 15, 1155, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_inhabitant', 'an inhabitant of'), LEFT_X, 1242)
        draw_dotted_pdf(rx + 15, 1242, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_exam', 'appeared the  AISSE/AISSCE  20'), LEFT_X, 1329)
        draw_dotted_pdf(rx + 15, 1329, 1205)
        rx2 = draw_txt_pdf(cert_info.get('line_roll', 'bearing Roll No.'), 1225, 1329)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of'), RIGHT_X, 1329)
        draw_dotted_pdf(rx2 + 15, 1329, board_lx - 15)

        # Full line justified
        draw_justified_pdf(cert_info.get('line_decl', 'Secondary Education, New Delhi was declared to have qualified the said Examination and was placed in the'), LEFT_X, RIGHT_X, 1416)

        rx = draw_txt_pdf(cert_info.get('line_grade', 'grade'), LEFT_X, 1503)
        nic_lx = draw_right_pdf(cert_info.get('line_nic', 'as per CBSE result uploaded by National Informatics Centre (NIC), New Delhi.'), RIGHT_X, 1503)
        draw_dotted_pdf(rx + 15, 1503, nic_lx - 20)

        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/her date of birth according to the school admission record is'), LEFT_X, 1590)
        draw_dotted_pdf(rx + 15, 1590, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), LEFT_X, 1677)
        draw_dotted_pdf(rx + 15, 1677, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_result', 'The result of the said Examination was announced on'), LEFT_X, 1764)
        draw_dotted_pdf(rx + 15, 1764, RIGHT_X)

    elif cert_key == 'character':
        draw_txt_pdf(cert_info.get('line_conduct', 'This is to certify that the conduct and character of'), LEFT_X, 1205)

        rx = draw_txt_pdf(cert_info.get('line_student_prefix', 'Mr./Miss'), LEFT_X, 1310)
        qual_lx = draw_right_pdf('qualified/', RIGHT_X, 1310)
        draw_dotted_pdf(rx + 15, 1310, qual_lx - 15)

        rx = draw_txt_pdf(cert_info.get('line_status', 'disqualified the AISSE/AISSCE, 20'), LEFT_X, 1415)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of Secondary Education, New Delhi'), RIGHT_X, 1415)
        draw_dotted_pdf(rx + 15, 1415, board_lx - 15)

        rx = draw_txt_pdf('bearing Roll No.', LEFT_X, 1519)
        placed_lx = draw_right_pdf(cert_info.get('line_placed', 'was placed in the grade'), RIGHT_X, 1519)
        draw_dotted_pdf(rx + 15, 1519, placed_lx - 15)

        draw_dotted_pdf(LEFT_X, 1623, 480)
        draw_right_pdf(cert_info.get('line_nic', 'As per CBSE result uploaded by National Informatics Centre (NIC), New Delhi is found'), RIGHT_X, 1623)

        rx = draw_txt_pdf(cert_info.get('line_satisfactory', 'satisfactory during the academic session 20'), LEFT_X, 1728)
        draw_dotted_pdf(rx + 15, 1728, 1800)

    elif cert_key == 'transfer':
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 969)
        draw_dotted_pdf(rx + 15, 969, RIGHT_X)

        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1051)
        draw_dotted_pdf(rx1 + 15, 1051, 1525)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545, 1051)
        draw_dotted_pdf(rx2 + 15, 1051, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_status', 'was declared to have qualified/disqualified the AISSE/AISSCE, 20'), LEFT_X, 1133)
        board_lx = draw_right_pdf(cert_info.get('line_board', 'of Central Board of Secondary'), RIGHT_X, 1133)
        draw_dotted_pdf(rx + 15, 1133, board_lx - 15)

        rx = draw_txt_pdf(cert_info.get('line_roll', 'Education, New Delhi, bearing Roll No.'), LEFT_X, 1214)
        draw_dotted_pdf(rx + 15, 1214, 1605)
        rx2 = draw_txt_pdf(cert_info.get('line_placed', 'was placed in the grade'), 1625, 1214)
        draw_dotted_pdf(rx2 + 15, 1214, RIGHT_X)

        # Full line justified
        draw_justified_pdf(cert_info.get('line_nic', 'as per CBSE result list uploaded by National Informatics Centre (NIC), New Delhi. He/She has cleared'), LEFT_X, RIGHT_X, 1295)

        rx = draw_txt_pdf(cert_info.get('line_dues', 'fees/dues payable to this institute during the academic session'), LEFT_X, 1377)
        draw_dotted_pdf(rx + 15, 1377, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/Her date of birth according to the school admission record is'), LEFT_X, 1459)
        draw_dotted_pdf(rx + 15, 1459, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_reg', 'His/Her Registration Number with the CBSE is'), LEFT_X, 1540)
        draw_dotted_pdf(rx + 15, 1540, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_left', 'He/She left this school on'), LEFT_X, 1622)
        draw_dotted_pdf(rx + 15, 1622, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_pen', 'His/Her PEN No.'), LEFT_X, 1703)
        draw_dotted_pdf(rx + 15, 1703, 1850)

        # Wish text centered
        draw_center_pdf(cert_info.get('wish_text', 'We wish him/her a bright future.'), 1775, "Times-Italic", 9.5, col_navy)

        # Reasons list on Left Column
        draw_txt_pdf(cert_info.get('reasons_title', 'REASONS OF LEAVING:'), LEFT_X, 1835, "Times-Bold", 8.5)
        draw_txt_pdf("i)   Completion of Course.", LEFT_X, 1875, "Times-Roman", 7.5)
        draw_txt_pdf("ii)  Ill Health", LEFT_X, 1913, "Times-Roman", 7.5)
        draw_txt_pdf("iii) Change of Residence", LEFT_X, 1951, "Times-Roman", 7.5)
        draw_txt_pdf("iv)  Student’s Choice/Parent’s Choice", LEFT_X, 1989, "Times-Roman", 7.5)
        draw_txt_pdf("v)   Other Reasons", LEFT_X, 2027, "Times-Roman", 7.5)

    elif cert_key == 'reading':
        rx = draw_txt_pdf(cert_info.get('line_certify', 'This is to certify that Mr/Miss'), LEFT_X, 1081)
        draw_dotted_pdf(rx + 15, 1081, RIGHT_X)

        rx1 = draw_txt_pdf(cert_info.get('line_parents', 'S/o, D/o Mr.'), LEFT_X, 1202)
        draw_dotted_pdf(rx1 + 15, 1202, 1525)
        rx2 = draw_txt_pdf(cert_info.get('line_mother', '& Mrs.'), 1545, 1202)
        draw_dotted_pdf(rx2 + 15, 1202, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_inhabitant', 'an inhabitant of'), LEFT_X, 1323)
        draw_dotted_pdf(rx + 15, 1323, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_reading', 'is reading in class'), LEFT_X, 1444)
        draw_dotted_pdf(rx + 15, 1444, 1000)
        rx2 = draw_txt_pdf(cert_info.get('line_stream', 'Stream'), 1020, 1444)
        draw_dotted_pdf(rx2 + 15, 1444, 1500)
        rx3 = draw_txt_pdf(cert_info.get('line_section', 'Section'), 1520, 1444)
        draw_dotted_pdf(rx3 + 15, 1444, 1920)
        rx4 = draw_txt_pdf(cert_info.get('line_roll', 'bearing class Roll No.'), 1940, 1444)
        draw_dotted_pdf(rx4 + 15, 1444, RIGHT_X)

        rx = draw_txt_pdf(cert_info.get('line_session', 'of this School during the academic session 20'), LEFT_X, 1565)
        draw_dotted_pdf(rx + 15, 1565, 1800)

        rx = draw_txt_pdf(cert_info.get('line_dob', 'His/Her date of birth as recorded in the school registered is'), LEFT_X, 1686)
        draw_dotted_pdf(rx + 15, 1686, RIGHT_X)

        draw_txt_pdf(cert_info.get('line_character', 'He/She bears a good moral character.'), LEFT_X, 1807)

    # 7. Footer (Common font and size for footer in PDF)
    foot_fn = renderer_instance.get_reportlab_font(footer.get('footer_font', 'Times New Roman'), bold=False)
    foot_princ_fn = renderer_instance.get_reportlab_font(footer.get('footer_font', 'Times New Roman'), bold=True)
    foot_pt = float(footer.get('footer_size', 10.5))

    if cert_key == 'transfer':
        # Center Date Column for Transfer Certificate
        draw_txt_pdf(footer.get('date_prefix', 'Dated, Senapati'), 1246, 1940, font_name=foot_fn, font_pt=foot_pt)
        draw_txt_pdf(footer.get('date_label', 'The'), 1246, 2024, font_name=foot_fn, font_pt=foot_pt)
        draw_dotted_pdf(1340, 2024, 1820)
    else:
        # Date on Left Margin for Provisional, Character, Reading
        draw_txt_pdf(footer.get('date_prefix', 'Dated, Senapati'), LEFT_X, 1940, font_name=foot_fn, font_pt=foot_pt)
        draw_txt_pdf(footer.get('date_label', 'The'), LEFT_X, 2024, font_name=foot_fn, font_pt=foot_pt)
        draw_dotted_pdf(LEFT_X + 90, 2024, LEFT_X + 600)

    px_r, _ = to_pdf_pt_func(2460, 1940)
    pdf.saveState()
    pdf.setFont(foot_princ_fn, foot_pt + 1.0)
    pdf.setFillColor(col_navy)
    pdf.drawCentredString(px_r, to_pdf_pt_func(2460, 1940)[1], footer.get('principal_title', 'Principal,'))
    pdf.setFont(foot_fn, foot_pt)
    pdf.drawCentredString(px_r, to_pdf_pt_func(2460, 2024)[1], footer.get('school_footer', 'Mount Everest Hr. Sec. School'))
    pdf.restoreState()
