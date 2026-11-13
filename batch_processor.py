import os
import csv
import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from renderer import compute_sl_no, to_sentence_case, clean_date_str

def normalize_key(key: str) -> str:
    cleaned = ''.join(c.lower() for c in key if c.isalnum())
    if cleaned in ('certtype', 'certificate', 'type', 'certificatetype'):
        return 'cert_type'
    if cleaned in ('slno', 'serial', 'serialno', 'sl', 'no', 'certificateno', 'certno'):
        return 'sl_no'
    if cleaned in ('studentname', 'name', 'candidatename', 'student', 'nameofstudent', 'fullname'):
        return 'student_name'
    if cleaned in ('fathername', 'fathersname', 'father', 'mr', 'sodoomr', 'fatherhusbandname', 'sodoo'):
        return 'father_name'
    if cleaned in ('mothername', 'mothersname', 'mother', 'mrs', 'mrsname', 'andmrs'):
        return 'mother_name'
    if cleaned in ('address', 'inhabitant', 'inhabitantof', 'residence', 'village', 'place', 'town', 'district'):
        return 'address'
    if cleaned in ('examname', 'exam', 'aisseaissce', 'examination', 'course'):
        return 'exam_name'
    if cleaned in ('examyear', 'year', 'examinationyear', 'passingyear'):
        return 'exam_year'
    if cleaned in ('rollno', 'roll', 'rollnumber', 'cbserollno', 'boardrollno', 'boardroll'):
        return 'roll_no'
    if cleaned in ('grade', 'division', 'result', 'gradeorresult', 'divisiongrade', 'finalgrade'):
        return 'grade'
    if cleaned in ('session', 'academicsession', 'academicyear', 'period'):
        return 'session'
    if cleaned in ('dob', 'dateofbirth', 'birthdate', 'birth'):
        return 'dob'
    if cleaned in ('regno', 'registrationno', 'registrationnumber', 'cbseregno', 'boardregno', 'cbseregistrationno'):
        return 'reg_no'
    if cleaned in ('resultdate', 'announcedon', 'resultannouncedon', 'resultannounceddate', 'dateofresult'):
        return 'result_date'
    if cleaned in ('leftdate', 'leftschoolon', 'dateofleaving', 'dateofleavingschool', 'dateleft', 'leavingdate'):
        return 'left_date'
    if cleaned in ('penno', 'pen', 'permanenteducationnumber', 'pennumber'):
        return 'pen_no'
    if cleaned in ('classname', 'class', 'readinginclass', 'readingclass', 'currentclass'):
        return 'class_name'
    if cleaned in ('stream', 'subject', 'major', 'faculty'):
        return 'stream'
    if cleaned in ('section', 'sec'):
        return 'section'
    if cleaned in ('classrollno', 'classroll', 'rollcls', 'classrollnumber'):
        return 'class_roll_no'
    if cleaned in ('status', 'qualified'):
        return 'status'
    if cleaned in ('date', 'issuedate', 'dated', 'the', 'dateofissue', 'issue'):
        return 'issue_date'
    return cleaned

def read_batch_file(file_path: str) -> list[dict]:
    """
    Reads an Excel or CSV file and returns standardized student records.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    raw_rows = []

    if ext in ('.xlsx', '.xlsm', '.xltx'):
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        # If there are multiple sheets, prefer one named 'Student Data', 'Students', or 'Certificates'
        for sname in ('Student Data', 'Students', 'Certificates'):
            if sname in wb.sheetnames:
                sheet = wb[sname]
                break

        headers = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(cell).strip() if cell is not None else f"col_{j}" for j, cell in enumerate(row)]
            else:
                if any(cell is not None and str(cell).strip() != '' for cell in row):
                    row_dict = {}
                    for j, cell in enumerate(row):
                        if j < len(headers):
                            if isinstance(cell, (datetime.datetime, datetime.date)):
                                val = clean_date_str(cell)
                            else:
                                val = "" if cell is None else clean_date_str(str(cell).strip()) if "00:00:00" in str(cell) else str(cell).strip()
                            row_dict[headers[j]] = val
                    raw_rows.append(row_dict)
    elif ext in ('.csv', '.txt'):
        with open(file_path, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if any(v and str(v).strip() for v in row.values()):
                    row_clean = {}
                    for k, v in row.items():
                        if not k:
                            continue
                        val = "" if v is None else str(v).strip()
                        if "00:00:00" in val:
                            val = clean_date_str(val)
                        row_clean[k.strip()] = val
                    raw_rows.append(row_clean)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Please use .xlsx or .csv")

    records = []
    for r in raw_rows:
        rec = {
            'cert_type': 'provisional',
            'sl_no': '',
            'student_name': '',
            'father_name': '',
            'mother_name': '',
            'address': '',
            'exam_name': '',
            'exam_year': '',
            'roll_no': '',
            'grade': '',
            'session': '',
            'dob': '',
            'reg_no': '',
            'result_date': '',
            'left_date': '',
            'pen_no': '',
            'class_name': '',
            'stream': '',
            'section': '',
            'class_roll_no': '',
            'status': '',
            'issue_date': ''
        }
        for k, v in r.items():
            norm = normalize_key(k)
            if norm in rec:
                val = str(v).strip()
                if norm == 'cert_type':
                    val = val.lower()
                    if 'prov' in val: val = 'provisional'
                    elif 'char' in val: val = 'character'
                    elif 'trans' in val or 'tc' in val: val = 'transfer'
                    elif 'read' in val: val = 'reading'
                elif norm in ('student_name', 'father_name', 'mother_name', 'address'):
                    val = to_sentence_case(val)
                elif norm in ('dob', 'result_date', 'left_date', 'issue_date') or norm.endswith('_date'):
                    val = clean_date_str(val)
                rec[norm] = val

        if not rec.get('sl_no'):
            rec['sl_no'] = compute_sl_no(
                rec.get('cert_type', 'provisional'),
                reg_no=rec.get('reg_no', ''),
                stream=rec.get('stream', ''),
                section=rec.get('section', ''),
                class_roll=rec.get('class_roll_no', '')
            )

        if rec['student_name'] or rec['roll_no']:
            records.append(rec)

    return records

def create_sample_files(dest_dir: str):
    """
    Creates comprehensive, professionally styled Excel and CSV templates
    reconstructed specifically for Mount Everest Higher Secondary School certificates.
    """
    os.makedirs(dest_dir, exist_ok=True)
    excel_path = os.path.join(dest_dir, 'Mount_Everest_Certificates_Template.xlsx')
    csv_path = os.path.join(dest_dir, 'Mount_Everest_Certificates_Template.csv')

    headers = [
        "Student Name", "Father's Name", "Mother's Name", "Address", "Date of Birth",
        "CBSE Reg No", "CBSE Roll No", "Exam Name", "Exam Year", "Grade",
        "Academic Session", "Result Announced Date", "Date Left School", "PEN No",
        "Class", "Stream", "Section", "Class Roll No",
        "Sl. No.", "Issue Date", "Certificate Type"
    ]

    wb = openpyxl.Workbook()

    # -------------------------------------------------------------
    # SHEET 1: Student Data (Clean entry sheet ready for your student records)
    # -------------------------------------------------------------
    ws = wb.active
    ws.title = "Student Data"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1B365D", end_color="1B365D", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    ws.append(headers)
    ws.row_dimensions[1].height = 28
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    # Add 25 clean blank rows formatted and ready for student data entry
    for r_i in range(2, 27):
        ws.row_dimensions[r_i].height = 22
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_i, column=col_idx)
            cell.border = thin_border
            if col_idx in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21):
                cell.alignment = align_center
            else:
                cell.alignment = align_left

    for col in ws.columns:
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = 16

    # -------------------------------------------------------------
    # SHEET 2: Field Guide & Notes (Instructions for reference)
    # -------------------------------------------------------------
    ws_guide = wb.create_sheet(title="Field Guide & Notes")
    guide_headers = ["Column Name", "Applies To Certificate(s)", "Description & Format", "Required / Optional"]
    guide_rows = [
        ["Student Name", "All 4 Certificates", "Full name of the student (automatically formatted to Title Case)", "Required"],
        ["Father's Name", "Provisional, Transfer, Reading", "Father's name (S/o, D/o Mr.)", "Recommended"],
        ["Mother's Name", "Provisional, Transfer, Reading", "Mother's name (& Mrs.)", "Recommended"],
        ["Address", "Provisional, Reading", "Village, Town, District or locality", "Recommended"],
        ["Date of Birth", "Provisional, Transfer, Reading", "Format: DD/MM/YYYY (e.g. 15/04/2006)", "Recommended"],
        ["CBSE Reg No", "Provisional, Character, Transfer", "e.g. R/1/24/1230048/0042 (Last 3 digits auto-set the Sl. No.!)", "Recommended"],
        ["CBSE Roll No", "Provisional, Character, Transfer", "8-digit CBSE Board examination roll number", "Recommended"],
        ["Exam Name", "Provisional, Character, Transfer", "'AISSCE (Class 12)' or 'AISSE (Class 10)'", "Optional (Default: AISSCE)"],
        ["Exam Year", "Provisional, Character, Transfer", "Passing year, e.g. 2024", "Optional (Default: 2024)"],
        ["Grade", "Provisional, Character, Transfer", "Grade or division, e.g. A1, A2, B1, B2, Passed", "Recommended"],
        ["Academic Session", "Character, Transfer, Reading", "e.g. 2023 - 2024", "Recommended"],
        ["Result Announced Date", "Provisional", "e.g. 13th May, 2024 or 13/05/2024", "Optional"],
        ["Date Left School", "Transfer Certificate", "Date of leaving school (DD/MM/YYYY)", "Optional (For TC)"],
        ["PEN No", "Transfer Certificate", "Permanent Education Number", "Optional (For TC)"],
        ["Class", "Reading Certificate", "Class currently studying, e.g. XI or XII", "Optional (For Reading)"],
        ["Stream", "Reading Certificate", "Science, Arts, or Commerce", "Optional (For Reading)"],
        ["Section", "Reading Certificate", "Section, e.g. A or B", "Optional (For Reading)"],
        ["Class Roll No", "Reading Certificate", "Class roll number, e.g. 08 or 18", "Optional (For Reading)"],
        ["Sl. No.", "All Certificates", "LEAVE BLANK to auto-generate: '042' for Prov/Char/TC, 'Sc/A/08' for Reading", "Optional Override"],
        ["Issue Date", "All Certificates", "LEAVE BLANK to automatically use today's date (DD/MM/YYYY)", "Optional Override"],
        ["Certificate Type", "Batch Processing", "'All' (can generate any certificate), or 'Provisional', 'Character', 'Transfer', 'Reading'", "Optional"]
    ]

    ws_guide.append(guide_headers)
    ws_guide.row_dimensions[1].height = 28
    for col_idx in range(1, len(guide_headers) + 1):
        cell = ws_guide.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        cell.alignment = align_center

    for r_idx, g_row in enumerate(guide_rows, start=2):
        ws_guide.append(g_row)
        ws_guide.row_dimensions[r_idx].height = 22
        for col_idx in range(1, len(g_row) + 1):
            cell = ws_guide.cell(row=r_idx, column=col_idx)
            cell.border = thin_border
            if col_idx in (1, 4):
                cell.alignment = align_center
            else:
                cell.alignment = align_left

    for col in ws_guide.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws_guide.column_dimensions[col_letter].width = max(max_len + 4, 18)

    # Ensure Student Data is the active sheet when user opens the workbook
    wb.active = 0
    saved = False
    for fname in ('Mount_Everest_Certificates_Template.xlsx', 'Mount_Everest_Certificates_Template_Blank.xlsx', 'Mount_Everest_Certificates_Template_New.xlsx'):
        try:
            target = os.path.join(dest_dir, fname)
            wb.save(target)
            excel_path = target
            saved = True
            break
        except PermissionError:
            continue
    if not saved:
        target = os.path.join(dest_dir, f'Mount_Everest_Certificates_Template_{os.getpid()}.xlsx')
        wb.save(target)
        excel_path = target

    # Write clean CSV Template with headers
    for cname in ('Mount_Everest_Certificates_Template.csv', 'Mount_Everest_Certificates_Template_Blank.csv'):
        try:
            target_csv = os.path.join(dest_dir, cname)
            with open(target_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            csv_path = target_csv
            break
        except PermissionError:
            continue

    return excel_path, csv_path

if __name__ == '__main__':
    dest = os.path.join(os.path.dirname(__file__), 'samples')
    ex, cs = create_sample_files(dest)
    print(f"Sample files created:\n{ex}\n{cs}")
