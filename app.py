import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageTk

from config import load_config, save_config, DEFAULT_CONFIG
from database import init_db, save_certificate, get_all_certificates, get_certificate_by_id, delete_certificate
from renderer import (
    CertificateRenderer, CERT_TYPES, PAPER_SIZES, get_page_dimensions,
    DEFAULT_POSITIONS, FIELD_METADATA, ADMIN_SAMPLE_DATA,
    load_positions, save_positions, save_certificate_position, reset_positions, IMG_W, IMG_H,
    compute_sl_no, to_sentence_case, clean_date_str
)
from printer import (
    get_printers, get_default_printer, print_pdf_file, open_pdf,
    open_printer_preferences, get_printer_paper_sizes, get_active_printer_paper_size,
    get_output_dir, open_output_folder, print_direct
)
from batch_processor import read_batch_file, create_sample_files
from tray_manager import SysTrayManager
from path_utils import get_asset_path, get_base_dir
from version import APP_VERSION, APP_NAME
import updater

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class CertificateApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self._hide_launcher_console()

        self.title("Mount Everest Higher Secondary School - Certificate Printing Studio (CBSE 1230048)")
        self.geometry("1460x940")
        self.minsize(1140, 760)

        # Set official school emblem icon for application window & taskbar
        ico_file = get_asset_path("assets", "app_icon.ico")
        png_file = get_asset_path("assets", "app_icon.png")
        if os.path.exists(ico_file):
            try:
                self.iconbitmap(ico_file)
            except Exception:
                pass
        if os.path.exists(png_file):
            try:
                self._app_icon_tk = ImageTk.PhotoImage(file=png_file)
                self.iconphoto(False, self._app_icon_tk)
            except Exception:
                pass

        self.config = load_config()
        init_db()
        self.renderer = CertificateRenderer()

        # State variables
        self.current_zoom = 0.85
        self.preview_image_tk = None
        self.batch_records = []
        self.batch_filename = ""
        self._student_dropdown_items = []
        self.current_student_idx = -1
        self.filtered_student_indices = []
        self.color_mode_var = ctk.StringVar(value=self.config.get("print_color_mode", "Color"))
        self.prompt_props_var = ctk.BooleanVar(value=True)
        self.current_cert_type = "provisional"
        self.output_dir = get_output_dir()

        # Printer paper cache
        self.printer_paper_list = []

        # Selective printing checkboxes state
        self.sel_provisional = ctk.BooleanVar(value=True)
        self.sel_character = ctk.BooleanVar(value=False)
        self.sel_transfer = ctk.BooleanVar(value=False)
        self.sel_reading = ctk.BooleanVar(value=False)

        # Admin Alignment Portal State
        self.admin_authenticated = False
        self.admin_cert_type = "reading"
        self.admin_positions = load_positions()
        self.admin_selected_field = "class_roll_no"
        self.admin_zoom = 0.70
        self.admin_mode = "full"
        self.admin_show_crosshairs = ctk.BooleanVar(value=True)
        self.admin_step_val = 5
        self.admin_preview_image_tk = None
        self._admin_drag_data = {"start_x": 0, "start_y": 0, "field_start_x": 0, "field_start_y": 0}

        # Build UI
        self._build_header()
        self._build_tabs()

        # Keyboard shortcuts for live arrow nudging in Admin Portal
        self.bind("<Left>", lambda e: self._on_admin_key_nudge(-1, 0, e))
        self.bind("<Right>", lambda e: self._on_admin_key_nudge(1, 0, e))
        self.bind("<Up>", lambda e: self._on_admin_key_nudge(0, -1, e))
        self.bind("<Down>", lambda e: self._on_admin_key_nudge(0, 1, e))

        # System tray icon setup & intercept window close to minimize to tray
        self.tray_manager = SysTrayManager(self)
        self.tray_manager.start()
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

        self.after(100, self._initial_setup)
        self.latest_update_info = None
        if self.config.get("auto_check_updates", True):
            self.after(3000, self._background_check_updates)

    def _hide_launcher_console(self):
        """Hides the launch console/cmd window once the GUI is starting up."""
        try:
            import ctypes
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass

    def minimize_to_tray(self):
        """Hides the main application window to the Windows System Tray."""
        self.withdraw()

    def restore_from_tray(self):
        """Restores and focuses the application window from the System Tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def exit_application(self):
        """Completely closes the application and removes the tray icon."""
        if hasattr(self, 'tray_manager') and self.tray_manager:
            self.tray_manager.stop()
        self.destroy()
        sys.exit(0)

    def on_window_close(self):
        """When user clicks X, minimize to system tray so it stays accessible."""
        self.minimize_to_tray()

    def _initial_setup(self):
        self._refresh_printer_papers()
        self.update_preview()

    def _open_admin_portal(self):
        self.tabview.set("  🛠️ Admin Alignment Portal  ")
        if not self.admin_authenticated:
            self._show_admin_lock_screen()
        else:
            self._show_admin_content_screen()

    def _on_tab_switched(self):
        tab_name = self.tabview.get()
        if "Records" in tab_name:
            self._load_records()
        elif "Admin" in tab_name:
            if not self.admin_authenticated:
                self._show_admin_lock_screen()
            else:
                self._show_admin_content_screen()

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, height=65, corner_radius=0, fg_color=("#1B365D", "#0F1E33"))
        header_frame.pack(side="top", fill="x")

        # School Emblem / Logo on the left side of the header
        logo_path = get_asset_path("assets", "app_icon.png")
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)
                self.header_logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(48, 50))
                self.header_logo_lbl = ctk.CTkLabel(header_frame, image=self.header_logo_ctk, text="")
                self.header_logo_lbl.pack(side="left", padx=(16, 0), pady=6)
            except Exception as e:
                print(f"Error loading header logo: {e}")

        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.pack(side="left", padx=(12, 20), pady=8)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="MOUNT EVEREST HIGHER SECONDARY SCHOOL",
            font=ctk.CTkFont(family="Times New Roman", size=19, weight="bold"),
            text_color="#FFFFFF"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="Taphou, Senapati - 795106, Manipur | CBSE Affiliation No. 1230048",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#CBD5E1"
        )
        sub_lbl.pack(anchor="w")

        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.pack(side="right", padx=20, pady=12)

        # Open Output Folder Button
        ctk.CTkButton(
            right_box,
            text="📂 Output Folder",
            width=120,
            height=30,
            fg_color="#059669",
            hover_color="#047857",
            command=open_output_folder
        ).pack(side="left", padx=6)

        # Admin Alignment Portal Button
        ctk.CTkButton(
            right_box,
            text="🛠️ Admin Alignment",
            width=140,
            height=30,
            fg_color="#D97706",
            hover_color="#B45309",
            command=self._open_admin_portal
        ).pack(side="left", padx=6)

        def_printer = get_default_printer() or "No Default Printer"
        self.printer_badge = ctk.CTkLabel(
            right_box,
            text=f"🖨️ {def_printer}",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#2563EB", "#1D4ED8"),
            text_color="#FFFFFF",
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.printer_badge.pack(side="left", padx=8)

        self.theme_btn = ctk.CTkButton(
            right_box,
            text="🌙 Theme",
            width=76,
            height=28,
            fg_color=("#334155", "#475569"),
            command=self._toggle_theme
        )
        self.theme_btn.pack(side="left", padx=(0, 4))

        # Check for updates / current version button
        self.update_btn = ctk.CTkButton(
            right_box,
            text=f"🔄 v{APP_VERSION}",
            width=90,
            height=28,
            fg_color=("#1E293B", "#334155"),
            hover_color=("#334155", "#475569"),
            command=self.open_updates_dialog
        )
        self.update_btn.pack(side="left", padx=(0, 4))

        # Tray button to minimize to Windows System Tray
        ctk.CTkButton(
            right_box,
            text="📥 To Tray",
            width=76,
            height=28,
            fg_color=("#1E293B", "#0F172A"),
            hover_color=("#334155", "#1E293B"),
            command=self.minimize_to_tray
        ).pack(side="left", padx=(0, 4))

        # Exit application button
        ctk.CTkButton(
            right_box,
            text="❌ Exit",
            width=62,
            height=28,
            fg_color=("#991B1B", "#7F1D1D"),
            hover_color=("#B91C1C", "#991B1B"),
            command=self.exit_application
        ).pack(side="left")

    def _toggle_theme(self):
        curr = ctk.get_appearance_mode()
        new_theme = "Dark" if curr == "Light" else "Light"
        ctk.set_appearance_mode(new_theme)
        self.theme_btn.configure(text="☀️ Theme" if new_theme == "Dark" else "🌙 Theme")
        self.config['theme'] = new_theme.lower()
        save_config(self.config)

    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=8, command=self._on_tab_switched)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        self.tab_single = self.tabview.add("  📄 Certificate Studio (4 Certificates)  ")
        self.tab_batch = self.tabview.add("  📊 Batch Processing (Excel/CSV)  ")
        self.tab_records = self.tabview.add("  📁 Records & Search  ")
        self.tab_calib = self.tabview.add("  ⚙️ Printer Paper & Calibration  ")
        self.tab_admin = self.tabview.add("  🛠️ Admin Alignment Portal  ")

        self._build_single_tab()
        self._build_batch_tab()
        self._build_records_tab()
        self._build_calib_tab()
        self._build_admin_tab()

    # =========================================================================
    # TAB 1: SINGLE CERTIFICATE STUDIO
    # =========================================================================
    def _build_single_tab(self):
        container = self.tab_single
        container.grid_columnconfigure(0, weight=4, minsize=480)
        container.grid_columnconfigure(1, weight=6, minsize=600)
        container.grid_rowconfigure(0, weight=1)

        # LEFT PANE: Form Controls
        left_frame = ctk.CTkScrollableFrame(container, corner_radius=8)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        # Certificate Type Selector
        ctk.CTkLabel(left_frame, text="Active Certificate:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(2, 4))
        self.cert_type_seg = ctk.CTkSegmentedButton(
            left_frame,
            values=["Provisional", "Character", "Transfer", "Reading"],
            command=self._on_cert_type_change
        )
        self.cert_type_seg.set("Provisional")
        self.cert_type_seg.pack(fill="x", pady=(0, 6))

        # =====================================================================
        # BATCH STUDENT QUICK SELECTOR & SEARCH BAR (Automatic from Excel/CSV!)
        # =====================================================================
        self.student_bar = ctk.CTkFrame(left_frame, fg_color=("#F0FDF4", "#064E3B"), corner_radius=8, border_width=1, border_color="#10B981")
        self.student_bar.pack(fill="x", pady=(0, 8), padx=2)

        # Row 1: Header & Batch Source
        sb_head = ctk.CTkFrame(self.student_bar, fg_color="transparent")
        sb_head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(
            sb_head,
            text="👨‍🎓 Student Selector (From Batch / File):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#065F46", "#34D399")
        ).pack(side="left")

        self.batch_src_lbl = ctk.CTkLabel(
            sb_head,
            text="No batch loaded",
            font=ctk.CTkFont(size=10),
            text_color=("#047857", "#6EE7B7")
        )
        self.batch_src_lbl.pack(side="left", padx=6)

        ctk.CTkButton(
            sb_head,
            text="📊 Batch Tab",
            width=76,
            height=22,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._switch_to_batch_tab
        ).pack(side="right")

        # Row 2: Search Box & Search Button
        sb_search = ctk.CTkFrame(self.student_bar, fg_color="transparent")
        sb_search.pack(fill="x", padx=8, pady=2)

        self.ent_student_search = ctk.CTkEntry(
            sb_search,
            placeholder_text="Search student name, roll, reg...",
            height=28,
            font=ctk.CTkFont(size=12)
        )
        self.ent_student_search.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.ent_student_search.bind("<Return>", lambda _: self._search_student())

        self.btn_student_search = ctk.CTkButton(
            sb_search,
            text="🔍 Search",
            width=65,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#047857",
            hover_color="#065F46",
            command=self._search_student
        )
        self.btn_student_search.pack(side="left", padx=(0, 4))

        self.btn_student_reset = ctk.CTkButton(
            sb_search,
            text="Reset",
            width=46,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=("#64748B", "#475569"),
            command=self._reset_student_search
        )
        self.btn_student_reset.pack(side="left")

        # Row 3: Dropdown list of students & Prev/Next buttons
        sb_select = ctk.CTkFrame(self.student_bar, fg_color="transparent")
        sb_select.pack(fill="x", padx=8, pady=(2, 6))

        self.btn_prev_student = ctk.CTkButton(
            sb_select,
            text="◀",
            width=28,
            height=28,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            command=self._prev_student
        )
        self.btn_prev_student.pack(side="left", padx=(0, 4))

        self._student_dropdown_items = ["-- No students loaded (Upload in Batch) --"]
        self.cmb_students = ctk.CTkComboBox(
            sb_select,
            values=self._student_dropdown_items,
            height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_student_dropdown_selected
        )
        self.cmb_students.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_next_student = ctk.CTkButton(
            sb_select,
            text="▶",
            width=28,
            height=28,
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            command=self._next_student
        )
        self.btn_next_student.pack(side="left", padx=(0, 4))

        self.lbl_student_counter = ctk.CTkLabel(
            sb_select,
            text="0/0",
            width=36,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("#065F46", "#A7F3D0")
        )
        self.lbl_student_counter.pack(side="left")

        # Paper Size & Print Mode Bar
        top_ctrl_box = ctk.CTkFrame(left_frame, fg_color=("#F1F5F9", "#1E293B"), corner_radius=6)
        top_ctrl_box.pack(fill="x", pady=(2, 8), padx=2)

        # Mode row
        m_row = ctk.CTkFrame(top_ctrl_box, fg_color="transparent")
        m_row.pack(fill="x", padx=8, pady=(6, 3))
        ctk.CTkLabel(m_row, text="Print Mode:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        self.print_mode_var = ctk.StringVar(value=self.config.get("print_mode", "full"))
        ctk.CTkSegmentedButton(
            m_row,
            values=["full", "overlay"],
            variable=self.print_mode_var,
            command=self._on_mode_change
        ).pack(side="left", fill="x", expand=True)

        # Color row: Color vs Grayscale selection
        c_row = ctk.CTkFrame(top_ctrl_box, fg_color="transparent")
        c_row.pack(fill="x", padx=8, pady=(3, 3))
        ctk.CTkLabel(c_row, text="Print Color:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        self.color_mode_var = ctk.StringVar(value=self.config.get("print_color_mode", "Color"))
        ctk.CTkSegmentedButton(
            c_row,
            values=["Color", "Grayscale"],
            variable=self.color_mode_var,
            command=self._on_color_mode_change
        ).pack(side="left", fill="x", expand=True)

        # Paper size row
        p_row = ctk.CTkFrame(top_ctrl_box, fg_color="transparent")
        p_row.pack(fill="x", padx=8, pady=(3, 6))
        ctk.CTkLabel(p_row, text="Paper Size:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 6))
        
        self.paper_size_var = ctk.StringVar(value="10.5x7.5")
        self.opt_paper = ctk.CTkOptionMenu(
            p_row,
            values=["10.5x7.5 (Certificate 10.5\" x 7.5\")", "Auto (Printer Setup)", "A4", "Letter"],
            command=self._on_paper_size_select
        )
        self.opt_paper.pack(side="left", fill="x", expand=True)

        # Selective Print Section (Page 1 Prov, Page 2 Char, Page 3 Trans, Page 4 Read)
        sel_frame = ctk.CTkFrame(left_frame, fg_color=("#EFF6FF", "#172554"), corner_radius=6)
        sel_frame.pack(fill="x", pady=(4, 8), padx=2)

        f_sel_head = ctk.CTkFrame(sel_frame, fg_color="transparent")
        f_sel_head.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(f_sel_head, text="📑 Select Certificates to Print / Export:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#1D4ED8").pack(side="left")
        
        ctk.CTkButton(f_sel_head, text="All 4 Pages", width=75, height=22, font=ctk.CTkFont(size=10), command=self._select_all_certs).pack(side="right", padx=2)
        ctk.CTkButton(f_sel_head, text="Only Current", width=80, height=22, font=ctk.CTkFont(size=10), command=self._select_current_cert).pack(side="right", padx=2)

        # 4 Checkboxes
        f_checks = ctk.CTkFrame(sel_frame, fg_color="transparent")
        f_checks.pack(fill="x", padx=8, pady=(2, 6))

        c1 = ctk.CTkCheckBox(f_checks, text="1. Provisional", variable=self.sel_provisional, font=ctk.CTkFont(size=11))
        c1.grid(row=0, column=0, sticky="w", padx=4, pady=2)
        c2 = ctk.CTkCheckBox(f_checks, text="2. Character", variable=self.sel_character, font=ctk.CTkFont(size=11))
        c2.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        c3 = ctk.CTkCheckBox(f_checks, text="3. Transfer", variable=self.sel_transfer, font=ctk.CTkFont(size=11))
        c3.grid(row=1, column=0, sticky="w", padx=4, pady=2)
        c4 = ctk.CTkCheckBox(f_checks, text="4. Reading", variable=self.sel_reading, font=ctk.CTkFont(size=11))
        c4.grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # Dynamic Form Container
        self.form_container = ctk.CTkFrame(left_frame, fg_color="transparent")
        self.form_container.pack(fill="x", pady=2)

        self._build_form_fields()

        # Strike out unselected check
        self.strike_var = ctk.BooleanVar(value=self.config.get("strike_unused", False))
        f_strike = ctk.CTkCheckBox(
            left_frame,
            text="Strike out non-applicable options (e.g. strike AISSCE for AISSE)",
            variable=self.strike_var,
            font=ctk.CTkFont(size=11),
            command=self.update_preview
        )
        f_strike.pack(fill="x", pady=(4, 6))

        # Action Buttons
        btn_box1 = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_box1.pack(fill="x", pady=3)

        self.btn_print = ctk.CTkButton(
            btn_box1,
            text="🖨️ Quick Print Selected",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#059669",
            hover_color="#047857",
            command=self.print_current_certificate
        )
        self.btn_print.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_dialog_print = ctk.CTkButton(
            btn_box1,
            text="🖨️ Print Setup / Dialog",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self.print_via_dialog
        )
        self.btn_dialog_print.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Checkbox: Prompt properties before printing
        self.chk_prompt_props = ctk.CTkCheckBox(
            left_frame,
            text="Show Printer Properties before printing (Paper Tray, Size, Quality)",
            variable=self.prompt_props_var,
            font=ctk.CTkFont(size=11)
        )
        self.chk_prompt_props.pack(fill="x", pady=(2, 4))

        btn_box2 = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_box2.pack(fill="x", pady=(3, 3))

        self.btn_save_pdf = ctk.CTkButton(
            btn_box2,
            text="📄 Save Selected to PDF",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.save_current_pdf
        )
        self.btn_save_pdf.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_view_pdf = ctk.CTkButton(
            btn_box2,
            text="👁️ Open in Viewer",
            height=34,
            fg_color=("#475569", "#334155"),
            command=self.open_current_in_viewer
        )
        self.btn_view_pdf.pack(side="left", fill="x", expand=True, padx=(4, 0))

        btn_box3 = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_box3.pack(fill="x", pady=(3, 8))

        self.btn_save_db = ctk.CTkButton(
            btn_box3,
            text="💾 Save Record",
            height=32,
            fg_color=("#334155", "#1E293B"),
            command=self.save_current_record
        )
        self.btn_save_db.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_reset = ctk.CTkButton(
            btn_box3,
            text="🔄 Clear",
            width=65,
            height=32,
            fg_color=("#DC2626", "#B91C1C"),
            command=self.reset_form
        )
        self.btn_reset.pack(side="left", padx=(4, 0))

        # RIGHT PANE: Certificate Live Preview
        right_frame = ctk.CTkFrame(container, corner_radius=8)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        preview_tool = ctk.CTkFrame(right_frame, height=40, fg_color="transparent")
        preview_tool.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))

        self.preview_title_lbl = ctk.CTkLabel(
            preview_tool,
            text="Live Preview: Provisional Certificate (10.5\" × 7.5\")",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.preview_title_lbl.pack(side="left")

        zoom_box = ctk.CTkFrame(preview_tool, fg_color="transparent")
        zoom_box.pack(side="right")

        ctk.CTkButton(zoom_box, text="➖", width=30, height=26, command=self._zoom_out).pack(side="left", padx=2)
        self.zoom_lbl = ctk.CTkLabel(zoom_box, text=f"{int(self.current_zoom*100)}%", width=45)
        self.zoom_lbl.pack(side="left")
        ctk.CTkButton(zoom_box, text="➕", width=30, height=26, command=self._zoom_in).pack(side="left", padx=2)
        ctk.CTkButton(zoom_box, text="Fit", width=42, height=26, command=self._zoom_fit).pack(side="left", padx=(4, 0))

        self.preview_canvas_frame = ctk.CTkFrame(right_frame, fg_color=("#E2E8F0", "#1E293B"), corner_radius=6)
        self.preview_canvas_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        
        self.preview_lbl = tk.Label(self.preview_canvas_frame, bg="#E2E8F0")
        self.preview_lbl.pack(expand=True, padx=6, pady=6)

        foot_info = ctk.CTkFrame(right_frame, height=28, fg_color="transparent")
        foot_info.grid(row=2, column=0, sticky="ew", padx=10, pady=(2, 6))

        self.mode_info_lbl = ctk.CTkLabel(
            foot_info,
            text="Paper: 10.5\" × 7.5\" (266.7 × 190.5 mm) | Mode: Full Certificate",
            font=ctk.CTkFont(size=11),
            text_color=("#475569", "#94A3B8")
        )
        self.mode_info_lbl.pack(side="left")

        self.status_lbl = ctk.CTkLabel(
            foot_info,
            text="Ready",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#059669"
        )
        self.status_lbl.pack(side="right")

    def _select_all_certs(self):
        self.sel_provisional.set(True)
        self.sel_character.set(True)
        self.sel_transfer.set(True)
        self.sel_reading.set(True)

    def _select_current_cert(self):
        self.sel_provisional.set(self.current_cert_type == "provisional")
        self.sel_character.set(self.current_cert_type == "character")
        self.sel_transfer.set(self.current_cert_type == "transfer")
        self.sel_reading.set(self.current_cert_type == "reading")

    def get_selected_cert_types(self) -> list:
        types = []
        if self.sel_provisional.get(): types.append("provisional")
        if self.sel_character.get(): types.append("character")
        if self.sel_transfer.get(): types.append("transfer")
        if self.sel_reading.get(): types.append("reading")
        if not types:
            # Fallback to current
            types.append(self.current_cert_type)
        return types

    def _refresh_printer_papers(self):
        printer_name = self.config.get("printer_name") or get_default_printer()
        self.printer_paper_list = get_printer_paper_sizes(printer_name)

        active_info = get_active_printer_paper_size(printer_name)
        active_label = f"Auto (Printer Setup: {active_info['name']})" if active_info else "Auto (Printer Setup)"

        # Populate menu options
        options = [
            active_label,
            '10.5x7.5 (Certificate 10.5" x 7.5")',
            '10.0x7.5 (10.0" x 7.5")',
            'A4 (210 x 297 mm)',
            'Letter (8.5" x 11")'
        ]

        # Add printer's own paper sizes
        for p in self.printer_paper_list[:12]:
            lbl = f"Printer: {p['name']}"
            if lbl not in options:
                options.append(lbl)

        self.opt_paper.configure(values=options)

    def _on_paper_size_select(self, val):
        if "Auto" in val:
            # Retrieve active setup from printer
            printer_name = self.config.get("printer_name") or get_default_printer()
            active = get_active_printer_paper_size(printer_name)
            if active:
                self.config['custom_width_pt'] = active['width_pt']
                self.config['custom_height_pt'] = active['height_pt']
                self.config['paper_size'] = "Custom"
        elif "10.5x7.5" in val:
            self.config['paper_size'] = "10.5x7.5"
            self.config['custom_width_pt'] = None
            self.config['custom_height_pt'] = None
        elif "10.0x7.5" in val:
            self.config['paper_size'] = "10.0x7.5"
            self.config['custom_width_pt'] = None
            self.config['custom_height_pt'] = None
        elif "A4" in val:
            self.config['paper_size'] = "A4"
            self.config['custom_width_pt'] = None
            self.config['custom_height_pt'] = None
        elif "Letter" in val:
            self.config['paper_size'] = "Letter"
            self.config['custom_width_pt'] = None
            self.config['custom_height_pt'] = None
        elif "Printer:" in val:
            pname = val.replace("Printer: ", "").strip()
            for p in self.printer_paper_list:
                if p['name'] == pname:
                    self.config['custom_width_pt'] = p['width_pt']
                    self.config['custom_height_pt'] = p['height_pt']
                    self.config['paper_size'] = "Custom"
                    break

        save_config(self.config)
        self._update_footer_info()
        self.update_preview()

    def _build_form_fields(self, preserve_data=None):
        for widget in self.form_container.winfo_children():
            widget.destroy()

        ctype = self.current_cert_type
        input_font = ctk.CTkFont(size=13)
        p = preserve_data or {}

        # 1. Sl. No.
        f_sl = ctk.CTkFrame(self.form_container, fg_color="transparent")
        f_sl.pack(fill="x", pady=2)
        ctk.CTkLabel(f_sl, text="Sl. No.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.ent_sl = ctk.CTkEntry(f_sl, placeholder_text="e.g. 042 or Sc/A/18", font=input_font)
        init_sl = p.get('sl_no', '')
        if init_sl:
            self.ent_sl.insert(0, str(init_sl))
        self.ent_sl.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.auto_sl_var = ctk.BooleanVar(value=self.config.get("auto_increment_sl", False))
        ctk.CTkCheckBox(f_sl, text="Auto+1", variable=self.auto_sl_var, width=60).pack(side="left")

        # 2. Student Name
        f_name = ctk.CTkFrame(self.form_container, fg_color="transparent")
        f_name.pack(fill="x", pady=2)
        ctk.CTkLabel(f_name, text="Student Name:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.ent_name = ctk.CTkEntry(f_name, placeholder_text="Full Name", font=input_font)
        init_name = to_sentence_case(p.get('student_name', ''))
        if init_name:
            self.ent_name.insert(0, init_name)
        self.ent_name.pack(side="left", fill="x", expand=True, padx=(4, 6))
        ctk.CTkButton(f_name, text="Aa", width=42, font=ctk.CTkFont(weight="bold"), command=self._apply_sentence_case).pack(side="left")

        # Father & Mother
        if ctype in ('provisional', 'transfer', 'reading'):
            f_p = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_p.pack(fill="x", pady=2)
            ctk.CTkLabel(f_p, text="S/o, D/o Mr.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_father = ctk.CTkEntry(f_p, placeholder_text="Father's Name", font=input_font)
            init_father = to_sentence_case(p.get('father_name', ''))
            if init_father:
                self.ent_father.insert(0, init_father)
            self.ent_father.pack(side="left", fill="x", expand=True, padx=(4, 6))

            f_m = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_m.pack(fill="x", pady=2)
            ctk.CTkLabel(f_m, text="& Mrs.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_mother = ctk.CTkEntry(f_m, placeholder_text="Mother's Name", font=input_font)
            init_mother = to_sentence_case(p.get('mother_name', ''))
            if init_mother:
                self.ent_mother.insert(0, init_mother)
            self.ent_mother.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_father = None
            self.ent_mother = None

        # Address
        if ctype in ('provisional', 'reading'):
            f_addr = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_addr.pack(fill="x", pady=2)
            ctk.CTkLabel(f_addr, text="Inhabitant of:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_address = ctk.CTkEntry(f_addr, placeholder_text="Address / Village", font=input_font)
            init_addr = to_sentence_case(p.get('address', ''))
            if init_addr:
                self.ent_address.insert(0, init_addr)
            self.ent_address.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_address = None

        # Exam Name & Year
        if ctype in ('provisional', 'character', 'transfer'):
            f_exam = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_exam.pack(fill="x", pady=2)
            ctk.CTkLabel(f_exam, text="Exam & Year:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.opt_exam = ctk.CTkOptionMenu(f_exam, values=["AISSCE (Class 12)", "AISSE (Class 10)"], width=130, command=lambda _: self.update_preview())
            init_exam = p.get('exam_name', "AISSCE (Class 12)")
            if "10" in init_exam or "AISSE" in init_exam.upper():
                self.opt_exam.set("AISSE (Class 10)")
            else:
                self.opt_exam.set("AISSCE (Class 12)")
            self.opt_exam.pack(side="left", padx=(4, 6))
            self.ent_year = ctk.CTkEntry(f_exam, placeholder_text="2024 or 24", width=80, font=input_font)
            init_year = p.get('exam_year', '')
            if init_year:
                self.ent_year.insert(0, init_year)
            self.ent_year.pack(side="left", fill="x", expand=True)
        else:
            self.opt_exam = None
            self.ent_year = None

        # Roll Number
        if ctype in ('provisional', 'character', 'transfer'):
            f_roll = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_roll.pack(fill="x", pady=2)
            ctk.CTkLabel(f_roll, text="CBSE Roll No.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_roll = ctk.CTkEntry(f_roll, placeholder_text="e.g. 12105482", font=input_font)
            init_roll = p.get('roll_no', '')
            if init_roll:
                self.ent_roll.insert(0, init_roll)
            self.ent_roll.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_roll = None

        # Grade
        if ctype in ('provisional', 'character', 'transfer'):
            f_gr = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_gr.pack(fill="x", pady=2)
            ctk.CTkLabel(f_gr, text="Grade / Result:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.opt_grade = ctk.CTkComboBox(f_gr, values=["A1", "A2", "B1", "B2", "C1", "C2", "Passed", "Qualifying"], width=120, command=lambda _: self.update_preview())
            init_grade = p.get('grade', '')
            if init_grade:
                self.opt_grade.set(init_grade)
            else:
                self.opt_grade.set("")
            self.opt_grade.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.opt_grade = None

        # Academic Session
        if ctype in ('character', 'transfer', 'reading'):
            f_sess = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_sess.pack(fill="x", pady=2)
            ctk.CTkLabel(f_sess, text="Academic Session:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_session = ctk.CTkEntry(f_sess, placeholder_text="e.g. 2023 - 2024", font=input_font)
            init_sess = p.get('session', '')
            if init_sess:
                self.ent_session.insert(0, init_sess)
            self.ent_session.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_session = None

        # Reading Certificate specifics
        if ctype == 'reading':
            f_cls = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_cls.pack(fill="x", pady=2)
            ctk.CTkLabel(f_cls, text="Class & Stream:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_class = ctk.CTkOptionMenu(f_cls, values=["XI", "XII", "X", "IX"], width=70, command=lambda _: self.update_preview())
            init_cls = p.get('class_name', "XII")
            self.ent_class.set(init_cls)
            self.ent_class.pack(side="left", padx=(4, 6))
            self.ent_stream = ctk.CTkOptionMenu(
                f_cls,
                values=["Science", "Arts", "Commerce"],
                width=90,
                command=lambda _: (self._auto_update_sl_no(), self.update_preview())
            )
            init_stream = p.get('stream', "Science")
            self.ent_stream.set(init_stream)
            self.ent_stream.pack(side="left", fill="x", expand=True)

            f_sec = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_sec.pack(fill="x", pady=2)
            ctk.CTkLabel(f_sec, text="Section & Class Roll:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_section = ctk.CTkEntry(f_sec, placeholder_text="Sec A/B", width=70, font=input_font)
            init_sec = p.get('section', '')
            if init_sec:
                self.ent_section.insert(0, init_sec)
            self.ent_section.pack(side="left", padx=(4, 6))
            self.ent_class_roll = ctk.CTkEntry(f_sec, placeholder_text="Class Roll No", width=90, font=input_font)
            init_roll_cls = p.get('class_roll_no', '')
            if init_roll_cls:
                self.ent_class_roll.insert(0, init_roll_cls)
            self.ent_class_roll.pack(side="left", fill="x", expand=True)
        else:
            self.ent_class = None
            self.ent_stream = None
            self.ent_section = None
            self.ent_class_roll = None

        # Date of Birth
        if ctype in ('provisional', 'transfer', 'reading'):
            f_dob = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_dob.pack(fill="x", pady=2)
            ctk.CTkLabel(f_dob, text="Date of Birth (DOB):", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_dob = ctk.CTkEntry(f_dob, placeholder_text="DD/MM/YYYY", font=input_font)
            init_dob = clean_date_str(p.get('dob', ''))
            if init_dob:
                self.ent_dob.insert(0, init_dob)
            self.ent_dob.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_dob = None

        # Registration No (Provisional, Character, Transfer)
        # Sl. No. and Reg. No. are strictly identical across Provisional, Character, Transfer!
        if ctype in ('provisional', 'character', 'transfer'):
            f_reg = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_reg.pack(fill="x", pady=2)
            ctk.CTkLabel(f_reg, text="CBSE Reg. No.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_reg = ctk.CTkEntry(f_reg, placeholder_text="R/1/24/1230048/...", font=input_font)
            default_reg = p.get('reg_no', '')
            if default_reg:
                self.ent_reg.insert(0, default_reg)
            self.ent_reg.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_reg = None

        # Result Announcement Date
        if ctype == 'provisional':
            f_res = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_res.pack(fill="x", pady=2)
            ctk.CTkLabel(f_res, text="Result Announced on:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_result_date = ctk.CTkEntry(f_res, placeholder_text="e.g. 13th May, 2024", font=input_font)
            init_res = clean_date_str(p.get('result_date', ''))
            if init_res:
                self.ent_result_date.insert(0, init_res)
            self.ent_result_date.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_result_date = None

        # Transfer Certificate specifics
        if ctype == 'transfer':
            f_left = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_left.pack(fill="x", pady=2)
            ctk.CTkLabel(f_left, text="Left School On:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_left_date = ctk.CTkEntry(f_left, placeholder_text="DD/MM/YYYY", font=input_font)
            init_left = clean_date_str(p.get('left_date', ''))
            if init_left:
                self.ent_left_date.insert(0, init_left)
            self.ent_left_date.pack(side="left", fill="x", expand=True, padx=(4, 0))

            f_pen = ctk.CTkFrame(self.form_container, fg_color="transparent")
            f_pen.pack(fill="x", pady=2)
            ctk.CTkLabel(f_pen, text="PEN No.:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
            self.ent_pen = ctk.CTkEntry(f_pen, placeholder_text="Permanent Education Number", font=input_font)
            init_pen = p.get('pen_no', '')
            if init_pen:
                self.ent_pen.insert(0, init_pen)
            self.ent_pen.pack(side="left", fill="x", expand=True, padx=(4, 0))
        else:
            self.ent_left_date = None
            self.ent_pen = None

        # Issue Date (Auto from current date!)
        f_date = ctk.CTkFrame(self.form_container, fg_color="transparent")
        f_date.pack(fill="x", pady=2)
        ctk.CTkLabel(f_date, text="Dated, Senapati:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.ent_date = ctk.CTkEntry(f_date, placeholder_text="DD/MM/YYYY", font=input_font)
        
        init_date = clean_date_str(p.get('issue_date')) or datetime.now().strftime("%d/%m/%Y")
        self.ent_date.insert(0, init_date)
        self.ent_date.pack(side="left", fill="x", expand=True, padx=(4, 6))

        self.auto_today_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(f_date, text="Auto Today", variable=self.auto_today_var, width=80).pack(side="left")

        # Initial Sl. No. calculation:
        # If preserving data, maintain the exact same Sl. No. for Provisional, Character, Transfer!
        saved_sl = p.get('sl_no', '')
        if saved_sl:
            self.ent_sl.delete(0, "end")
            self.ent_sl.insert(0, str(saved_sl))
        else:
            self._auto_update_sl_no()

        # Bind entries for real-time live preview & Sl No generation
        for widget in [
            self.ent_sl, self.ent_name, self.ent_father, self.ent_mother,
            self.ent_address, self.ent_year, self.ent_roll, self.ent_session,
            self.ent_dob, self.ent_result_date, self.ent_left_date,
            self.ent_pen, self.ent_date
        ]:
            if widget is not None:
                widget.bind("<KeyRelease>", lambda _: self.update_preview())

        # Registration entry binding for dynamic last 3 digit Sl. No.
        if self.ent_reg is not None:
            self.ent_reg.bind("<KeyRelease>", lambda _: (self._auto_update_sl_no(), self.update_preview()))

        # Reading certificate stream, section & class roll binding for Sl. No.
        if self.ent_section is not None:
            self.ent_section.bind("<KeyRelease>", lambda _: (self._auto_update_sl_no(), self.update_preview()))
        if self.ent_class_roll is not None:
            self.ent_class_roll.bind("<KeyRelease>", lambda _: (self._auto_update_sl_no(), self.update_preview()))

    def _on_cert_type_change(self, val):
        prev_data = self.get_current_form_data() if hasattr(self, 'ent_name') and self.ent_name else None
        self.current_cert_type = val.lower()
        self._build_form_fields(preserve_data=prev_data)
        # Ensure active cert is checked in selective printing
        self._select_current_cert()
        self._update_footer_info()
        self.update_preview()

    def _apply_sentence_case(self):
        """Converts student name, father name, mother name, and address to clean Sentence Case."""
        for entry in [self.ent_name, self.ent_father, self.ent_mother, self.ent_address]:
            if entry is not None:
                txt = entry.get()
                if txt:
                    entry.delete(0, "end")
                    entry.insert(0, to_sentence_case(txt))
        self.update_preview()

    def _on_mode_change(self, val):
        self.config['print_mode'] = val
        self._update_footer_info()
        self.update_preview()

    def _update_footer_info(self):
        cname = CERT_TYPES.get(self.current_cert_type, {}).get('name', 'Certificate')
        mode = self.config.get("print_mode", "full")
        mode_txt = "Full Certificate" if mode == "full" else "Pre-printed Sheet Overlay"
        
        w_pt, h_pt = get_page_dimensions(self.config)
        w_in = w_pt / 72.0
        h_in = h_pt / 72.0
        w_mm = w_in * 25.4
        h_mm = h_in * 25.4

        self.preview_title_lbl.configure(text=f"Live Preview: {cname} ({w_in:.1f}\" × {h_in:.1f}\")")
        self.mode_info_lbl.configure(text=f"Paper: {w_in:.1f}\" × {h_in:.1f}\" ({w_mm:.1f} × {h_mm:.1f} mm) | Mode: {mode_txt}")

    def _zoom_in(self):
        if self.current_zoom < 1.4:
            self.current_zoom += 0.1
            self.zoom_lbl.configure(text=f"{int(self.current_zoom*100)}%")
            self.update_preview()

    def _zoom_out(self):
        if self.current_zoom > 0.4:
            self.current_zoom -= 0.1
            self.zoom_lbl.configure(text=f"{int(self.current_zoom*100)}%")
            self.update_preview()

    def _zoom_fit(self):
        self.current_zoom = 0.85
        self.zoom_lbl.configure(text=f"{int(self.current_zoom*100)}%")
        self.update_preview()

    def get_current_form_data(self) -> dict:
        # If auto today is checked, refresh to today's date
        if hasattr(self, 'auto_today_var') and self.auto_today_var.get() and self.ent_date:
            cur_date = datetime.now().strftime("%d/%m/%Y")
            self.ent_date.delete(0, "end")
            self.ent_date.insert(0, cur_date)

        sl = self.ent_sl.get().strip() if self.ent_sl else ''
        reg = self.ent_reg.get().strip() if self.ent_reg else ''
        stream = self.ent_stream.get().strip() if self.ent_stream else ''
        sec = self.ent_section.get().strip() if self.ent_section else ''
        roll = self.ent_class_roll.get().strip() if self.ent_class_roll else ''
        if not sl:
            sl = compute_sl_no(self.current_cert_type, reg_no=reg, stream=stream, section=sec, class_roll=roll)

        data = {
            'cert_type': self.current_cert_type,
            'sl_no': sl,
            'student_name': to_sentence_case(self.ent_name.get().strip()) if self.ent_name else '',
            'father_name': to_sentence_case(self.ent_father.get().strip()) if self.ent_father else '',
            'mother_name': to_sentence_case(self.ent_mother.get().strip()) if self.ent_mother else '',
            'address': to_sentence_case(self.ent_address.get().strip()) if self.ent_address else '',
            'exam_name': self.opt_exam.get().split()[0] if self.opt_exam else 'AISSCE',
            'exam_year': self.ent_year.get().strip() if self.ent_year else '2024',
            'roll_no': self.ent_roll.get().strip() if self.ent_roll else '',
            'grade': self.opt_grade.get().strip() if self.opt_grade else '',
            'session': self.ent_session.get().strip() if self.ent_session else '',
            'dob': clean_date_str(self.ent_dob.get().strip()) if self.ent_dob else '',
            'reg_no': self.ent_reg.get().strip() if self.ent_reg else '',
            'result_date': clean_date_str(self.ent_result_date.get().strip()) if self.ent_result_date else '',
            'left_date': clean_date_str(self.ent_left_date.get().strip()) if self.ent_left_date else '',
            'pen_no': self.ent_pen.get().strip() if self.ent_pen else '',
            'class_name': self.ent_class.get() if self.ent_class else '',
            'stream': self.ent_stream.get() if self.ent_stream else '',
            'section': self.ent_section.get().strip() if self.ent_section else '',
            'class_roll_no': self.ent_class_roll.get().strip() if self.ent_class_roll else '',
            'issue_date': clean_date_str(self.ent_date.get().strip()) if self.ent_date else datetime.now().strftime("%d/%m/%Y"),
            'status': 'qualified'
        }
        return data

    def update_preview(self):
        try:
            data = self.get_current_form_data()
            mode = self.print_mode_var.get()
            cfg = self.config.copy()
            cfg['strike_unused'] = self.strike_var.get()

            # Render 3000x2250 image
            pil_img = self.renderer.render_pil(data, mode=mode, cert_type=self.current_cert_type, config=cfg)

            preview_base_w = 980
            preview_base_h = int(preview_base_w * (pil_img.height / pil_img.width))
            new_w = int(preview_base_w * self.current_zoom)
            new_h = int(preview_base_h * self.current_zoom)
            resized = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            self.preview_image_tk = ImageTk.PhotoImage(resized)
            self.preview_lbl.configure(image=self.preview_image_tk)
        except Exception as e:
            print(f"Preview update error: {e}")

    def save_current_pdf(self):
        data = self.get_current_form_data()
        selected_types = self.get_selected_cert_types()

        student = data.get('student_name', 'student').replace(' ', '_')
        sl = data.get('sl_no', '').replace('/', '_')
        type_desc = "_".join(t.capitalize() for t in selected_types)
        filename = f"{type_desc}_{sl}_{student}.pdf" if sl else f"{type_desc}_{student}.pdf"

        # Default destination is the dedicated Output_Certificates folder!
        default_save_path = os.path.join(get_output_dir(), filename)

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Document", "*.pdf")],
            initialdir=get_output_dir(),
            initialfile=filename,
            title="Save Selected Certificates as PDF"
        )
        if file_path:
            mode = self.print_mode_var.get()
            cfg = self.config.copy()
            cfg['strike_unused'] = self.strike_var.get()
            self.renderer.render_pdf([data], file_path, mode=mode, cert_type=self.current_cert_type, selected_cert_types=selected_types, config=cfg)
            self.status_lbl.configure(text=f"Saved {len(selected_types)} page(s) to Output", text_color="#059669")
            
            # Sl. No. is identical across Provisional, Character, Transfer (last 3 digits of registration)
            reg = data.get('reg_no', '')
            common_sl = data.get('sl_no', '')
            if not common_sl or '/' in str(common_sl):
                common_sl = compute_sl_no('provisional', reg_no=reg) or data.get('sl_no', '')

            # Save all selected cert types to database
            for t in selected_types:
                rec = data.copy()
                rec['cert_type'] = t
                if t in ('provisional', 'character', 'transfer'):
                    rec['sl_no'] = common_sl
                elif t == 'reading':
                    rec['sl_no'] = data.get('sl_no', '') if self.current_cert_type == 'reading' else compute_sl_no(
                        'reading', stream=data.get('stream', ''), section=data.get('section', ''), class_roll=data.get('class_roll_no', '')
                    )
                save_certificate(rec)
            self._load_records()

            confirm = messagebox.askyesno(
                "Certificates Saved",
                f"Successfully saved {len(selected_types)} certificate(s)!\n\n"
                f"Pages included: {', '.join(t.capitalize() for t in selected_types)}\n"
                f"Location: {file_path}\n\n"
                f"Open output folder now?"
            )
            if confirm:
                open_output_folder()

    def open_current_in_viewer(self):
        data = self.get_current_form_data()
        selected_types = self.get_selected_cert_types()
        
        out_pdf = os.path.join(get_output_dir(), f"Preview_{self.current_cert_type}_{datetime.now().strftime('%H%M%S')}.pdf")
        mode = self.print_mode_var.get()
        cfg = self.config.copy()
        cfg['strike_unused'] = self.strike_var.get()
        self.renderer.render_pdf([data], out_pdf, mode=mode, cert_type=self.current_cert_type, selected_cert_types=selected_types, config=cfg)
        open_pdf(out_pdf)
        self.status_lbl.configure(text="Opened in PDF Viewer", text_color="#2563EB")

    def _auto_update_sl_no(self):
        """
        Dynamically calculates and sets Sl. No. according to school rules:
        - Provisional, Character, Transfer: exact last 3 digits of CBSE Registration.
        - Reading Certificate: Exact from Stream (Science->Sc, Arts->AR, Commerce->Co), Section & Class Roll (e.g. Sc/A/18).
        """
        ctype = self.current_cert_type
        reg = self.ent_reg.get().strip() if self.ent_reg else ''
        stream = self.ent_stream.get().strip() if self.ent_stream else ''
        sec = self.ent_section.get().strip() if self.ent_section else ''
        roll = self.ent_class_roll.get().strip() if self.ent_class_roll else ''
        calculated_sl = compute_sl_no(ctype, reg_no=reg, stream=stream, section=sec, class_roll=roll)
        if calculated_sl and self.ent_sl:
            self.ent_sl.delete(0, "end")
            self.ent_sl.insert(0, calculated_sl)

    def _on_color_mode_change(self, val):
        self.config['print_color_mode'] = val
        save_config(self.config)
        self.update_preview()

    def _switch_to_batch_tab(self):
        self.tabview.set("  📊 Batch Processing (Excel/CSV)  ")

    def _sync_batch_to_studio(self, filename=""):
        if not self.batch_records:
            self._student_dropdown_items = ["-- No students loaded (Upload in Batch) --"]
            if hasattr(self, 'cmb_students'):
                self.cmb_students.configure(values=self._student_dropdown_items)
                self.cmb_students.set(self._student_dropdown_items[0])
            if hasattr(self, 'batch_src_lbl'):
                self.batch_src_lbl.configure(text="No batch loaded")
            if hasattr(self, 'lbl_student_counter'):
                self.lbl_student_counter.configure(text="0/0")
            return

        self._student_dropdown_items = []
        for i, r in enumerate(self.batch_records):
            name = r.get('student_name', 'Student').strip()
            roll = r.get('roll_no', '').strip()
            reg = r.get('reg_no', '').strip()
            sl = r.get('sl_no', '').strip()
            details = []
            if roll: details.append(f"Roll: {roll}")
            if reg: details.append(f"Reg: {reg[-4:] if len(reg)>=4 else reg}")
            if sl: details.append(f"Sl: {sl}")
            detail_str = f" ({' | '.join(details)})" if details else ""
            self._student_dropdown_items.append(f"{i+1}. {name}{detail_str}")

        self.filtered_student_indices = list(range(len(self.batch_records)))
        if hasattr(self, 'cmb_students'):
            self.cmb_students.configure(values=self._student_dropdown_items)
            self.cmb_students.set(self._student_dropdown_items[0])
        if hasattr(self, 'batch_src_lbl'):
            fname = filename or self.batch_filename or "Batch File"
            self.batch_src_lbl.configure(text=f"📁 {len(self.batch_records)} from {fname}")
        if hasattr(self, 'lbl_student_counter'):
            self.lbl_student_counter.configure(text=f"1/{len(self.batch_records)}")

        # Automatically load student #1 into Certificate Studio
        self._load_student_into_studio(0)

    def _load_student_into_studio(self, target):
        """
        Loads a student record into the Certificate Studio form fields.
        target can be an index (int) into self.batch_records or a dict record.
        """
        if isinstance(target, int):
            if 0 <= target < len(self.batch_records):
                rec = self.batch_records[target]
                self.current_student_idx = target
            else:
                return
        elif isinstance(target, dict):
            rec = target
            if rec in self.batch_records:
                self.current_student_idx = self.batch_records.index(rec)
        else:
            return

        # If record specifies certificate type, switch to it if needed
        rec_type = (rec.get('cert_type') or '').lower()
        if rec_type in CERT_TYPES and rec_type != self.current_cert_type:
            self.cert_type_seg.set(rec_type.capitalize())
            self._on_cert_type_change(rec_type.capitalize())

        ctype = self.current_cert_type

        # Populate all fields (enforcing clean Sentence Case for names & address)
        if self.ent_name:
            self.ent_name.delete(0, "end")
            self.ent_name.insert(0, to_sentence_case(rec.get('student_name', '')))
        if self.ent_father:
            self.ent_father.delete(0, "end")
            self.ent_father.insert(0, to_sentence_case(rec.get('father_name', '')))
        if self.ent_mother:
            self.ent_mother.delete(0, "end")
            self.ent_mother.insert(0, to_sentence_case(rec.get('mother_name', '')))
        if self.ent_address:
            self.ent_address.delete(0, "end")
            self.ent_address.insert(0, to_sentence_case(rec.get('address', '')))
        if self.ent_roll:
            self.ent_roll.delete(0, "end")
            self.ent_roll.insert(0, rec.get('roll_no', ''))
        if self.ent_year:
            self.ent_year.delete(0, "end")
            self.ent_year.insert(0, rec.get('exam_year', '2024'))
        if self.opt_exam and rec.get('exam_name'):
            ex = rec.get('exam_name')
            self.opt_exam.set("AISSE (Class 10)" if "10" in ex or "AISSE" in ex.upper() else "AISSCE (Class 12)")
        if self.opt_grade and rec.get('grade'):
            self.opt_grade.set(rec.get('grade'))
        if self.ent_session:
            self.ent_session.delete(0, "end")
            self.ent_session.insert(0, rec.get('session', '2023 - 2024'))
        if self.ent_dob:
            self.ent_dob.delete(0, "end")
            self.ent_dob.insert(0, clean_date_str(rec.get('dob', '')))
        if self.ent_reg:
            self.ent_reg.delete(0, "end")
            self.ent_reg.insert(0, rec.get('reg_no', ''))
        if self.ent_class and rec.get('class_name'):
            self.ent_class.set(rec.get('class_name'))
        if self.ent_stream and rec.get('stream'):
            st = rec.get('stream').strip()
            if 'sci' in st.lower(): self.ent_stream.set("Science")
            elif 'art' in st.lower(): self.ent_stream.set("Arts")
            elif 'com' in st.lower(): self.ent_stream.set("Commerce")
            else: self.ent_stream.set(st)
        if self.ent_section:
            self.ent_section.delete(0, "end")
            self.ent_section.insert(0, rec.get('section', 'A'))
        if self.ent_class_roll:
            self.ent_class_roll.delete(0, "end")
            self.ent_class_roll.insert(0, rec.get('class_roll_no', ''))
        if self.ent_result_date and rec.get('result_date'):
            self.ent_result_date.delete(0, "end")
            self.ent_result_date.insert(0, clean_date_str(rec.get('result_date')))
        if self.ent_left_date and rec.get('left_date'):
            self.ent_left_date.delete(0, "end")
            self.ent_left_date.insert(0, clean_date_str(rec.get('left_date')))
        if self.ent_pen and rec.get('pen_no'):
            self.ent_pen.delete(0, "end")
            self.ent_pen.insert(0, rec.get('pen_no'))
        if self.ent_date and rec.get('issue_date'):
            self.ent_date.delete(0, "end")
            self.ent_date.insert(0, clean_date_str(rec.get('issue_date')))

        # Set Sl. No: use record sl_no if given, or compute using school rule
        sl = rec.get('sl_no', '')
        if ctype in ('provisional', 'character', 'transfer'):
            if not sl or '/' in str(sl) or any(c.isalpha() for c in str(sl)):
                sl = compute_sl_no('provisional', reg_no=rec.get('reg_no', '')) or sl
        elif ctype == 'reading':
            if not sl or (str(sl).isdigit() and len(str(sl)) <= 4):
                sl = compute_sl_no('reading', stream=rec.get('stream', ''),
                                   section=rec.get('section', ''), class_roll=rec.get('class_roll_no', ''))
        if self.ent_sl and sl:
            self.ent_sl.delete(0, "end")
            self.ent_sl.insert(0, str(sl))

        # Update counter & dropdown selector text
        total = len(self.batch_records)
        idx_display = self.current_student_idx + 1 if self.current_student_idx >= 0 else 0
        if hasattr(self, 'lbl_student_counter'):
            self.lbl_student_counter.configure(text=f"{idx_display}/{total}")
        if hasattr(self, 'cmb_students') and 0 <= self.current_student_idx < len(self._student_dropdown_items):
            self.cmb_students.set(self._student_dropdown_items[self.current_student_idx])

        self.update_preview()

    def _search_student(self):
        query = self.ent_student_search.get().strip().lower() if hasattr(self, 'ent_student_search') else ""
        if not query:
            self._reset_student_search()
            return
        if not self.batch_records:
            messagebox.showinfo("No Batch", "Please import an Excel or CSV file in the Batch Processing tab first!")
            return

        matches = []
        for i, r in enumerate(self.batch_records):
            haystack = f"{r.get('student_name', '')} {r.get('roll_no', '')} {r.get('reg_no', '')} {r.get('sl_no', '')}".lower()
            if query in haystack:
                matches.append(i)

        if not matches:
            messagebox.showinfo("Search", f"No student found matching: '{query}'")
            return

        self.filtered_student_indices = matches
        filtered_items = [self._student_dropdown_items[i] for i in matches]
        self.cmb_students.configure(values=filtered_items)
        self.cmb_students.set(filtered_items[0])
        self._load_student_into_studio(matches[0])
        self.status_lbl.configure(text=f"Found {len(matches)} student match(es) for '{query}'", text_color="#059669")

    def _reset_student_search(self):
        if hasattr(self, 'ent_student_search'):
            self.ent_student_search.delete(0, "end")
        self.filtered_student_indices = list(range(len(self.batch_records)))
        if hasattr(self, 'cmb_students'):
            self.cmb_students.configure(values=self._student_dropdown_items if self._student_dropdown_items else ["-- No students loaded --"])
            if self.batch_records and 0 <= self.current_student_idx < len(self._student_dropdown_items):
                self.cmb_students.set(self._student_dropdown_items[self.current_student_idx])

    def _prev_student(self):
        if not self.batch_records:
            return
        active_list = self.filtered_student_indices if self.filtered_student_indices else list(range(len(self.batch_records)))
        if not active_list:
            return
        current_pos = active_list.index(self.current_student_idx) if self.current_student_idx in active_list else 0
        new_pos = (current_pos - 1) % len(active_list)
        self._load_student_into_studio(active_list[new_pos])

    def _next_student(self):
        if not self.batch_records:
            return
        active_list = self.filtered_student_indices if self.filtered_student_indices else list(range(len(self.batch_records)))
        if not active_list:
            return
        current_pos = active_list.index(self.current_student_idx) if self.current_student_idx in active_list else -1
        new_pos = (current_pos + 1) % len(active_list)
        self._load_student_into_studio(active_list[new_pos])

    def _on_student_dropdown_selected(self, val):
        if not self.batch_records or val.startswith("--"):
            return
        import re
        m = re.match(r'^(\d+)\.', val)
        if m:
            idx = int(m.group(1)) - 1
            self._load_student_into_studio(idx)
        else:
            for i, item in enumerate(self._student_dropdown_items):
                if item == val:
                    self._load_student_into_studio(i)
                    break

    def _open_selected_batch_in_studio(self):
        if not self.batch_records:
            messagebox.showwarning("No Data", "Please import an Excel or CSV file first!")
            return
        sel = self.batch_tree.selection()
        idx = 0
        if sel:
            all_children = self.batch_tree.get_children()
            try:
                idx = all_children.index(sel[0])
            except ValueError:
                idx = 0
        self.tabview.set("  📄 Certificate Studio (4 Certificates)  ")
        self._load_student_into_studio(idx)
        name = self.batch_records[idx].get('student_name', 'Student')
        self.status_lbl.configure(text=f"Opened in Studio: {name} (Student {idx+1}/{len(self.batch_records)})", text_color="#059669")

    def print_via_dialog(self):
        """
        Shows the native Windows / Epson printer properties dialog (DocumentProperties).
        Lets the user select paper tray, paper size, quality, etc.
        When user clicks OK, sends print job directly in full color without opening any PDF reader!
        """
        data = self.get_current_form_data()
        selected_types = self.get_selected_cert_types()
        printer_name = self.config.get("printer_name") or get_default_printer()
        mode = self.print_mode_var.get()
        color_mode = self.color_mode_var.get()
        cfg = self.config.copy()
        cfg['strike_unused'] = self.strike_var.get()

        self.status_lbl.configure(text="Opening Printer Properties dialog...", text_color="#0284C7")
        self.update_idletasks()

        # Render PIL images for direct printing
        images = [self.renderer.render_pil(data, mode=mode, cert_type=t, config=cfg) for t in selected_types]

        try:
            success = print_direct(images, printer_name=printer_name, color_mode=color_mode,
                                   show_properties_dialog=True, hwnd=self.winfo_id())
            if not success:
                self.status_lbl.configure(text="Print cancelled in properties dialog.", text_color="#64748B")
                return

            self.status_lbl.configure(text=f"Sent {len(selected_types)} certificate(s) to printer ({color_mode})!", text_color="#059669")

            # Also generate a saved copy in Output_Certificates folder
            out_pdf = os.path.join(get_output_dir(), f"PrintJob_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            self.renderer.render_pdf([data], out_pdf, mode=mode, cert_type=self.current_cert_type, selected_cert_types=selected_types, config=cfg)

            # Sl. No. is identical across Provisional, Character, Transfer (last 3 digits of registration)
            reg = data.get('reg_no', '')
            common_sl = compute_sl_no('provisional', reg_no=reg) or data.get('sl_no', '')

            for t in selected_types:
                rec = data.copy()
                rec['cert_type'] = t
                if t in ('provisional', 'character', 'transfer'):
                    rec['sl_no'] = common_sl
                elif t == 'reading':
                    rec['sl_no'] = data.get('sl_no', '') if self.current_cert_type == 'reading' else compute_sl_no(
                        'reading', stream=data.get('stream', ''), section=data.get('section', ''), class_roll=data.get('class_roll_no', '')
                    )
                save_certificate(rec)
            self._load_records()
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print directly to printer:\n{e}")
            self.status_lbl.configure(text=f"Print error: {e}", text_color="#DC2626")

    def print_current_certificate(self):
        """
        Quick Print Selected.
        Prints directly to the printer in full color without opening any PDF reader!
        If 'Show Printer Properties before printing' is checked, prompts properties dialog first.
        """
        data = self.get_current_form_data()
        selected_types = self.get_selected_cert_types()
        printer_name = self.config.get("printer_name") or get_default_printer()
        mode = self.print_mode_var.get()
        color_mode = self.color_mode_var.get()
        cfg = self.config.copy()
        cfg['strike_unused'] = self.strike_var.get()

        show_props = self.prompt_props_var.get() if hasattr(self, 'prompt_props_var') else False

        self.status_lbl.configure(text="Sending job to printer...", text_color="#059669")
        self.update_idletasks()

        images = [self.renderer.render_pil(data, mode=mode, cert_type=t, config=cfg) for t in selected_types]

        try:
            success = print_direct(images, printer_name=printer_name, color_mode=color_mode,
                                   show_properties_dialog=show_props, hwnd=self.winfo_id())
            if not success and show_props:
                self.status_lbl.configure(text="Print cancelled in properties dialog.", text_color="#64748B")
                return

            self.status_lbl.configure(text=f"Sent {len(selected_types)} certificate(s) to printer ({color_mode})!", text_color="#059669")

            # Also generate a saved copy in Output_Certificates folder
            out_pdf = os.path.join(get_output_dir(), f"PrintJob_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            self.renderer.render_pdf([data], out_pdf, mode=mode, cert_type=self.current_cert_type, selected_cert_types=selected_types, config=cfg)

            # Sl. No. is identical across Provisional, Character, Transfer
            reg = data.get('reg_no', '')
            common_sl = compute_sl_no('provisional', reg_no=reg) or data.get('sl_no', '')

            for t in selected_types:
                rec = data.copy()
                rec['cert_type'] = t
                if t in ('provisional', 'character', 'transfer'):
                    rec['sl_no'] = common_sl
                elif t == 'reading':
                    rec['sl_no'] = data.get('sl_no', '') if self.current_cert_type == 'reading' else compute_sl_no(
                        'reading', stream=data.get('stream', ''), section=data.get('section', ''), class_roll=data.get('class_roll_no', '')
                    )
                save_certificate(rec)
            self._load_records()
        except Exception as e:
            messagebox.showerror("Print Error", f"Failed to print directly to printer:\n{e}")
            self.status_lbl.configure(text=f"Print error: {e}", text_color="#DC2626")

    def _increment_sl(self):
        curr_sl = self.ent_sl.get().strip()
        import re
        match = re.search(r'(\d+)$', curr_sl)
        if match:
            num_str = match.group(1)
            prefix = curr_sl[:match.start()]
            next_num = int(num_str) + 1
            new_sl = f"{prefix}{next_num:0{len(num_str)}d}"
            self.ent_sl.delete(0, "end")
            self.ent_sl.insert(0, new_sl)
            self.config['last_sl_number'] = next_num
            save_config(self.config)
            self.update_preview()

    def save_current_record(self):
        data = self.get_current_form_data()
        selected_types = self.get_selected_cert_types()
        if not data.get('student_name'):
            messagebox.showwarning("Validation", "Student name is required!")
            return

        # Sl. No. is the exact same for all 3 certificates (Provisional, Character, Transfer)
        reg = data.get('reg_no', '')
        common_sl = compute_sl_no('provisional', reg_no=reg) or data.get('sl_no', '')

        saved_list = []
        for t in selected_types:
            rec = data.copy()
            rec['cert_type'] = t
            if t in ('provisional', 'character', 'transfer'):
                rec['sl_no'] = common_sl
            elif t == 'reading':
                rec['sl_no'] = data.get('sl_no', '') if self.current_cert_type == 'reading' else compute_sl_no(
                    'reading', stream=data.get('stream', ''), section=data.get('section', ''), class_roll=data.get('class_roll_no', '')
                )
            save_certificate(rec)
            saved_list.append(t.capitalize())

        self.status_lbl.configure(text=f"Saved {len(selected_types)} certificate(s) to Records", text_color="#059669")
        self._load_records()
        messagebox.showinfo(
            "Records Saved",
            f"Successfully saved {len(selected_types)} certificate(s) for {data['student_name']}!\n\n"
            f"• Certificates: {', '.join(saved_list)}\n"
            f"• Sl. No. (Constant across certificates): {common_sl}\n\n"
            f"All saved certificates are now visible under 'Records & Search' and can be reloaded or reprinted anytime!"
        )

    def reset_form(self):
        if hasattr(self, 'ent_sl') and self.ent_sl: self.ent_sl.delete(0, "end")
        if hasattr(self, 'ent_name') and self.ent_name: self.ent_name.delete(0, "end")
        if hasattr(self, 'ent_father') and self.ent_father: self.ent_father.delete(0, "end")
        if hasattr(self, 'ent_mother') and self.ent_mother: self.ent_mother.delete(0, "end")
        if hasattr(self, 'ent_address') and self.ent_address: self.ent_address.delete(0, "end")
        if hasattr(self, 'ent_year') and self.ent_year: self.ent_year.delete(0, "end")
        if hasattr(self, 'ent_roll') and self.ent_roll: self.ent_roll.delete(0, "end")
        if hasattr(self, 'opt_grade') and self.opt_grade: self.opt_grade.set("")
        if hasattr(self, 'ent_session') and self.ent_session: self.ent_session.delete(0, "end")
        if hasattr(self, 'ent_dob') and self.ent_dob: self.ent_dob.delete(0, "end")
        if hasattr(self, 'ent_reg') and self.ent_reg: self.ent_reg.delete(0, "end")
        if hasattr(self, 'ent_result_date') and self.ent_result_date: self.ent_result_date.delete(0, "end")
        if hasattr(self, 'ent_left_date') and self.ent_left_date: self.ent_left_date.delete(0, "end")
        if hasattr(self, 'ent_pen') and self.ent_pen: self.ent_pen.delete(0, "end")
        if hasattr(self, 'ent_section') and self.ent_section: self.ent_section.delete(0, "end")
        if hasattr(self, 'ent_class_roll') and self.ent_class_roll: self.ent_class_roll.delete(0, "end")
        if hasattr(self, 'ent_date') and self.ent_date:
            self.ent_date.delete(0, "end")
            self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.update_preview()

    # =========================================================================
    # TAB 2: BATCH PROCESSING (EXCEL / CSV)
    # =========================================================================
    def _build_batch_tab(self):
        container = self.tab_batch
        container.grid_rowconfigure(2, weight=1)
        container.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(container, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))

        ctk.CTkButton(
            top_bar,
            text="📂 Browse Excel / CSV File...",
            font=ctk.CTkFont(weight="bold"),
            height=36,
            command=self._browse_batch_file
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            top_bar,
            text="📥 Download Sample Excel Template",
            height=36,
            fg_color=("#475569", "#334155"),
            command=self._generate_template_files
        ).pack(side="left")

        ctk.CTkButton(
            top_bar,
            text="📂 Open Output Folder",
            height=36,
            fg_color="#059669",
            command=open_output_folder
        ).pack(side="left", padx=10)

        self.batch_file_lbl = ctk.CTkLabel(
            top_bar,
            text="No file loaded. Click 'Browse' to import student records.",
            text_color=("#64748B", "#94A3B8"),
            font=ctk.CTkFont(size=12)
        )
        self.batch_file_lbl.pack(side="left", padx=10)

        # Controls & Selective Options
        opts_bar = ctk.CTkFrame(container, fg_color=("#F1F5F9", "#1E293B"), corner_radius=6)
        opts_bar.grid(row=1, column=0, sticky="ew", padx=10, pady=4)

        ctk.CTkLabel(opts_bar, text="Batch Mode:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(10, 4), pady=8)
        self.batch_mode_var = ctk.StringVar(value=self.config.get("print_mode", "full"))
        ctk.CTkSegmentedButton(
            opts_bar,
            values=["full", "overlay"],
            variable=self.batch_mode_var
        ).pack(side="left", padx=(0, 10), pady=8)

        # Batch selective certificates
        ctk.CTkLabel(opts_bar, text="Generate:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(6, 4), pady=8)
        self.batch_sel_prov = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_bar, text="Prov", variable=self.batch_sel_prov, width=55).pack(side="left", pady=8)
        self.batch_sel_char = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_bar, text="Char", variable=self.batch_sel_char, width=55).pack(side="left", pady=8)
        self.batch_sel_trans = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_bar, text="Trans", variable=self.batch_sel_trans, width=55).pack(side="left", pady=8)
        self.batch_sel_read = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_bar, text="Read", variable=self.batch_sel_read, width=55).pack(side="left", padx=(0, 10), pady=8)

        self.single_pdf_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts_bar,
            text="Single Combined PDF (All pages in 1 file)",
            variable=self.single_pdf_var
        ).pack(side="left", padx=(0, 10), pady=8)

        self.btn_run_batch = ctk.CTkButton(
            opts_bar,
            text="🚀 Generate Batch",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._run_batch_generation
        )
        self.btn_run_batch.pack(side="right", padx=(4, 10), pady=8)

        self.btn_open_in_studio = ctk.CTkButton(
            opts_bar,
            text="🎓 Open in Certificate Studio",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=self._open_selected_batch_in_studio
        )
        self.btn_open_in_studio.pack(side="right", padx=4, pady=8)

        # Batch Table
        table_frame = ctk.CTkFrame(container, fg_color="transparent")
        table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ("cert_type", "sl_no", "student_name", "father_name", "mother_name", "exam_name", "roll_no", "grade", "session", "dob", "reg_no", "issue_date")
        self.batch_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.batch_tree.bind("<Double-1>", lambda _: self._open_selected_batch_in_studio())
        
        headers_display = {
            "cert_type": "Certificate",
            "sl_no": "Sl. No.",
            "student_name": "Student Name",
            "father_name": "Father Name",
            "mother_name": "Mother Name",
            "exam_name": "Exam",
            "roll_no": "CBSE Roll No",
            "grade": "Grade",
            "session": "Session",
            "dob": "DOB",
            "reg_no": "Reg No",
            "issue_date": "Date"
        }
        for col in columns:
            self.batch_tree.heading(col, text=headers_display[col])
            w = 110 if col in ("cert_type", "exam_name") else 160 if col == "student_name" else 110 if col in ("father_name", "mother_name", "reg_no") else 80
            self.batch_tree.column(col, width=w, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.batch_tree.yview)
        tree_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.batch_tree.xview)
        self.batch_tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.batch_tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        bottom_bar = ctk.CTkFrame(container, fg_color="transparent")
        bottom_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(4, 8))

        self.batch_progress = ctk.CTkProgressBar(bottom_bar)
        self.batch_progress.set(0)
        self.batch_progress.pack(side="left", fill="x", expand=True, padx=(0, 15))

        self.batch_status_lbl = ctk.CTkLabel(bottom_bar, text="0 records loaded", font=ctk.CTkFont(weight="bold"))
        self.batch_status_lbl.pack(side="right")

    def _browse_batch_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Excel / CSV files", "*.xlsx;*.xls;*.csv"), ("Excel Files", "*.xlsx"), ("CSV Files", "*.csv")],
            title="Select Student Records File"
        )
        if file_path:
            try:
                self.batch_records = read_batch_file(file_path)
                self.batch_filename = os.path.basename(file_path)
                self.batch_file_lbl.configure(text=f"Loaded: {self.batch_filename} ({len(self.batch_records)} students)")
                self.batch_status_lbl.configure(text=f"{len(self.batch_records)} students ready")

                for item in self.batch_tree.get_children():
                    self.batch_tree.delete(item)

                for r in self.batch_records:
                    self.batch_tree.insert("", "end", values=(
                        r.get("cert_type", "").capitalize(),
                        r.get("sl_no", ""),
                        r.get("student_name", ""),
                        r.get("father_name", ""),
                        r.get("mother_name", ""),
                        r.get("exam_name", ""),
                        r.get("roll_no", ""),
                        r.get("grade", ""),
                        r.get("session", ""),
                        r.get("dob", ""),
                        r.get("reg_no", ""),
                        r.get("issue_date", "")
                    ))

                # Automatically reflex loaded batch to Certificate Studio dropdown and form!
                self._sync_batch_to_studio(self.batch_filename)
                messagebox.showinfo(
                    "Batch Loaded & Synced",
                    f"Successfully loaded {len(self.batch_records)} student records from {self.batch_filename}!\n\n"
                    f"• Records are now automatically ready in the Certificate Studio student dropdown list.\n"
                    f"• You can also click 'Open in Certificate Studio' to view or edit them individually!"
                )
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to read file:\n{e}")

    def _generate_template_files(self):
        dest_dir = get_output_dir()
        ex, cs = create_sample_files(dest_dir)
        messagebox.showinfo(
            "Templates Ready",
            f"Sample Excel and CSV templates generated in your Output folder!\n\n"
            f"1. {os.path.basename(ex)}\n"
            f"2. {os.path.basename(cs)}"
        )
        open_output_folder()

    def _run_batch_generation(self):
        if not self.batch_records:
            messagebox.showwarning("No Data", "Please import an Excel or CSV file first!")
            return

        out_dir = get_output_dir()
        mode = self.batch_mode_var.get()
        cfg = self.config.copy()
        total = len(self.batch_records)

        # Selected types for batch
        batch_types = []
        if self.batch_sel_prov.get(): batch_types.append("provisional")
        if self.batch_sel_char.get(): batch_types.append("character")
        if self.batch_sel_trans.get(): batch_types.append("transfer")
        if self.batch_sel_read.get(): batch_types.append("reading")
        if not batch_types:
            batch_types = ["provisional"]

        if self.single_pdf_var.get():
            merged_file = os.path.join(out_dir, f"Batch_Certificates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            self.renderer.render_pdf(
                self.batch_records,
                merged_file,
                mode=mode,
                cert_type="provisional",
                selected_cert_types=batch_types,
                config=cfg
            )
            self.batch_progress.set(1.0)
            
            for r in self.batch_records:
                reg = r.get('reg_no', '')
                common_sl = r.get('sl_no', '')
                if not common_sl or '/' in str(common_sl):
                    common_sl = compute_sl_no('provisional', reg_no=reg)
                for t in batch_types:
                    rec = r.copy()
                    rec['cert_type'] = t
                    for d_k in ('dob', 'result_date', 'left_date', 'issue_date'):
                        if d_k in rec:
                            rec[d_k] = clean_date_str(rec[d_k])
                    if t in ('provisional', 'character', 'transfer'):
                        rec['sl_no'] = common_sl
                    elif t == 'reading':
                        rec['sl_no'] = compute_sl_no('reading', stream=r.get('stream', ''), section=r.get('section', ''), class_roll=r.get('class_roll_no', ''))
                    save_certificate(rec)
            self._load_records()

            confirm = messagebox.askyesno(
                "Batch Complete",
                f"Successfully generated combined PDF with {total * len(batch_types)} certificate pages!\n\n"
                f"Saved to Output folder: {os.path.basename(merged_file)}\n\n"
                f"Would you like to open the PDF now?"
            )
            if confirm:
                open_pdf(merged_file)
        else:
            for i, r in enumerate(self.batch_records):
                s_name = r.get('student_name', f'student_{i+1}').replace(' ', '_')
                r_num = r.get('roll_no', '')
                fname = f"Batch_{r_num}_{s_name}.pdf" if r_num else f"Batch_{s_name}.pdf"
                dest_pdf = os.path.join(out_dir, fname)
                self.renderer.render_pdf(
                    [r],
                    dest_pdf,
                    mode=mode,
                    cert_type="provisional",
                    selected_cert_types=batch_types,
                    config=cfg
                )
                reg = r.get('reg_no', '')
                common_sl = r.get('sl_no', '')
                if not common_sl or '/' in str(common_sl):
                    common_sl = compute_sl_no('provisional', reg_no=reg)
                for t in batch_types:
                    rec = r.copy()
                    rec['cert_type'] = t
                    for d_k in ('dob', 'result_date', 'left_date', 'issue_date'):
                        if d_k in rec:
                            rec[d_k] = clean_date_str(rec[d_k])
                    if t in ('provisional', 'character', 'transfer'):
                        rec['sl_no'] = common_sl
                    elif t == 'reading':
                        rec['sl_no'] = compute_sl_no('reading', stream=r.get('stream', ''), section=r.get('section', ''), class_roll=r.get('class_roll_no', ''))
                    save_certificate(rec)
                self.batch_progress.set((i + 1) / total)
                self.update_idletasks()

            self._load_records()
            messagebox.showinfo("Batch Complete", f"All individual certificate PDFs have been generated in:\n{out_dir}")
            open_output_folder()

    # =========================================================================
    # TAB 3: RECORDS & SEARCH (LOCAL DATABASE)
    # =========================================================================
    def _build_records_tab(self):
        container = self.tab_records
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

        search_bar = ctk.CTkFrame(container, fg_color="transparent")
        search_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 4))

        ctk.CTkLabel(search_bar, text="🔍 Search:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 6))
        self.ent_search = ctk.CTkEntry(search_bar, placeholder_text="Search by Student Name, Roll No, or Serial No...", width=300)
        self.ent_search.pack(side="left", padx=(0, 8))
        self.ent_search.bind("<KeyRelease>", lambda _: self._load_records())

        ctk.CTkLabel(search_bar, text="Filter:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(4, 4))
        self.records_filter_var = ctk.StringVar(value="all")
        ctk.CTkOptionMenu(
            search_bar,
            values=["all", "provisional", "character", "transfer", "reading"],
            variable=self.records_filter_var,
            width=110,
            command=lambda _: self._load_records()
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(search_bar, text="Clear", width=60, fg_color=("#475569", "#334155"), command=self._clear_search).pack(side="left")

        ctk.CTkButton(
            search_bar,
            text="🖨️ Quick Reprint",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self._reprint_selected_record
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            search_bar,
            text="✏️ Load in Studio",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#0284C7",
            command=self._load_selected_to_designer
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            search_bar,
            text="🗑️ Delete",
            fg_color="#DC2626",
            width=75,
            command=self._delete_selected_record
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            search_bar,
            text="📊 Export Excel",
            fg_color=("#059669", "#047857"),
            width=100,
            command=self._export_records_excel
        ).pack(side="right")

        table_frame = ctk.CTkFrame(container, fg_color="transparent")
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ("id", "cert_type", "sl_no", "student_name", "father_name", "mother_name", "exam_name", "roll_no", "grade", "session", "issue_date", "created_at")
        self.records_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        headers_display = {
            "id": "ID",
            "cert_type": "Certificate",
            "sl_no": "Sl. No.",
            "student_name": "Student Name",
            "father_name": "Father Name",
            "mother_name": "Mother Name",
            "exam_name": "Exam",
            "roll_no": "CBSE Roll No",
            "grade": "Grade",
            "session": "Session",
            "issue_date": "Issue Date",
            "created_at": "Saved At"
        }
        for col in columns:
            self.records_tree.heading(col, text=headers_display[col])
            w = 40 if col == "id" else 110 if col in ("cert_type", "exam_name") else 160 if col == "student_name" else 110 if col in ("father_name", "mother_name") else 80
            self.records_tree.column(col, width=w, anchor="center")

        rec_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.records_tree.yview)
        rec_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.records_tree.xview)
        self.records_tree.configure(yscrollcommand=rec_scroll_y.set, xscrollcommand=rec_scroll_x.set)

        self.records_tree.grid(row=0, column=0, sticky="nsew")
        rec_scroll_y.grid(row=0, column=1, sticky="ns")
        rec_scroll_x.grid(row=1, column=0, sticky="ew")

        self.records_tree.bind("<Double-1>", lambda _: self._load_selected_to_designer())

        self.records_count_lbl = ctk.CTkLabel(container, text="0 records in database", font=ctk.CTkFont(size=11), text_color=("#64748B", "#94A3B8"))
        self.records_count_lbl.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 6))

        self._load_records()

    def _clear_search(self):
        self.ent_search.delete(0, "end")
        self.records_filter_var.set("all")
        self._load_records()

    def _load_records(self):
        q = self.ent_search.get().strip() if hasattr(self, 'ent_search') else None
        ctype = self.records_filter_var.get() if hasattr(self, 'records_filter_var') else None
        rows = get_all_certificates(query=q, cert_type=ctype)

        for item in self.records_tree.get_children():
            self.records_tree.delete(item)

        for r in rows:
            self.records_tree.insert("", "end", values=(
                r.get("id"),
                (r.get("cert_type") or "provisional").capitalize(),
                r.get("sl_no"),
                r.get("student_name"),
                r.get("father_name"),
                r.get("mother_name"),
                r.get("exam_name"),
                r.get("roll_no"),
                r.get("grade"),
                r.get("session"),
                r.get("issue_date"),
                r.get("created_at")
            ))

        self.records_count_lbl.configure(text=f"{len(rows)} records in database")

    def _load_selected_to_designer(self):
        selected = self.records_tree.selection()
        if not selected:
            messagebox.showinfo("Select Record", "Please select a record from the table first.")
            return

        values = self.records_tree.item(selected[0], "values")
        if not values:
            return

        rec_id = values[0]
        rec = get_certificate_by_id(rec_id)
        if not rec:
            return

        raw_type = (rec.get('cert_type') or 'provisional').capitalize()
        self.cert_type_seg.set(raw_type)
        self._on_cert_type_change(raw_type)

        if self.ent_sl: self.ent_sl.delete(0, "end"); self.ent_sl.insert(0, rec.get('sl_no', ''))
        if self.ent_name: self.ent_name.delete(0, "end"); self.ent_name.insert(0, to_sentence_case(rec.get('student_name', '')))
        if self.ent_father: self.ent_father.delete(0, "end"); self.ent_father.insert(0, to_sentence_case(rec.get('father_name', '')))
        if self.ent_mother: self.ent_mother.delete(0, "end"); self.ent_mother.insert(0, to_sentence_case(rec.get('mother_name', '')))
        if self.ent_address: self.ent_address.delete(0, "end"); self.ent_address.insert(0, to_sentence_case(rec.get('address', '')))
        if self.ent_year: self.ent_year.delete(0, "end"); self.ent_year.insert(0, rec.get('exam_year', ''))
        if self.ent_roll: self.ent_roll.delete(0, "end"); self.ent_roll.insert(0, rec.get('roll_no', ''))
        if self.opt_grade: self.opt_grade.set(rec.get('grade', ''))
        if self.ent_session: self.ent_session.delete(0, "end"); self.ent_session.insert(0, rec.get('session', ''))
        if self.ent_dob: self.ent_dob.delete(0, "end"); self.ent_dob.insert(0, clean_date_str(rec.get('dob', '')))
        if self.ent_reg: self.ent_reg.delete(0, "end"); self.ent_reg.insert(0, rec.get('reg_no', ''))
        if self.ent_result_date: self.ent_result_date.delete(0, "end"); self.ent_result_date.insert(0, clean_date_str(rec.get('result_date', '')))
        if self.ent_left_date: self.ent_left_date.delete(0, "end"); self.ent_left_date.insert(0, clean_date_str(rec.get('left_date', '')))
        if self.ent_pen: self.ent_pen.delete(0, "end"); self.ent_pen.insert(0, rec.get('pen_no', ''))
        if self.ent_date: self.ent_date.delete(0, "end"); self.ent_date.insert(0, clean_date_str(rec.get('issue_date', datetime.now().strftime("%d/%m/%Y"))))
        if self.ent_class and rec.get('class_name'): self.ent_class.set(rec.get('class_name'))
        if self.ent_stream and rec.get('stream'): self.ent_stream.set(rec.get('stream'))
        if self.ent_section and rec.get('section'): self.ent_section.delete(0, "end"); self.ent_section.insert(0, rec.get('section'))
        if self.ent_class_roll and rec.get('class_roll_no'): self.ent_class_roll.delete(0, "end"); self.ent_class_roll.insert(0, rec.get('class_roll_no'))

        self.tabview.set("  📄 Certificate Studio (4 Certificates)  ")
        self.update_preview()
        self.status_lbl.configure(text=f"Loaded record for {rec.get('student_name')}", text_color="#0284C7")

    def _reprint_selected_record(self):
        selected = self.records_tree.selection()
        if not selected:
            messagebox.showinfo("Select Record", "Please select a record from the table to reprint.")
            return
        self._load_selected_to_designer()
        self.print_via_dialog()

    def _delete_selected_record(self):
        selected = self.records_tree.selection()
        if not selected:
            return
        values = self.records_tree.item(selected[0], "values")
        rec_id = values[0]
        s_name = values[3]

        if messagebox.askyesno("Confirm Delete", f"Delete record #{rec_id} for {s_name}?"):
            delete_certificate(rec_id)
            self._load_records()

    def _export_records_excel(self):
        rows = get_all_certificates()
        if not rows:
            messagebox.showinfo("No Data", "No records found in database to export.")
            return

        save_path = os.path.join(get_output_dir(), f"Mount_Everest_Certificates_{datetime.now().strftime('%Y%m%d')}.xlsx")
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Issued Certificates"

        headers = ["ID", "Certificate", "Sl. No.", "Student Name", "Father Name", "Mother Name", "Address", "Exam", "Year", "Roll No", "Grade", "Session", "DOB", "Reg No", "Result Date", "Left Date", "PEN No", "Issue Date", "Saved At"]
        ws.append(headers)

        for r in rows:
            ws.append([
                r.get("id"), (r.get("cert_type") or "").capitalize(), r.get("sl_no"), r.get("student_name"),
                r.get("father_name"), r.get("mother_name"), r.get("address"), r.get("exam_name"),
                r.get("exam_year"), r.get("roll_no"), r.get("grade"), r.get("session"),
                r.get("dob"), r.get("reg_no"), r.get("result_date"), r.get("left_date"),
                r.get("pen_no"), r.get("issue_date"), r.get("created_at")
            ])

        wb.save(save_path)
        messagebox.showinfo("Export Successful", f"Exported {len(rows)} records to Output Folder:\n{save_path}")
        open_output_folder()

    # =========================================================================
    # TAB 4: CALIBRATION & PRINTER SETTINGS
    # =========================================================================
    def _build_calib_tab(self):
        container = self.tab_calib
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        container.grid_rowconfigure(0, weight=1)

        left_box = ctk.CTkScrollableFrame(container, corner_radius=8)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        ctk.CTkLabel(
            left_box,
            text="Printer Paper Setup & Hardware Integration",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(0, 4))

        printers = get_printers()
        f_pselect = ctk.CTkFrame(left_box, fg_color="transparent")
        f_pselect.pack(fill="x", pady=(2, 6))

        ctk.CTkLabel(f_pselect, text="Target Printer:", width=120, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.printer_dropdown = ctk.CTkOptionMenu(
            f_pselect,
            values=printers if printers else ["No Printers Found"],
            command=self._on_printer_select
        )
        def_p = self.config.get("printer_name") or get_default_printer()
        if def_p in printers:
            self.printer_dropdown.set(def_p)
        self.printer_dropdown.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            left_box,
            text="⚙️ Open Epson / Printer Preferences (Choose Paper Size & Tray)",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self._open_driver_preferences
        ).pack(fill="x", pady=(4, 10))

        # Paper Size Options from Printer Setup
        ctk.CTkLabel(left_box, text="Choose Paper Size from Printer Setup:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(6, 2))
        f_psize_cfg = ctk.CTkFrame(left_box, fg_color="transparent")
        f_psize_cfg.pack(fill="x", pady=(2, 12))

        self.calib_paper_opt = ctk.CTkOptionMenu(
            f_psize_cfg,
            values=["10.5x7.5 (Certificate 10.5\" x 7.5\")", "Auto (Printer Setup)", "A4", "Letter"],
            command=self._on_calib_paper_change
        )
        self.calib_paper_opt.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkButton(
            f_psize_cfg,
            text="🔄 Refresh",
            width=70,
            command=self._refresh_printer_papers
        ).pack(side="left")

        # Output Folder Configuration
        ctk.CTkLabel(
            left_box,
            text="Output Folder for Generated PDFs",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(10, 4))

        f_out = ctk.CTkFrame(left_box, fg_color="transparent")
        f_out.pack(fill="x", pady=(2, 8))

        self.lbl_out_dir = ctk.CTkLabel(f_out, text=get_output_dir(), anchor="w", font=ctk.CTkFont(size=11), text_color=("#1D4ED8", "#60A5FA"))
        self.lbl_out_dir.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(f_out, text="📂 Open", width=70, fg_color="#059669", command=open_output_folder).pack(side="left", padx=4)

        # Offsets
        ctk.CTkLabel(
            left_box,
            text="Physical Printer Calibration (Offsets)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", pady=(10, 4))

        ctk.CTkLabel(
            left_box,
            text="Fine-tune horizontal and vertical text placement in millimeters\nto align with the pre-printed stationery's dotted lines.",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8"),
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(left_box, text="Horizontal Shift (X in mm):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        fx = ctk.CTkFrame(left_box, fg_color="transparent")
        fx.pack(fill="x", pady=(2, 10))

        self.slider_x = ctk.CTkSlider(fx, from_=-20.0, to=20.0, number_of_steps=80, command=self._on_slider_x)
        self.slider_x.set(self.config.get("offset_x_mm", 0.0))
        self.slider_x.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_x_val = ctk.CTkLabel(fx, text=f"{self.config.get('offset_x_mm', 0.0):+.1f} mm", width=65, font=ctk.CTkFont(weight="bold"))
        self.lbl_x_val.pack(side="left", padx=(0, 6))

        ctk.CTkButton(fx, text="0", width=30, command=lambda: self._reset_offset('x')).pack(side="left")

        ctk.CTkLabel(left_box, text="Vertical Shift (Y in mm):", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        fy = ctk.CTkFrame(left_box, fg_color="transparent")
        fy.pack(fill="x", pady=(2, 12))

        self.slider_y = ctk.CTkSlider(fy, from_=-20.0, to=20.0, number_of_steps=80, command=self._on_slider_y)
        self.slider_y.set(self.config.get("offset_y_mm", 0.0))
        self.slider_y.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_y_val = ctk.CTkLabel(fy, text=f"{self.config.get('offset_y_mm', 0.0):+.1f} mm", width=65, font=ctk.CTkFont(weight="bold"))
        self.lbl_y_val.pack(side="left", padx=(0, 6))

        ctk.CTkButton(fy, text="0", width=30, command=lambda: self._reset_offset('y')).pack(side="left")

        ctk.CTkButton(
            left_box,
            text="🎯 Print Calibration Test Sheet",
            font=ctk.CTkFont(weight="bold"),
            height=36,
            fg_color="#D97706",
            hover_color="#B45309",
            command=self._print_calibration_sheet
        ).pack(fill="x", pady=(0, 15))

        # Typography
        ctk.CTkLabel(left_box, text="Typography & Styling", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(10, 6))

        f_fsize = ctk.CTkFrame(left_box, fg_color="transparent")
        f_fsize.pack(fill="x", pady=4)
        ctk.CTkLabel(f_fsize, text="Font Size (pt):", width=130, anchor="w").pack(side="left")
        self.opt_fsize = ctk.CTkOptionMenu(f_fsize, values=["14", "15", "16", "17", "18", "19", "20", "21", "22", "24", "26"], command=self._on_fsize_change)
        self.opt_fsize.set(str(self.config.get("font_size", 22)))
        self.opt_fsize.pack(side="left")

        f_fcol = ctk.CTkFrame(left_box, fg_color="transparent")
        f_fcol.pack(fill="x", pady=4)
        ctk.CTkLabel(f_fcol, text="Ink Color:", width=130, anchor="w").pack(side="left")
        self.opt_fcol = ctk.CTkOptionMenu(
            f_fcol,
            values=["Navy Blue (#001478)", "Classic Black (#111111)", "Dark Royal Blue (#002080)", "Dark Crimson (#800000)"],
            command=self._on_fcol_change
        )
        self.opt_fcol.set("Navy Blue (#001478)")
        self.opt_fcol.pack(side="left")

        f_scol = ctk.CTkFrame(left_box, fg_color="transparent")
        f_scol.pack(fill="x", pady=4)
        ctk.CTkLabel(f_scol, text="Sl. No. Color:", width=130, anchor="w").pack(side="left")
        self.opt_scol = ctk.CTkOptionMenu(
            f_scol,
            values=["Crimson Red (#b40000)", "Navy Blue (#001478)", "Classic Black (#111111)"],
            command=self._on_scol_change
        )
        self.opt_scol.set("Crimson Red (#b40000)")
        self.opt_scol.pack(side="left")

        ctk.CTkButton(
            left_box,
            text="💾 Save Calibration & Settings",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#059669",
            hover_color="#047857",
            command=self._save_settings
        ).pack(fill="x", pady=(20, 10))

        # Right Column
        right_box = ctk.CTkFrame(container, corner_radius=8, fg_color=("#F8FAFC", "#0F172A"))
        right_box.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        ctk.CTkLabel(
            right_box,
            text="How Paper Size from Printer Setup Works",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 6))

        guide_text = (
            "1. Existing Paper Size Set on Printer:\n"
            "   • Click '⚙️ Open Epson / Printer Preferences' to open your printer driver.\n"
            "   • Choose or define any paper size (e.g. 10.5 x 7.5 in, A4, User-Defined).\n"
            "   • In the Paper Size dropdown, select 'Auto (Printer Setup)' to automatically\n"
            "     read and match the active paper size from your Epson L3210 driver!\n\n"
            "2. Selective Certificate Printing (Page 1 to 4):\n"
            "   • In the Studio tab, use the checkboxes to choose which pages to print:\n"
            "     [✓] Page 1: Provisional Certificate\n"
            "     [✓] Page 2: Character Certificate\n"
            "     [✓] Page 3: Transfer Certificate\n"
            "     [✓] Page 4: Reading Certificate\n"
            "   • Click 'Quick Print Selected' or 'Save Selected to PDF' to generate\n"
            "     exactly those certificates in a single merged multi-page job!\n\n"
            "3. Dedicated Output Folder:\n"
            "   • All generated PDFs are automatically saved into:\n"
            "     'd:\\Certificate app\\Output_Certificates\\'\n"
            "   • Click the green '📂 Output Folder' button anytime to view files.\n\n"
            "4. Automatic Current Date:\n"
            "   • The 'Dated, Senapati' issue date is automatically filled with today's date."
        )

        ctk.CTkLabel(
            right_box,
            text=guide_text,
            font=ctk.CTkFont(family="Consolas" if os.name == "nt" else "Courier", size=11),
            justify="left",
            text_color=("#334155", "#CBD5E1")
        ).pack(anchor="w", padx=15, pady=8)

        # Software Updates & Multi-Computer Distribution Box
        upd_box = ctk.CTkFrame(right_box, fg_color=("#E2E8F0", "#1E293B"), corner_radius=6)
        upd_box.pack(fill="x", padx=15, pady=(10, 10))

        ctk.CTkLabel(
            upd_box,
            text=f"📦 Software Updates & Distribution (Current: v{APP_VERSION})",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            upd_box,
            text="Distribute software updates to other school computers via Network Shared Folder,\nUSB drive (.zip), or online without re-installing.",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8"),
            justify="left"
        ).pack(anchor="w", padx=12, pady=(0, 8))

        btn_row_upd = ctk.CTkFrame(upd_box, fg_color="transparent")
        btn_row_upd.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkButton(
            btn_row_upd,
            text="🔄 Check / Manage Updates",
            height=32,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.open_updates_dialog
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row_upd,
            text="📦 Create Update Package (.zip)",
            height=32,
            fg_color="#059669",
            hover_color="#047857",
            command=self._open_create_update_dialog
        ).pack(side="left", padx=(0, 8))

    def _on_calib_paper_change(self, val):
        self._on_paper_size_select(val)

    def _open_driver_preferences(self):
        target = self.config.get("printer_name") or get_default_printer()
        ok = open_printer_preferences(target)
        if not ok:
            messagebox.showinfo("Printer Setup", f"Could not launch preferences for: {target}")

    def _on_slider_x(self, val):
        self.lbl_x_val.configure(text=f"{val:+.1f} mm")
        self.config['offset_x_mm'] = round(val, 2)
        self.update_preview()

    def _on_slider_y(self, val):
        self.lbl_y_val.configure(text=f"{val:+.1f} mm")
        self.config['offset_y_mm'] = round(val, 2)
        self.update_preview()

    def _reset_offset(self, axis):
        if axis == 'x':
            self.slider_x.set(0.0)
            self._on_slider_x(0.0)
        else:
            self.slider_y.set(0.0)
            self._on_slider_y(0.0)

    def _on_fsize_change(self, val):
        self.config['font_size'] = int(val)
        self.update_preview()

    def _on_fcol_change(self, val):
        import re
        m = re.search(r'#([0-9a-fA-F]{6})', val)
        if m:
            self.config['font_color'] = f"#{m.group(1)}"
            self.update_preview()

    def _on_scol_change(self, val):
        import re
        m = re.search(r'#([0-9a-fA-F]{6})', val)
        if m:
            self.config['sl_no_color'] = f"#{m.group(1)}"
            self.update_preview()

    def _on_printer_select(self, val):
        self.config['printer_name'] = val
        self.printer_badge.configure(text=f"🖨️ {val}")
        save_config(self.config)
        self._refresh_printer_papers()

    def _print_calibration_sheet(self):
        cal_path = os.path.join(get_output_dir(), f'Calibration_{self.current_cert_type}.pdf')
        cfg = self.config.copy()
        self.renderer.render_calibration_sheet(cal_path, cert_type=self.current_cert_type, config=cfg)

        printer_name = self.config.get("printer_name") or get_default_printer()
        confirm = messagebox.askyesno(
            "Print Calibration Sheet",
            f"Send calibration grid sheet to:\n\n"
            f"Certificate: {CERT_TYPES[self.current_cert_type]['name']}\n"
            f"Printer: {printer_name or 'Default Printer'}\n\n"
            f"Click 'Yes' to print now, or 'No' to open PDF and view."
        )
        if confirm:
            try:
                print_pdf_file(cal_path, printer_name)
                messagebox.showinfo("Printed", "Calibration test sheet sent to printer!")
            except Exception as e:
                open_pdf(cal_path)
        else:
            open_pdf(cal_path)

    def _save_settings(self):
        save_config(self.config)
        messagebox.showinfo("Settings Saved", "Calibration offsets, paper size, colors, and printer settings saved successfully!")

    # =========================================================================
    # TAB 5: ADMIN ALIGNMENT PORTAL
    # =========================================================================
    def _build_admin_tab(self):
        # Two main frames: Lock Frame (when unauthenticated) & Content Frame (when authenticated)
        self.admin_lock_frame = ctk.CTkFrame(self.tab_admin, fg_color="transparent")
        self.admin_content_frame = ctk.CTkFrame(self.tab_admin, fg_color="transparent")

        self._build_admin_lock_frame()
        self._build_admin_content_frame()

        if self.admin_authenticated:
            self._show_admin_content_screen()
        else:
            self._show_admin_lock_screen()

    # --- ADMIN LOCK / LOGIN SCREEN ---
    def _build_admin_lock_frame(self):
        for w in self.admin_lock_frame.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self.admin_lock_frame, width=440, corner_radius=12, fg_color=("#FFFFFF", "#1E293B"))
        card.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(
            card,
            text="🔒",
            font=ctk.CTkFont(size=44)
        ).pack(pady=(28, 6))

        ctk.CTkLabel(
            card,
            text="Admin Alignment Portal",
            font=ctk.CTkFont(family="Times New Roman", size=20, weight="bold"),
            text_color=("#0F172A", "#F8FAFC")
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            card,
            text="Enter admin password to adjust certificate alignment settings:",
            font=ctk.CTkFont(size=12),
            text_color=("#64748B", "#94A3B8")
        ).pack(padx=20, pady=(0, 16))

        self.ent_admin_pw = ctk.CTkEntry(
            card,
            placeholder_text="Enter Admin Password",
            show="*",
            width=280,
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.ent_admin_pw.pack(padx=30, pady=(0, 6))
        self.ent_admin_pw.bind("<Return>", lambda e: self._attempt_admin_unlock())

        self.lbl_admin_err = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#EF4444"
        )
        self.lbl_admin_err.pack(pady=(0, 8))

        ctk.CTkButton(
            card,
            text="Unlock Admin Portal 🔓",
            width=280,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#D97706",
            hover_color="#B45309",
            command=self._attempt_admin_unlock
        ).pack(padx=30, pady=(0, 14))

        ctk.CTkLabel(
            card,
            text="Default Password: 1234 (You can change it inside the portal)",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color=("#94A3B8", "#64748B")
        ).pack(pady=(0, 22))

    def _attempt_admin_unlock(self):
        entered = self.ent_admin_pw.get().strip()
        actual = str(self.config.get('admin_password', '1234')).strip()
        if entered == actual:
            self.admin_authenticated = True
            self.lbl_admin_err.configure(text="")
            self.ent_admin_pw.delete(0, "end")
            self._show_admin_content_screen()
        else:
            self.lbl_admin_err.configure(text="❌ Incorrect password. Please try again.")
            self.ent_admin_pw.delete(0, "end")
            self.ent_admin_pw.focus_set()

    def _show_admin_lock_screen(self):
        self.admin_content_frame.pack_forget()
        self.admin_lock_frame.pack(fill="both", expand=True)
        if hasattr(self, 'ent_admin_pw'):
            self.ent_admin_pw.delete(0, "end")
            self.ent_admin_pw.focus_set()

    def _show_admin_content_screen(self):
        self.admin_lock_frame.pack_forget()
        self.admin_content_frame.pack(fill="both", expand=True)
        self._sync_admin_field_controls()
        self._update_admin_preview()

    def _lock_admin_portal(self):
        self.admin_authenticated = False
        self._show_admin_lock_screen()

    # --- ADMIN CONTENT / CONTROLS SCREEN ---
    def _build_admin_content_frame(self):
        container = self.admin_content_frame

        # Left pane: Controls & Tuning (Width 510)
        left_pane = ctk.CTkFrame(container, width=510, corner_radius=8)
        left_pane.pack(side="left", fill="y", padx=(6, 6), pady=6)
        left_pane.pack_propagate(False)

        # Right pane: Visual Preview
        right_pane = ctk.CTkFrame(container, corner_radius=8)
        right_pane.pack(side="right", fill="both", expand=True, padx=(6, 6), pady=6)

        # --- LEFT PANE CONTENT ---
        # 1. Header Card with Title and Actions (Change PW, Lock)
        hdr_frame = ctk.CTkFrame(left_pane, fg_color=("#E2E8F0", "#1E293B"), corner_radius=6)
        hdr_frame.pack(fill="x", padx=10, pady=(10, 8))

        hdr_top = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        hdr_top.pack(fill="x", padx=10, pady=(6, 2))

        ctk.CTkLabel(
            hdr_top,
            text="🛠️ Admin Alignment Portal",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#0F172A", "#F8FAFC")
        ).pack(side="left")

        # Top Right Actions: Change Password & Lock
        hdr_btns = ctk.CTkFrame(hdr_top, fg_color="transparent")
        hdr_btns.pack(side="right")

        ctk.CTkButton(
            hdr_btns,
            text="🔑 Password",
            font=ctk.CTkFont(size=10),
            width=76,
            height=24,
            fg_color="#475569",
            hover_color="#334155",
            command=self._open_change_password_dialog
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            hdr_btns,
            text="🔒 Lock",
            font=ctk.CTkFont(size=10),
            width=54,
            height=24,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=self._lock_admin_portal
        ).pack(side="left", padx=2)

        ctk.CTkLabel(
            hdr_frame,
            text="Fine-tune text field positions (X, Y) to align perfectly with your stationery.",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8")
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Scrollable controls frame for left pane
        ctrl_scroll = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        ctrl_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # 2. Certificate Type Selector
        cert_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        cert_sec.pack(fill="x", pady=4)
        ctk.CTkLabel(cert_sec, text="1. SELECT CERTIFICATE TO CALIBRATE", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 4))

        self.admin_cert_seg = ctk.CTkSegmentedButton(
            cert_sec,
            values=["Provisional", "Character", "Transfer", "Reading"],
            command=self._on_admin_cert_change
        )
        self.admin_cert_seg.set("Reading")
        self.admin_cert_seg.pack(fill="x", padx=10, pady=(2, 8))

        # 3. Active Field Selector
        field_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        field_sec.pack(fill="x", pady=4)
        ctk.CTkLabel(field_sec, text="2. SELECT FIELD TO ADJUST", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 2))

        self.admin_field_var = ctk.StringVar()
        self.admin_field_menu = ctk.CTkOptionMenu(
            field_sec,
            variable=self.admin_field_var,
            command=self._on_admin_field_change,
            height=32
        )
        self.admin_field_menu.pack(fill="x", padx=10, pady=(2, 6))

        # Shortcut hint
        ctk.CTkLabel(
            field_sec,
            text="💡 Tip: Arrow keys (← ↑ → ↓) on keyboard nudge the active field live!",
            font=ctk.CTkFont(size=10, slant="italic"),
            text_color="#0284C7"
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # 4. Precision Coordinate Adjuster
        coord_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        coord_sec.pack(fill="x", pady=4)
        ctk.CTkLabel(coord_sec, text="3. PRECISION POSITIONING (PIXELS on 3000x2250)", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 4))

        # --- X Coordinate ---
        x_hdr = ctk.CTkFrame(coord_sec, fg_color="transparent")
        x_hdr.pack(fill="x", padx=10, pady=(4, 2))
        ctk.CTkLabel(x_hdr, text="Horizontal (X Position):", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.admin_x_lbl = ctk.CTkLabel(x_hdr, text="X = 0", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color="#D97706")
        self.admin_x_lbl.pack(side="right")

        x_btns_frame = ctk.CTkFrame(coord_sec, fg_color="transparent")
        x_btns_frame.pack(fill="x", padx=10, pady=2)

        self.admin_entry_x = ctk.CTkEntry(x_btns_frame, width=70, font=ctk.CTkFont(family="Consolas", size=12))
        self.admin_entry_x.pack(side="left", padx=(0, 4))
        self.admin_entry_x.bind("<Return>", self._on_admin_entry_x_commit)
        self.admin_entry_x.bind("<FocusOut>", self._on_admin_entry_x_commit)

        for delta, label in [(-50, "-50"), (-10, "-10"), (-1, "-1"), (+1, "+1"), (+10, "+10"), (+50, "+50")]:
            ctk.CTkButton(
                x_btns_frame,
                text=label,
                width=36,
                height=26,
                font=ctk.CTkFont(size=10),
                command=lambda d=delta: self._nudge_admin_field(d, 0)
            ).pack(side="left", padx=1)

        self.admin_slider_x = ctk.CTkSlider(
            coord_sec,
            from_=0,
            to=IMG_W,
            number_of_steps=int(IMG_W),
            command=self._on_admin_slider_x
        )
        self.admin_slider_x.pack(fill="x", padx=10, pady=(2, 8))

        # --- Y Coordinate ---
        y_hdr = ctk.CTkFrame(coord_sec, fg_color="transparent")
        y_hdr.pack(fill="x", padx=10, pady=(4, 2))
        ctk.CTkLabel(y_hdr, text="Vertical Baseline (Y Position):", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.admin_y_lbl = ctk.CTkLabel(y_hdr, text="Y = 0", font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color="#059669")
        self.admin_y_lbl.pack(side="right")

        y_btns_frame = ctk.CTkFrame(coord_sec, fg_color="transparent")
        y_btns_frame.pack(fill="x", padx=10, pady=2)

        self.admin_entry_y = ctk.CTkEntry(y_btns_frame, width=70, font=ctk.CTkFont(family="Consolas", size=12))
        self.admin_entry_y.pack(side="left", padx=(0, 4))
        self.admin_entry_y.bind("<Return>", self._on_admin_entry_y_commit)
        self.admin_entry_y.bind("<FocusOut>", self._on_admin_entry_y_commit)

        for delta, label in [(-50, "-50"), (-10, "-10"), (-1, "-1"), (+1, "+1"), (+10, "+10"), (+50, "+50")]:
            ctk.CTkButton(
                y_btns_frame,
                text=label,
                width=36,
                height=26,
                font=ctk.CTkFont(size=10),
                command=lambda d=delta: self._nudge_admin_field(0, d)
            ).pack(side="left", padx=1)

        self.admin_slider_y = ctk.CTkSlider(
            coord_sec,
            from_=0,
            to=IMG_H,
            number_of_steps=int(IMG_H),
            command=self._on_admin_slider_y
        )
        self.admin_slider_y.pack(fill="x", padx=10, pady=(2, 8))

        # 5. D-PAD NUDGE CONTROLLER
        dpad_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        dpad_sec.pack(fill="x", pady=4)
        dpad_hdr = ctk.CTkFrame(dpad_sec, fg_color="transparent")
        dpad_hdr.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(dpad_hdr, text="4. DIRECTIONAL NUDGE", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")

        step_box = ctk.CTkFrame(dpad_hdr, fg_color="transparent")
        step_box.pack(side="right")
        ctk.CTkLabel(step_box, text="Step:", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 4))
        self.admin_step_seg = ctk.CTkSegmentedButton(
            step_box,
            values=["1px", "5px", "10px", "25px"],
            command=self._on_admin_step_change,
            height=22,
            font=ctk.CTkFont(size=10)
        )
        self.admin_step_seg.set("5px")
        self.admin_step_seg.pack(side="left")

        dpad_grid = ctk.CTkFrame(dpad_sec, fg_color="transparent")
        dpad_grid.pack(pady=6)

        ctk.CTkButton(
            dpad_grid, text="▲ Up", width=70, height=28,
            command=lambda: self._nudge_by_step(0, -1)
        ).grid(row=0, column=1, padx=4, pady=2)

        ctk.CTkButton(
            dpad_grid, text="◀ Left", width=70, height=28,
            command=lambda: self._nudge_by_step(-1, 0)
        ).grid(row=1, column=0, padx=4, pady=2)

        self.admin_active_badge = ctk.CTkLabel(
            dpad_grid, text="🎯", font=ctk.CTkFont(size=14)
        )
        self.admin_active_badge.grid(row=1, column=1, padx=4, pady=2)

        ctk.CTkButton(
            dpad_grid, text="Right ▶", width=70, height=28,
            command=lambda: self._nudge_by_step(1, 0)
        ).grid(row=1, column=2, padx=4, pady=2)

        ctk.CTkButton(
            dpad_grid, text="▼ Down", width=70, height=28,
            command=lambda: self._nudge_by_step(0, 1)
        ).grid(row=2, column=1, padx=4, pady=2)

        # 6. Action Buttons Bar
        act_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        act_sec.pack(fill="x", pady=6)

        cur_cert_name = CERT_TYPES.get(self.admin_cert_type, {}).get('name', 'Reading Certificate')

        # Button 1: Save CURRENT certificate alignment
        self.btn_save_single_cert = ctk.CTkButton(
            act_sec,
            text=f"💾 Save {cur_cert_name} Alignment",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            height=34,
            command=self._save_current_cert_positions
        )
        self.btn_save_single_cert.pack(fill="x", padx=10, pady=(8, 3))

        # Button 2: Save ALL certificates alignments
        ctk.CTkButton(
            act_sec,
            text="💾 Save All 4 Certificates Alignments",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0D9488",
            hover_color="#0F766E",
            height=30,
            command=self._save_admin_positions
        ).pack(fill="x", padx=10, pady=(2, 6))

        act_row2 = ctk.CTkFrame(act_sec, fg_color="transparent")
        act_row2.pack(fill="x", padx=10, pady=4)

        ctk.CTkButton(
            act_row2,
            text="🔄 Reset Cert Default",
            font=ctk.CTkFont(size=11),
            fg_color="#D97706",
            hover_color="#B45309",
            height=28,
            command=self._reset_admin_cert_positions
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            act_row2,
            text="⏪ Reset All 4 Certs",
            font=ctk.CTkFont(size=11),
            fg_color="#475569",
            hover_color="#334155",
            height=28,
            command=self._reset_admin_all_positions
        ).pack(side="right", fill="x", expand=True, padx=(4, 0))

        act_row3 = ctk.CTkFrame(act_sec, fg_color="transparent")
        act_row3.pack(fill="x", padx=10, pady=(4, 8))

        ctk.CTkButton(
            act_row3,
            text="🖨️ Test Print (Overlay)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=30,
            command=lambda: self._admin_test_print(mode="overlay")
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkButton(
            act_row3,
            text="📄 Test Print (Full)",
            font=ctk.CTkFont(size=11),
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            height=30,
            command=lambda: self._admin_test_print(mode="full")
        ).pack(side="right", fill="x", expand=True, padx=(4, 0))

        # 7. All Fields Overview Table
        overview_sec = ctk.CTkFrame(ctrl_scroll, corner_radius=6)
        overview_sec.pack(fill="x", pady=4)
        ctk.CTkLabel(overview_sec, text="5. ALL FIELDS FOR THIS CERTIFICATE", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=10, pady=(6, 4))

        self.admin_fields_table = ctk.CTkFrame(overview_sec, fg_color="transparent")
        self.admin_fields_table.pack(fill="x", padx=6, pady=(0, 8))

        # --- RIGHT PANE CONTENT (VISUAL STUDIO PREVIEW) ---
        # Preview toolbar
        prev_bar = ctk.CTkFrame(right_pane, height=44, corner_radius=6)
        prev_bar.pack(fill="x", padx=8, pady=(8, 4))

        # Mode toggle
        self.admin_mode_seg = ctk.CTkSegmentedButton(
            prev_bar,
            values=["Full Template", "Overlay (White)"],
            command=self._on_admin_mode_change,
            height=28
        )
        self.admin_mode_seg.set("Full Template")
        self.admin_mode_seg.pack(side="left", padx=8)

        # Crosshair guide toggle
        ctk.CTkCheckBox(
            prev_bar,
            text="Show Guides & Crosshairs",
            variable=self.admin_show_crosshairs,
            command=self._update_admin_preview,
            font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=10)

        # Active field status badge
        self.admin_status_badge = ctk.CTkLabel(
            prev_bar,
            text="Selected: Class Roll Number (X: 2410, Y: 1444)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=("#E0F2FE", "#0C4A6E"),
            text_color=("#0284C7", "#38BDF8"),
            corner_radius=4,
            padx=10,
            pady=2
        )
        self.admin_status_badge.pack(side="left", padx=10)

        # Zoom controls
        zoom_frame = ctk.CTkFrame(prev_bar, fg_color="transparent")
        zoom_frame.pack(side="right", padx=8)

        ctk.CTkButton(zoom_frame, text="🔍 -", width=36, height=28, command=self._admin_zoom_out).pack(side="left", padx=2)
        self.admin_zoom_lbl = ctk.CTkLabel(zoom_frame, text="70%", width=40, font=ctk.CTkFont(size=11))
        self.admin_zoom_lbl.pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="🔍 +", width=36, height=28, command=self._admin_zoom_in).pack(side="left", padx=2)
        ctk.CTkButton(zoom_frame, text="Fit", width=42, height=28, command=self._admin_zoom_fit).pack(side="left", padx=2)

        # Scrollable Canvas
        canvas_container = ctk.CTkFrame(right_pane, corner_radius=6)
        canvas_container.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.admin_canvas = tk.Canvas(
            canvas_container,
            bg="#222222" if ctk.get_appearance_mode() == "Dark" else "#E2E8F0",
            highlightthickness=0
        )
        v_bar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.admin_canvas.yview)
        h_bar = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.admin_canvas.xview)
        self.admin_canvas.configure(xscrollcommand=h_bar.set, yscrollcommand=v_bar.set)

        v_bar.pack(side="right", fill="y")
        h_bar.pack(side="bottom", fill="x")
        self.admin_canvas.pack(side="left", fill="both", expand=True)

        # Canvas event bindings for interactive clicking & dragging
        self.admin_canvas.bind("<ButtonPress-1>", self._on_admin_canvas_click)
        self.admin_canvas.bind("<B1-Motion>", self._on_admin_canvas_drag)

        # Initialize field menu & table
        self._populate_admin_fields()

    # --- ADMIN PASSWORD CHANGE DIALOG ---
    def _open_change_password_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Change Admin Password")
        dialog.geometry("400x340")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="🔑 Change Admin Password",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            dialog,
            text="Enter your current password and set a new password:",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8")
        ).pack(pady=(0, 16))

        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(padx=30, fill="x")

        ctk.CTkLabel(form, text="Current Password:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ent_curr = ctk.CTkEntry(form, show="*", height=32)
        ent_curr.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(form, text="New Password:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ent_new = ctk.CTkEntry(form, show="*", height=32)
        ent_new.pack(fill="x", pady=(2, 8))

        ctk.CTkLabel(form, text="Confirm New Password:", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
        ent_conf = ctk.CTkEntry(form, show="*", height=32)
        ent_conf.pack(fill="x", pady=(2, 12))

        lbl_status = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=11))
        lbl_status.pack(pady=(0, 8))

        def save_pw():
            c_pw = ent_curr.get().strip()
            n_pw = ent_new.get().strip()
            cf_pw = ent_conf.get().strip()

            actual_pw = str(self.config.get('admin_password', '1234')).strip()
            if c_pw != actual_pw:
                lbl_status.configure(text="❌ Current password is incorrect.", text_color="#EF4444")
                return
            if not n_pw:
                lbl_status.configure(text="❌ New password cannot be empty.", text_color="#EF4444")
                return
            if n_pw != cf_pw:
                lbl_status.configure(text="❌ New passwords do not match.", text_color="#EF4444")
                return

            self.config['admin_password'] = n_pw
            save_config(self.config)
            messagebox.showinfo("Password Changed", "✅ Admin password has been updated successfully!", parent=dialog)
            dialog.destroy()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=30, pady=(0, 16))

        ctk.CTkButton(btn_row, text="Update Password", fg_color="#059669", hover_color="#047857", command=save_pw).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(btn_row, text="Cancel", fg_color="#64748B", hover_color="#475569", command=dialog.destroy).pack(side="right", fill="x", expand=True, padx=(4, 0))

    # --- ADMIN PORTAL HELPER METHODS ---
    def _on_admin_cert_change(self, val):
        self.admin_cert_type = val.lower()
        cert_name = CERT_TYPES.get(self.admin_cert_type, {}).get('name', val)
        if hasattr(self, 'btn_save_single_cert'):
            self.btn_save_single_cert.configure(text=f"💾 Save {cert_name} Alignment")
        self._populate_admin_fields()
        self._update_admin_preview()

    def _on_admin_mode_change(self, val):
        self.admin_mode = "full" if "Full" in val else "overlay"
        self._update_admin_preview()

    def _on_admin_step_change(self, val):
        try:
            self.admin_step_val = int(str(val).replace("px", "").strip())
        except Exception:
            self.admin_step_val = 5

    def _populate_admin_fields(self):
        cert_k = self.admin_cert_type
        meta_list = FIELD_METADATA.get(cert_k, [])
        options = [label for _, label, _ in meta_list]
        self.admin_field_menu.configure(values=options)

        # If current active field not in this cert, pick first
        valid_keys = [k for k, _, _ in meta_list]
        if self.admin_selected_field not in valid_keys and valid_keys:
            self.admin_selected_field = valid_keys[0]

        # Set dropdown value
        for k, label, _ in meta_list:
            if k == self.admin_selected_field:
                self.admin_field_var.set(label)
                break

        self._sync_admin_field_controls()

    def _on_admin_field_change(self, val):
        cert_k = self.admin_cert_type
        for k, label, _ in FIELD_METADATA.get(cert_k, []):
            if label == val:
                self.admin_selected_field = k
                break
        self._sync_admin_field_controls()
        self._update_admin_preview()

    def _select_admin_field_by_key(self, f_key, f_label):
        self.admin_selected_field = f_key
        self.admin_field_var.set(f_label)
        self._sync_admin_field_controls()
        self._update_admin_preview()

    def _sync_admin_field_controls(self):
        cert_k = self.admin_cert_type
        f_key = self.admin_selected_field
        if not f_key or cert_k not in self.admin_positions or f_key not in self.admin_positions[cert_k]:
            return

        coords = self.admin_positions[cert_k][f_key]
        if len(coords) != 2:
            return
        x, y = coords

        self.admin_x_lbl.configure(text=f"X = {x}")
        self.admin_y_lbl.configure(text=f"Y = {y}")

        self.admin_entry_x.delete(0, "end")
        self.admin_entry_x.insert(0, str(x))

        self.admin_entry_y.delete(0, "end")
        self.admin_entry_y.insert(0, str(y))

        self.admin_slider_x.set(x)
        self.admin_slider_y.set(y)

        # Update status badge
        disp_label = f_key
        for k, lbl, _ in FIELD_METADATA.get(cert_k, []):
            if k == f_key:
                disp_label = lbl
                break
        self.admin_status_badge.configure(text=f"Selected: {disp_label} (X: {x}, Y: {y})")

        # Refresh the table display
        self._refresh_admin_fields_table()

    def _refresh_admin_fields_table(self):
        for w in self.admin_fields_table.winfo_children():
            w.destroy()

        cert_k = self.admin_cert_type
        meta_list = FIELD_METADATA.get(cert_k, [])
        pos_dict = self.admin_positions.get(cert_k, {})

        for f_key, f_label, _ in meta_list:
            coords = pos_dict.get(f_key, (0, 0))
            is_active = (f_key == self.admin_selected_field)

            row = ctk.CTkFrame(
                self.admin_fields_table,
                fg_color=("#DBEAFE", "#1E3A8A") if is_active else ("#F8FAFC", "#1E293B"),
                corner_radius=4,
                height=30
            )
            row.pack(fill="x", pady=2)

            btn = ctk.CTkButton(
                row,
                text=f"{f_label}",
                font=ctk.CTkFont(size=11, weight="bold" if is_active else "normal"),
                fg_color="transparent",
                text_color=("#1E40AF", "#93C5FD") if is_active else ("#334155", "#CBD5E1"),
                hover_color=("#BFDBFE", "#1E40AF"),
                anchor="w",
                command=lambda k=f_key, l=f_label: self._select_admin_field_by_key(k, l)
            )
            btn.pack(side="left", fill="x", expand=True, padx=4)

            coord_str = f"X:{coords[0]}  Y:{coords[1]}"
            ctk.CTkLabel(
                row,
                text=coord_str,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                text_color="#D97706" if is_active else ("#64748B", "#94A3B8"),
                padx=6
            ).pack(side="right")

    def _nudge_by_step(self, dx_sign, dy_sign):
        step = getattr(self, 'admin_step_val', 5)
        self._nudge_admin_field(dx_sign * step, dy_sign * step)

    def _nudge_admin_field(self, dx, dy):
        cert_k = self.admin_cert_type
        f_key = self.admin_selected_field
        if not f_key or cert_k not in self.admin_positions or f_key not in self.admin_positions[cert_k]:
            return

        cur_x, cur_y = self.admin_positions[cert_k][f_key]
        new_x = int(round(max(0, min(IMG_W, cur_x + dx))))
        new_y = int(round(max(0, min(IMG_H, cur_y + dy))))

        self.admin_positions[cert_k][f_key] = (new_x, new_y)
        self._sync_admin_field_controls()
        self._update_admin_preview()

    def _on_admin_slider_x(self, val):
        cert_k = self.admin_cert_type
        f_key = self.admin_selected_field
        if not f_key or cert_k not in self.admin_positions or f_key not in self.admin_positions[cert_k]:
            return
        new_x = int(round(val))
        cur_y = self.admin_positions[cert_k][f_key][1]
        self.admin_positions[cert_k][f_key] = (new_x, cur_y)
        self.admin_x_lbl.configure(text=f"X = {new_x}")
        self.admin_entry_x.delete(0, "end")
        self.admin_entry_x.insert(0, str(new_x))
        self._update_admin_preview()

    def _on_admin_slider_y(self, val):
        cert_k = self.admin_cert_type
        f_key = self.admin_selected_field
        if not f_key or cert_k not in self.admin_positions or f_key not in self.admin_positions[cert_k]:
            return
        new_y = int(round(val))
        cur_x = self.admin_positions[cert_k][f_key][0]
        self.admin_positions[cert_k][f_key] = (cur_x, new_y)
        self.admin_y_lbl.configure(text=f"Y = {new_y}")
        self.admin_entry_y.delete(0, "end")
        self.admin_entry_y.insert(0, str(new_y))
        self._update_admin_preview()

    def _on_admin_entry_x_commit(self, event=None):
        try:
            val = int(self.admin_entry_x.get().strip())
            new_x = max(0, min(int(IMG_W), val))
            cert_k = self.admin_cert_type
            f_key = self.admin_selected_field
            if f_key in self.admin_positions[cert_k]:
                cur_y = self.admin_positions[cert_k][f_key][1]
                self.admin_positions[cert_k][f_key] = (new_x, cur_y)
                self.admin_slider_x.set(new_x)
                self.admin_x_lbl.configure(text=f"X = {new_x}")
                self._update_admin_preview()
        except Exception:
            pass

    def _on_admin_entry_y_commit(self, event=None):
        try:
            val = int(self.admin_entry_y.get().strip())
            new_y = max(0, min(int(IMG_H), val))
            cert_k = self.admin_cert_type
            f_key = self.admin_selected_field
            if f_key in self.admin_positions[cert_k]:
                cur_x = self.admin_positions[cert_k][f_key][0]
                self.admin_positions[cert_k][f_key] = (cur_x, new_y)
                self.admin_slider_y.set(new_y)
                self.admin_y_lbl.configure(text=f"Y = {new_y}")
                self._update_admin_preview()
        except Exception:
            pass

    def _on_admin_key_nudge(self, dx_sign, dy_sign, event):
        # Only nudge if Admin Portal tab is currently active and authenticated
        try:
            if "Admin Alignment" not in self.tabview.get() or not self.admin_authenticated:
                return
        except Exception:
            return

        # Don't intercept if user is typing inside an entry box
        focused = self.focus_get()
        if focused and isinstance(focused, (tk.Entry, ttk.Entry, ctk.CTkEntry)):
            return

        # Shift key multiplies step by 5x
        multiplier = (self.admin_step_val * 5) if (event.state & 0x0001) else self.admin_step_val
        self._nudge_admin_field(dx_sign * multiplier, dy_sign * multiplier)

    def _on_admin_canvas_click(self, event):
        disp_w = int(IMG_W * self.admin_zoom)
        disp_h = int(IMG_H * self.admin_zoom)
        if disp_w <= 0 or disp_h <= 0:
            return

        cx = self.admin_canvas.canvasx(event.x)
        cy = self.admin_canvas.canvasy(event.y)

        click_img_x = (cx / disp_w) * IMG_W
        click_img_y = (cy / disp_h) * IMG_H

        cert_k = self.admin_cert_type
        cert_positions = self.admin_positions.get(cert_k, {})
        closest_field = None
        min_dist = float("inf")

        for f_key, coords in cert_positions.items():
            if len(coords) == 2:
                fx, fy = coords
                dist = (click_img_x - fx)**2 + (click_img_y - fy)**2
                if dist < min_dist:
                    min_dist = dist
                    closest_field = f_key

        if closest_field and min_dist < (350 ** 2):
            self.admin_selected_field = closest_field
            for k, label, _ in FIELD_METADATA.get(cert_k, []):
                if k == closest_field:
                    self.admin_field_var.set(label)
                    break
            self._sync_admin_field_controls()
            self._update_admin_preview()

        cur_coords = cert_positions.get(self.admin_selected_field, (0, 0))
        self._admin_drag_data = {
            "start_x": cx,
            "start_y": cy,
            "field_start_x": cur_coords[0],
            "field_start_y": cur_coords[1]
        }

    def _on_admin_canvas_drag(self, event):
        if not self.admin_selected_field:
            return
        disp_w = int(IMG_W * self.admin_zoom)
        disp_h = int(IMG_H * self.admin_zoom)
        if disp_w <= 0 or disp_h <= 0:
            return

        cx = self.admin_canvas.canvasx(event.x)
        cy = self.admin_canvas.canvasy(event.y)

        delta_canvas_x = cx - self._admin_drag_data["start_x"]
        delta_canvas_y = cy - self._admin_drag_data["start_y"]

        delta_img_x = (delta_canvas_x / disp_w) * IMG_W
        delta_img_y = (delta_canvas_y / disp_h) * IMG_H

        new_x = int(round(max(0, min(IMG_W, self._admin_drag_data["field_start_x"] + delta_img_x))))
        new_y = int(round(max(0, min(IMG_H, self._admin_drag_data["field_start_y"] + delta_img_y))))

        cert_k = self.admin_cert_type
        if cert_k in self.admin_positions and self.admin_selected_field in self.admin_positions[cert_k]:
            self.admin_positions[cert_k][self.admin_selected_field] = (new_x, new_y)
            self._sync_admin_field_controls()
            self._update_admin_preview()

    def _update_admin_preview(self):
        try:
            if not self.admin_authenticated:
                return
            cert_k = self.admin_cert_type
            dummy_data = ADMIN_SAMPLE_DATA.get(cert_k, {})
            cfg = self.config.copy()

            pil_img = self.renderer.render_pil(
                dummy_data,
                mode=self.admin_mode,
                cert_type=cert_k,
                config=cfg,
                highlight_field=self.admin_selected_field,
                show_crosshairs=self.admin_show_crosshairs.get(),
                custom_positions_override=self.admin_positions
            )

            target_w = int(pil_img.width * self.admin_zoom)
            target_h = int(pil_img.height * self.admin_zoom)
            resized = pil_img.resize((target_w, target_h), Image.Resampling.BILINEAR)

            self.admin_preview_image_tk = ImageTk.PhotoImage(resized)
            self.admin_canvas.delete("all")
            self.admin_canvas.create_image(0, 0, anchor="nw", image=self.admin_preview_image_tk)
            self.admin_canvas.config(scrollregion=(0, 0, target_w, target_h))
        except Exception as e:
            print(f"Error in _update_admin_preview: {e}")

    def _admin_zoom_in(self):
        self.admin_zoom = min(1.5, self.admin_zoom + 0.1)
        self.admin_zoom_lbl.configure(text=f"{int(self.admin_zoom * 100)}%")
        self._update_admin_preview()

    def _admin_zoom_out(self):
        self.admin_zoom = max(0.3, self.admin_zoom - 0.1)
        self.admin_zoom_lbl.configure(text=f"{int(self.admin_zoom * 100)}%")
        self._update_admin_preview()

    def _admin_zoom_fit(self):
        self.admin_zoom = 0.70
        self.admin_zoom_lbl.configure(text=f"{int(self.admin_zoom * 100)}%")
        self._update_admin_preview()

    # --- SAVE OPTIONS ---
    def _save_current_cert_positions(self):
        """Saves alignment positions specifically for the currently active certificate."""
        cert_k = self.admin_cert_type
        cert_name = CERT_TYPES.get(cert_k, {}).get('name', cert_k)
        cert_coords = self.admin_positions.get(cert_k, {})

        success = save_certificate_position(cert_k, cert_coords)
        if success:
            self.renderer.reload_positions()
            self.update_preview()
            self._update_admin_preview()
            messagebox.showinfo(
                "Certificate Alignment Saved",
                f"✅ Alignment adjustments for '{cert_name}' have been saved successfully!\n\n"
                f"This certificate's customized coordinates are now active for printing and PDF generation."
            )
        else:
            messagebox.showerror("Error", f"Could not save alignment for '{cert_name}'.")

    def _save_admin_positions(self):
        """Saves alignment positions for all 4 certificates at once."""
        success = save_positions(self.admin_positions)
        if success:
            self.renderer.reload_positions()
            self.update_preview()
            self._update_admin_preview()
            messagebox.showinfo(
                "All Alignments Saved",
                "✅ All 4 certificate field alignments have been saved successfully!\n\n"
                "Your customized coordinates are now active across all single prints, batch printing, and PDF exports."
            )
        else:
            messagebox.showerror("Error", "Could not save custom alignment positions to file.")

    def _reset_admin_cert_positions(self):
        cert_k = self.admin_cert_type
        cname = CERT_TYPES.get(cert_k, {}).get('name', cert_k)
        confirm = messagebox.askyesno(
            "Reset Confirmation",
            f"Are you sure you want to revert all field alignments for:\n\n"
            f"'{cname}'\n\n"
            f"back to factory default coordinates?"
        )
        if confirm:
            self.admin_positions = reset_positions(cert_k)
            self.renderer.reload_positions()
            self._sync_admin_field_controls()
            self.update_preview()
            self._update_admin_preview()
            messagebox.showinfo("Reset Done", f"Alignments for '{cname}' reset to factory defaults.")

    def _reset_admin_all_positions(self):
        confirm = messagebox.askyesno(
            "Reset All Certificates",
            "Are you sure you want to revert ALL 4 certificates back to factory default coordinates?\n\n"
            "This will restore all default positions."
        )
        if confirm:
            self.admin_positions = reset_positions(None)
            self.renderer.reload_positions()
            self._sync_admin_field_controls()
            self.update_preview()
            self._update_admin_preview()
            messagebox.showinfo("Reset Done", "All certificates have been restored to factory default alignments.")

    def _admin_test_print(self, mode="overlay"):
        cert_k = self.admin_cert_type
        dummy_data = ADMIN_SAMPLE_DATA.get(cert_k, {})
        cfg = self.config.copy()

        out_pdf = os.path.join(get_output_dir(), f"Admin_Alignment_Test_{cert_k}_{mode}.pdf")
        self.renderer.render_pdf(
            [dummy_data],
            out_pdf,
            mode=mode,
            cert_type=cert_k,
            config=cfg,
            custom_positions_override=self.admin_positions
        )

        printer_name = self.config.get("printer_name") or get_default_printer()
        desc = "OVERLAY MODE (Blank white sheet for printing directly onto stationery)" if mode == "overlay" else "FULL MODE (With template background)"

        confirm = messagebox.askyesno(
            "Print Alignment Test",
            f"Send {desc} test print to:\n\n"
            f"Certificate: {CERT_TYPES[cert_k]['name']}\n"
            f"Printer: {printer_name or 'Default Printer'}\n\n"
            f"Click 'Yes' to print now, or 'No' to open and view the PDF."
        )
        if confirm:
            try:
                print_pdf_file(out_pdf, printer_name)
                messagebox.showinfo("Printed", f"Test sheet sent to {printer_name}!")
            except Exception as e:
                open_pdf(out_pdf)
        else:
            open_pdf(out_pdf)

    # =========================================================================
    # SOFTWARE UPDATES & VERSION CONTROL
    # =========================================================================
    def _background_check_updates(self):
        """Silently checks for updates in background thread on startup."""
        import threading
        def worker():
            try:
                res = updater.check_for_updates(self.config)
                if res and res.get('has_update'):
                    self.latest_update_info = res
                    self.after(0, lambda: self._on_update_found(res))
            except Exception:
                pass
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_update_found(self, res):
        """Updates the header updates button to notify user of a newer version."""
        if hasattr(self, 'update_btn') and self.update_btn:
            self.update_btn.configure(
                text=f"🚀 v{res['new_version']} Available!",
                fg_color="#D97706",
                hover_color="#B45309"
            )

    def open_updates_dialog(self):
        """Opens a modern modal dialog to check, download, or install updates."""
        win = ctk.CTkToplevel(self)
        win.title("Software Updates & Versions")
        win.geometry("640x630")
        win.minsize(580, 560)
        win.transient(self)
        win.grab_set()

        ico_file = get_asset_path("assets", "app_icon.ico")
        if os.path.exists(ico_file):
            try: win.iconbitmap(ico_file)
            except Exception: pass

        # Header banner
        hdr = ctk.CTkFrame(win, fg_color=("#1B365D", "#0F1E33"), corner_radius=0, height=60)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text=f"🎓 {APP_NAME}",
            font=ctk.CTkFont(family="Times New Roman", size=14, weight="bold"),
            text_color="#FFFFFF"
        ).pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkLabel(
            hdr,
            text=f"Current Installed Version: v{APP_VERSION}  |  CBSE 1230048",
            font=ctk.CTkFont(size=11),
            text_color="#CBD5E1"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Main scrollable container
        content = ctk.CTkScrollableFrame(win, corner_radius=0)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        # --- SECTION 1: CHECK FOR UPDATES CARD ---
        card_check = ctk.CTkFrame(content, corner_radius=8)
        card_check.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(
            card_check,
            text="Online & Network Update Channel",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(12, 4))

        status_lbl = ctk.CTkLabel(
            card_check,
            text="Click below to check for the latest version...",
            font=ctk.CTkFont(size=12),
            text_color=("#475569", "#94A3B8"),
            justify="left"
        )
        status_lbl.pack(anchor="w", padx=14, pady=(0, 8))

        progress_bar = ctk.CTkProgressBar(card_check)
        progress_bar.set(0.0)

        # Frame for details when update found
        details_frame = ctk.CTkFrame(card_check, fg_color=("#F1F5F9", "#0F172A"), corner_radius=6)
        lbl_new_ver = ctk.CTkLabel(details_frame, text="", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_new_ver.pack(anchor="w", padx=10, pady=(8, 4))
        txt_changelog = ctk.CTkTextbox(details_frame, height=90, font=ctk.CTkFont(size=11))
        txt_changelog.pack(fill="x", padx=10, pady=(0, 8))

        btn_download = ctk.CTkButton(
            details_frame,
            text="🚀 Download & Install Update",
            font=ctk.CTkFont(weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            height=34
        )

        def do_check():
            status_lbl.configure(text="🔍 Checking for newer version...", text_color=("#2563EB", "#3B82F6"))
            btn_check.configure(state="disabled")
            def worker():
                res = updater.check_for_updates(self.config)
                def update_ui():
                    btn_check.configure(state="normal")
                    if res.get('has_update'):
                        status_lbl.configure(text=f"✨ New Update v{res['new_version']} Found!", text_color="#059669")
                        lbl_new_ver.configure(text=f"Version v{res['new_version']} (Released: {res.get('date', 'Recent')})")
                        txt_changelog.delete("1.0", "end")
                        txt_changelog.insert("1.0", res.get('notes', 'Bug fixes and feature updates.'))
                        details_frame.pack(fill="x", padx=14, pady=(4, 12))
                        btn_download.pack(fill="x", padx=10, pady=(0, 10))
                        btn_download.configure(command=lambda: self._start_online_update_flow(res, progress_bar, status_lbl, btn_download, win))
                    else:
                        details_frame.pack_forget()
                        err = res.get('error')
                        if err:
                            status_lbl.configure(text=f"⚠️ {err}\n(You can also use 'Install Update from File (.zip)' below)", text_color="#D97706")
                        else:
                            status_lbl.configure(text=f"✅ You are running the latest version (v{APP_VERSION}).", text_color="#059669")
                self.after(0, update_ui)
            import threading
            threading.Thread(target=worker, daemon=True).start()

        btn_row_check = ctk.CTkFrame(card_check, fg_color="transparent")
        btn_row_check.pack(fill="x", padx=14, pady=(0, 12))
        btn_check = ctk.CTkButton(
            btn_row_check,
            text="🔄 Check Now",
            width=130,
            command=do_check
        )
        btn_check.pack(side="left")

        # Auto-check if we already discovered an update in background
        if self.latest_update_info and self.latest_update_info.get('has_update'):
            res = self.latest_update_info
            status_lbl.configure(text=f"✨ New Update v{res['new_version']} Found!", text_color="#059669")
            lbl_new_ver.configure(text=f"Version v{res['new_version']} (Released: {res.get('date', 'Recent')})")
            txt_changelog.delete("1.0", "end")
            txt_changelog.insert("1.0", res.get('notes', 'Bug fixes and feature updates.'))
            details_frame.pack(fill="x", padx=14, pady=(4, 12))
            btn_download.pack(fill="x", padx=10, pady=(0, 10))
            btn_download.configure(command=lambda: self._start_online_update_flow(res, progress_bar, status_lbl, btn_download, win))

        # --- SECTION 2: OFFLINE / USB UPDATE CARD ---
        card_offline = ctk.CTkFrame(content, corner_radius=8)
        card_offline.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(
            card_offline,
            text="Offline / USB Update (No Internet Required)",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            card_offline,
            text="If an update package (.zip) was given to you via USB drive or local disk,\nselect the file below to upgrade this computer immediately.",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8"),
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 10))

        ctk.CTkButton(
            card_offline,
            text="📁 Select Update Package (.zip) & Install...",
            height=34,
            fg_color=("#334155", "#475569"),
            hover_color=("#1E293B", "#334155"),
            command=lambda: self._install_update_from_file(win)
        ).pack(fill="x", padx=14, pady=(0, 14))

        # --- SECTION 3: UPDATE SOURCE SETTINGS CARD ---
        card_cfg = ctk.CTkFrame(content, corner_radius=8)
        card_cfg.pack(fill="x", pady=(0, 12), padx=4)

        ctk.CTkLabel(
            card_cfg,
            text="⚙️ Update Source Settings",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=14, pady=(12, 6))

        # Network shared folder
        ctk.CTkLabel(card_cfg, text="Local School Network Folder (e.g. \\\\SERVER\\Updates):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(2, 2))
        f_net = ctk.CTkFrame(card_cfg, fg_color="transparent")
        f_net.pack(fill="x", padx=14, pady=(0, 8))
        ent_net = ctk.CTkEntry(f_net, placeholder_text="\\\\SERVER\\CertificateUpdates or D:\\Shared\\Updates")
        ent_net.insert(0, self.config.get("update_network_folder", ""))
        ent_net.pack(side="left", fill="x", expand=True, padx=(0, 6))
        def browse_net():
            p = filedialog.askdirectory(parent=win, title="Select Network Shared Updates Folder")
            if p:
                ent_net.delete(0, "end")
                ent_net.insert(0, p)
        ctk.CTkButton(f_net, text="Browse", width=70, command=browse_net).pack(side="left")

        # Online URL
        ctk.CTkLabel(card_cfg, text="Online Web Update URL (version.json):", font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w", padx=14, pady=(2, 2))
        ent_url = ctk.CTkEntry(card_cfg, placeholder_text="https://raw.githubusercontent.com/.../version.json")
        ent_url.insert(0, self.config.get("update_url", ""))
        ent_url.pack(fill="x", padx=14, pady=(0, 10))

        chk_auto = ctk.CTkCheckBox(card_cfg, text="Automatically check for updates on software startup")
        if self.config.get("auto_check_updates", True):
            chk_auto.select()
        else:
            chk_auto.deselect()
        chk_auto.pack(anchor="w", padx=14, pady=(0, 12))

        def save_updater_settings():
            self.config["update_network_folder"] = ent_net.get().strip()
            self.config["update_url"] = ent_url.get().strip()
            self.config["auto_check_updates"] = bool(chk_auto.get())
            save_config(self.config)
            messagebox.showinfo("Settings Saved", "Update source configuration saved successfully!", parent=win)

        ctk.CTkButton(
            card_cfg,
            text="💾 Save Update Settings",
            width=160,
            fg_color="#059669",
            hover_color="#047857",
            command=save_updater_settings
        ).pack(anchor="w", padx=14, pady=(0, 14))

    def _start_online_update_flow(self, info, progress_bar, status_lbl, btn_download, parent_win):
        """Downloads and applies update over internet or network."""
        import threading
        btn_download.configure(state="disabled", text="Downloading update...")
        progress_bar.pack(fill="x", padx=14, pady=(4, 10))
        progress_bar.set(0.0)
        status_lbl.configure(text="Connecting to update source...")

        def worker():
            temp_zip = os.path.join(get_base_dir(), "update_package.zip")
            def on_progress(pct):
                self.after(0, lambda: progress_bar.set(pct / 100.0))
                self.after(0, lambda: status_lbl.configure(text=f"Downloading update: {pct}%"))

            try:
                updater.download_file(info['download_url'], temp_zip, progress_callback=on_progress)
                self.after(0, lambda: status_lbl.configure(text="Download complete! Applying update..."))
                is_frozen = getattr(sys, 'frozen', False)
                base_dir = get_base_dir()
                self.after(500, lambda: updater.apply_update_from_zip(temp_zip, is_frozen, base_dir))
            except Exception as e:
                self.after(0, lambda: btn_download.configure(state="normal", text="🚀 Download & Install Update"))
                self.after(0, lambda: status_lbl.configure(text=f"❌ Download failed: {e}"))
                self.after(0, lambda: messagebox.showerror("Update Error", f"Failed to download update:\n{e}", parent=parent_win))

        threading.Thread(target=worker, daemon=True).start()

    def _install_update_from_file(self, parent_win=None):
        """Lets the user select an update zip from disk/USB and installs it."""
        zip_path = filedialog.askopenfilename(
            parent=parent_win or self,
            title="Select Certificate Studio Update Package",
            filetypes=[("Zip Archives", "*.zip"), ("All Files", "*.*")]
        )
        if not zip_path:
            return

        confirm = messagebox.askyesno(
            "Confirm Update Installation",
            f"Are you sure you want to install this update package?\n\n"
            f"File: {os.path.basename(zip_path)}\n\n"
            f"The application will automatically close, install updated files,\n"
            f"and relaunch. Your student records and alignments will be preserved.",
            parent=parent_win or self
        )
        if not confirm:
            return

        try:
            is_frozen = getattr(sys, 'frozen', False)
            base_dir = get_base_dir()
            updater.apply_update_from_zip(zip_path, is_frozen, base_dir)
        except Exception as e:
            messagebox.showerror("Update Failed", f"Could not apply update:\n{e}", parent=parent_win or self)

    def _open_create_update_dialog(self):
        """Admin tool to package the current software state into an update zip."""
        win = ctk.CTkToplevel(self)
        win.title("Create Software Update Package")
        win.geometry("520x460")
        win.minsize(480, 420)
        win.transient(self)
        win.grab_set()

        ico_file = get_asset_path("assets", "app_icon.ico")
        if os.path.exists(ico_file):
            try: win.iconbitmap(ico_file)
            except Exception: pass

        ctk.CTkLabel(
            win,
            text="📦 Package Current Software as Update",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=18, pady=(16, 4))

        ctk.CTkLabel(
            win,
            text=f"Current Version is v{APP_VERSION}. Specify the new version to distribute\nto other school computers.",
            font=ctk.CTkFont(size=11),
            text_color=("#64748B", "#94A3B8"),
            justify="left"
        ).pack(anchor="w", padx=18, pady=(0, 12))

        # Version input
        v_parts = APP_VERSION.split('.')
        try:
            suggested_v = f"{v_parts[0]}.{v_parts[1]}.{int(v_parts[2]) + 1}"
        except Exception:
            suggested_v = "1.0.1"

        ctk.CTkLabel(win, text="New Version Number (e.g. 1.0.1):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=18, pady=(4, 2))
        ent_ver = ctk.CTkEntry(win, width=160)
        ent_ver.insert(0, suggested_v)
        ent_ver.pack(anchor="w", padx=18, pady=(0, 10))

        # Changelog input
        ctk.CTkLabel(win, text="Changelog / What's New:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=18, pady=(4, 2))
        txt_notes = ctk.CTkTextbox(win, height=100)
        txt_notes.insert("1.0", "- Updated certificate alignment and font size 22.\n- Cleaned date formatting.\n- Blank Excel/CSV templates included.")
        txt_notes.pack(fill="x", padx=18, pady=(0, 12))

        # Target output folder
        default_out = os.path.join(get_base_dir(), "Output_Certificates")
        ctk.CTkLabel(win, text="Save Update Package In:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=18, pady=(4, 2))
        f_dest = ctk.CTkFrame(win, fg_color="transparent")
        f_dest.pack(fill="x", padx=18, pady=(0, 16))
        ent_dest = ctk.CTkEntry(f_dest)
        ent_dest.insert(0, default_out)
        ent_dest.pack(side="left", fill="x", expand=True, padx=(0, 6))
        def browse_dest():
            p = filedialog.askdirectory(parent=win, title="Select Destination Folder")
            if p:
                ent_dest.delete(0, "end")
                ent_dest.insert(0, p)
        ctk.CTkButton(f_dest, text="Browse", width=70, command=browse_dest).pack(side="left")

        lbl_status = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=11))
        lbl_status.pack(anchor="w", padx=18, pady=(0, 6))

        def do_create():
            n_ver = ent_ver.get().strip()
            if not n_ver:
                messagebox.showerror("Error", "Please enter a valid version number.", parent=win)
                return
            n_notes = txt_notes.get("1.0", "end").strip()
            dest_dir = ent_dest.get().strip() or default_out

            btn_build.configure(state="disabled", text="Packaging files...")
            lbl_status.configure(text="Compressing and generating version manifest...", text_color="#2563EB")

            def worker():
                try:
                    zip_p, json_p = updater.create_update_package(n_ver, n_notes, dest_dir)
                    def on_done():
                        btn_build.configure(state="normal", text="📦 Generate Update Package (.zip)")
                        lbl_status.configure(text="✅ Update package generated successfully!", text_color="#059669")
                        confirm_open = messagebox.askyesno(
                            "Update Package Created",
                            f"Update Package v{n_ver} has been generated successfully!\n\n"
                            f"Files created:\n"
                            f"• {os.path.basename(zip_p)}\n"
                            f"• {os.path.basename(json_p)}\n\n"
                            f"Location: {dest_dir}\n\n"
                            f"Would you like to open this folder now?",
                            parent=win
                        )
                        if confirm_open:
                            try:
                                os.startfile(dest_dir)
                            except Exception:
                                pass
                        win.destroy()
                    self.after(0, on_done)
                except Exception as e:
                    def on_err():
                        btn_build.configure(state="normal", text="📦 Generate Update Package (.zip)")
                        lbl_status.configure(text=f"❌ Failed: {e}", text_color="#EF4444")
                        messagebox.showerror("Error", f"Failed to create update package:\n{e}", parent=win)
                    self.after(0, on_err)

            import threading
            threading.Thread(target=worker, daemon=True).start()

        btn_build = ctk.CTkButton(
            win,
            text="📦 Generate Update Package (.zip)",
            font=ctk.CTkFont(weight="bold"),
            height=36,
            fg_color="#059669",
            hover_color="#047857",
            command=do_create
        )
        btn_build.pack(fill="x", padx=18, pady=(0, 16))

def main():
    app = CertificateApp()
    app.mainloop()

if __name__ == '__main__':
    main()
