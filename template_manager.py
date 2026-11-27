# -*- coding: utf-8 -*-
"""
Certificate Template Manager
Stores, loads, and manages fully editable certificate wording, headers, and layouts.
Allows administrators to customize school information, certificate titles, body sentences,
and footer signatures without needing static PNG background images.
"""

import os
import json
import copy
from path_utils import get_base_dir

TEMPLATE_CONFIG_FILE = os.path.join(get_base_dir(), 'templates_config.json')

DEFAULT_TEMPLATE_CONFIG = {
    "use_editable_template": True,
    "header": {
        "office_title": "OFFICE OF THE PRINCIPAL",
        "office_font": "Times New Roman",
        "office_size": 11,
        "school_name": "MOUNT EVEREST HIGHER SECONDARY SCHOOL",
        "school_font": "Times New Roman",
        "school_size": 22,
        "sub_title": "Taphou, Senapati - 795106, Manipur",
        "sub_font": "Times New Roman",
        "sub_size": 10,
        "affiliation_line": "Affiliated to Central Board of Secondary Education, New Delhi",
        "affiliation_font": "CommercialScriptBT",
        "affiliation_size": 16,
        "affiliation_no": "Affiliation No. 1230048",
        "affiliation_no_font": "Times New Roman",
        "affiliation_no_size": 12,
        "sl_label": "Sl. No."
    },
    "body_font": "Times New Roman",
    "body_size": 11,
    "footer": {
        "footer_font": "Times New Roman",
        "footer_size": 11,
        "date_prefix": "Dated, Senapati",
        "date_label": "The",
        "principal_title": "Principal,",
        "school_footer": "Mount Everest Hr. Sec. School"
    },
    "certificates": {
        "provisional": {
            "title": "Provisional Certificate",
            "title_font": "Times New Roman",
            "title_size": 18,
            "line_certify": "This is to certify that Mr/Miss",
            "line_parents": "S/o, D/o Mr.",
            "line_mother": "& Mrs.",
            "line_inhabitant": "an inhabitant of",
            "line_exam": "appeared the  AISSE/AISSCE  20",
            "line_roll": "bearing Roll No.",
            "line_board": "of Central Board of",
            "line_decl": "Secondary Education, New Delhi was declared to have qualified the said Examination and was placed in the",
            "line_grade": "grade",
            "line_nic": "as per CBSE result uploaded by National Informatics Centre (NIC), New Delhi.",
            "line_dob": "His/her date of birth according to the school admission record is",
            "line_reg": "His/Her Registration Number with the CBSE is",
            "line_result": "The result of the said Examination was announced on"
        },
        "character": {
            "title": "Character Certificate",
            "title_font": "Times New Roman",
            "title_size": 18,
            "line_conduct": "This is to certify that the conduct and character of",
            "line_student_prefix": "Mr./Miss",
            "line_status": "qualified/disqualified the AISSE/AISSCE, 20",
            "line_board": "of Central Board of Secondary Education, New Delhi bearing Roll No.",
            "line_placed": "was placed in the grade ............................As per CBSE result uploaded",
            "line_nic": "by National Informatics Centre (NIC), New Delhi is found satisfactory during the",
            "line_satisfactory": "academic session 20"
        },
        "transfer": {
            "title": "Transfer Certificate",
            "title_font": "Times New Roman",
            "title_size": 18,
            "line_certify": "This is to certify that Mr/Miss",
            "line_parents": "S/o, D/o Mr.",
            "line_mother": "& Mrs.",
            "line_status": "was declared to have qualified/disqualified the AISSE/AISSCE, 20",
            "line_board": "of Central Board of Secondary",
            "line_roll": "Education, New Delhi, bearing Roll No.",
            "line_placed": "was placed in the grade",
            "line_nic": "as per CBSE result list uploaded by National Informatics Centre (NIC), New Delhi. He/She has cleared",
            "line_dues": "fees/dues payable to this institute during the academic session",
            "line_dob": "His/Her date of birth according to the school admission record is",
            "line_reg": "His/Her Registration Number with the CBSE is",
            "line_left": "He/She left this school on",
            "line_pen": "His/Her PEN No.",
            "reasons_title": "REASONS OF LEAVING:",
            "reasons_list": [
                "i)   Completion of Course.",
                "ii)  Ill Health",
                "iii) Change of Residence",
                "iv)  Student’s Choice/Parent’s Choice",
                "v)   Other Reasons"
            ],
            "wish_text": "We wish him/her a bright future."
        },
        "reading": {
            "title": "Reading Certificate",
            "title_font": "Times New Roman",
            "title_size": 18,
            "line_certify": "This is to certify that Mr/Miss",
            "line_parents": "S/o, D/o Mr.",
            "line_mother": "& Mrs.",
            "line_inhabitant": "an inhabitant of",
            "line_reading": "is reading in class",
            "line_stream": "Stream",
            "line_section": "Section",
            "line_roll": "bearing class Roll No.",
            "line_session": "of this School during the academic session 20",
            "line_dob": "His/Her date of birth as recorded in the school registered is",
            "line_character": "He/She bears a good moral character."
        }
    }
}

def load_template_config() -> dict:
    """Loads custom template wording configuration, falling back to defaults."""
    cfg = copy.deepcopy(DEFAULT_TEMPLATE_CONFIG)
    if os.path.exists(TEMPLATE_CONFIG_FILE):
        try:
            with open(TEMPLATE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    # Deep update for nested sections
                    if 'header' in saved and isinstance(saved['header'], dict):
                        cfg['header'].update(saved['header'])
                    if 'footer' in saved and isinstance(saved['footer'], dict):
                        cfg['footer'].update(saved['footer'])
                    if 'certificates' in saved and isinstance(saved['certificates'], dict):
                        for c_k, c_v in saved['certificates'].items():
                            if c_k in cfg['certificates'] and isinstance(c_v, dict):
                                cfg['certificates'][c_k].update(c_v)
                            else:
                                cfg['certificates'][c_k] = c_v
                    if 'body_font' in saved:
                        cfg['body_font'] = str(saved['body_font'])
                    if 'body_size' in saved:
                        try: cfg['body_size'] = float(saved['body_size'])
                        except Exception: pass
                    if 'use_editable_template' in saved:
                        cfg['use_editable_template'] = bool(saved['use_editable_template'])
                    if 'header_positions' in saved and isinstance(saved['header_positions'], dict):
                        cfg['header_positions'] = saved['header_positions']
                    if 'footer_positions' in saved and isinstance(saved['footer_positions'], dict):
                        cfg['footer_positions'] = saved['footer_positions']
        except Exception as e:
            print(f"Error loading template config: {e}")
    else:
        # Save default configuration for user inspection/editing
        save_template_config(cfg)
    return cfg

def save_template_config(cfg: dict) -> bool:
    """Saves custom template wording configuration."""
    try:
        with open(TEMPLATE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving template config: {e}")
        return False

def reset_template_config() -> dict:
    """Resets template configuration back to factory default."""
    cfg = copy.deepcopy(DEFAULT_TEMPLATE_CONFIG)
    save_template_config(cfg)
    return cfg
