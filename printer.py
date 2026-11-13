import os
import sys
import subprocess
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'Output_Certificates')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR

def open_output_folder():
    out_dir = get_output_dir()
    if os.path.exists(out_dir):
        os.startfile(out_dir)
        return True
    return False

def get_printers():
    """Returns list of installed Windows printers."""
    printers = []
    try:
        import win32print
        raw_list = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        for p in raw_list:
            printers.append(p[2])
    except Exception as e:
        print(f"Error enumerating printers: {e}")
    return printers

def get_default_printer():
    """Returns default Windows printer name or empty string."""
    try:
        import win32print
        return win32print.GetDefaultPrinter()
    except Exception:
        return ""

def get_printer_paper_sizes(printer_name=None):
    """
    Queries the printer driver (DC_PAPERNAMES & DC_PAPERSIZE)
    to return all paper sizes defined on that printer with dimensions.
    """
    target = printer_name or get_default_printer()
    if not target:
        return []
    try:
        import win32print
        names = win32print.DeviceCapabilities(target, "", 16) # DC_PAPERNAMES
        sizes = win32print.DeviceCapabilities(target, "", 3)  # DC_PAPERSIZE (tenths of mm)
        
        result = []
        for n, sz in zip(names, sizes):
            # Convert tenths of mm to points (1 pt = 25.4 / 72 mm)
            w_pt = (sz["x"] / 10.0 / 25.4) * 72.0
            h_pt = (sz["y"] / 10.0 / 25.4) * 72.0
            # Normalize landscape
            l_w = max(w_pt, h_pt)
            l_h = min(w_pt, h_pt)
            result.append({
                "name": str(n).strip(),
                "width_pt": l_w,
                "height_pt": l_h,
                "width_in": l_w / 72.0,
                "height_in": l_h / 72.0
            })
        return result
    except Exception as e:
        print(f"Error reading paper sizes from {target}: {e}")
        return []

def get_active_printer_paper_size(printer_name=None):
    """
    Returns the currently active paper size and dimensions from the printer's setup.
    """
    target = printer_name or get_default_printer()
    if not target:
        return None
    try:
        import win32print
        h = win32print.OpenPrinter(target)
        info = win32print.GetPrinter(h, 2)
        devmode = info.get("pDevMode")
        active_id = devmode.PaperSize if devmode else None
        
        names = win32print.DeviceCapabilities(target, "", 16)
        ids = win32print.DeviceCapabilities(target, "", 2)
        sizes = win32print.DeviceCapabilities(target, "", 3)
        win32print.ClosePrinter(h)

        if active_id and ids:
            for n, pid, sz in zip(names, ids, sizes):
                if pid == active_id:
                    w_pt = (sz["x"] / 10.0 / 25.4) * 72.0
                    h_pt = (sz["y"] / 10.0 / 25.4) * 72.0
                    return {
                        "name": str(n).strip(),
                        "width_pt": max(w_pt, h_pt),
                        "height_pt": min(w_pt, h_pt),
                        "width_in": max(w_pt, h_pt) / 72.0,
                        "height_in": min(w_pt, h_pt) / 72.0
                    }
    except Exception as e:
        print(f"Error fetching active paper: {e}")
    return None

def open_pdf(pdf_path):
    """Opens the PDF in default Windows PDF viewer."""
    if os.path.exists(pdf_path):
        os.startfile(pdf_path)
        return True
    return False

def open_printer_preferences(printer_name=None):
    """
    Opens the native Windows / Epson printer preferences window
    where user can configure custom paper size (10.5 x 7.5 in), paper tray, and quality.
    """
    target = printer_name or get_default_printer()
    if not target:
        return False
    try:
        cmd = f'rundll32.exe printui.dll,PrintUIEntry /e /n "{target}"'
        subprocess.Popen(cmd, shell=True)
        return True
    except Exception as e:
        print(f"Failed to open printer preferences: {e}")
        return False

def print_direct(images, printer_name=None, color_mode="Color", show_properties_dialog=False, hwnd=0):
    """
    Directly prints one or more high-resolution PIL certificate images to the Windows printer DC.
    - NEVER opens an external PDF reader.
    - Explicitly sets Color or Grayscale in DEVMODE.
    - Sets landscape orientation.
    - If show_properties_dialog=True, opens the native Windows / Epson printer properties dialog (DocumentProperties).
    """
    target = printer_name or get_default_printer()
    if not target:
        raise ValueError("No printer selected or found. Please connect and select a printer.")

    import win32gui
    import win32ui
    import win32print
    import win32con
    from PIL import ImageWin

    hPrinter = win32print.OpenPrinter(target)
    try:
        info = win32print.GetPrinter(hPrinter, 2)
        devmode = info.get('pDevMode')
        if devmode:
            devmode.Orientation = win32con.DMORIENT_LANDSCAPE
            if str(color_mode).lower() in ('gray', 'grayscale', 'mono', 'black & white'):
                devmode.Color = win32con.DMCOLOR_MONOCHROME
            else:
                devmode.Color = win32con.DMCOLOR_COLOR
            devmode.Fields |= (win32con.DM_ORIENTATION | win32con.DM_COLOR)

        if show_properties_dialog:
            res = win32print.DocumentProperties(
                int(hwnd) if hwnd else 0,
                hPrinter,
                target,
                devmode,
                devmode,
                win32con.DM_IN_PROMPT | win32con.DM_OUT_BUFFER | win32con.DM_IN_BUFFER
            )
            # res == 1 (IDOK), 2 (IDCANCEL)
            if res != 1:
                return False  # User clicked cancel in printer properties dialog

        hdc_raw = win32gui.CreateDC("WINSPOOL", target, devmode)
        dc = win32ui.CreateDCFromHandle(hdc_raw)

        # High quality photo halftone stretching
        try:
            import ctypes
            ctypes.windll.gdi32.SetStretchBltMode(hdc_raw, win32con.HALFTONE)
            ctypes.windll.gdi32.SetBrushOrgEx(hdc_raw, 0, 0, None)
        except Exception as e:
            print(f"Halftone setup notice: {e}")

        pw = dc.GetDeviceCaps(win32con.HORZRES)
        ph = dc.GetDeviceCaps(win32con.VERTRES)

        dc.StartDoc("Mount Everest Higher Secondary School Certificate")
        for img in images:
            dc.StartPage()
            if str(color_mode).lower() in ('gray', 'grayscale', 'mono', 'black & white'):
                img_out = img.convert("L").convert("RGB")
            else:
                img_out = img.convert("RGB")

            dib = ImageWin.Dib(img_out)
            dib.draw(hdc_raw, (0, 0, pw, ph))
            dc.EndPage()

        dc.EndDoc()
        dc.DeleteDC()
        return True
    finally:
        win32print.ClosePrinter(hPrinter)

def print_pdf_file(pdf_path, printer_name=None):
    """
    Sends the PDF file to the printer.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
    abs_path = os.path.abspath(pdf_path)
    
    try:
        import win32api
        import win32print
        
        target_printer = printer_name or get_default_printer()
        if target_printer:
            win32api.ShellExecute(0, "printto", abs_path, f'"{target_printer}"', ".", 0)
            return True
        else:
            win32api.ShellExecute(0, "print", abs_path, None, ".", 0)
            return True
    except Exception as e:
        print(f"ShellExecute print failed: {e}. Falling back to os.startfile...")
        try:
            os.startfile(abs_path, "print")
            return True
        except Exception as e2:
            print(f"Fallback print failed: {e2}")
            open_pdf(abs_path)
            raise e2
