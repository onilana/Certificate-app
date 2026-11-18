import json
import os
from path_utils import get_base_dir

CONFIG_FILE = os.path.join(get_base_dir(), 'config.json')
DEFAULT_OUTPUT_DIR = os.path.join(get_base_dir(), 'Output_Certificates')

DEFAULT_CONFIG = {
    "printer_name": "",
    "paper_size": "10.5x7.5",     # "10.5x7.5", "10.0x7.5", "Auto (Printer Setup)", "A4", etc.
    "custom_width_in": 10.5,
    "custom_height_in": 7.5,
    "custom_width_pt": None,
    "custom_height_pt": None,
    "print_mode": "full",         # "full" or "overlay"
    "print_color_mode": "Color",  # "Color" or "Grayscale"
    "offset_x_mm": 0.0,
    "offset_y_mm": 0.0,
    "font_size": 18,
    "font_color": "#001478",       # Deep Navy Blue
    "sl_no_color": "#b40000",      # Crimson Red
    "font_family": "CommercialScriptBT",
    "is_bold": True,
    "is_italic": True,
    "strike_unused": False,
    "auto_increment_sl": False,
    "auto_date_today": True,
    "last_sl_number": 1,
    "theme": "light",
    "output_dir": DEFAULT_OUTPUT_DIR,
    "admin_password": "1234"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                return config
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
