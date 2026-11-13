# Mount Everest Higher Secondary School - Certificate System

A dedicated Windows visual desktop application designed for **Mount Everest Higher Secondary School** (CBSE Affiliation No. 1230048, Taphou, Senapati - 795106, Manipur) to create, preview, manage, and print all 4 official school certificates.

---

## 🌟 New Features & Enhancements

### 1. 🖨️ Existing Paper Size from Printer Setup
- **Direct Printer Integration**: Reads the supported paper sizes directly from your connected printer (e.g. `EPSON L3210 Series`).
- **`Auto (Printer Setup)` Option**: Automatically detects and uses the active paper size configured in your Epson printer preferences.
- **Custom / Standard Sizes**: Switch between `10.5" × 7.5"` (Certificate Standard), `10.0" × 7.5"`, `A4`, `Letter`, or any paper size defined on your printer.

### 2. 📑 Selective Certificate Printing (Pages 1 to 4)
Choose exactly which certificates to print or export:
- `[✓] Page 1: Provisional Certificate`
- `[✓] Page 2: Character Certificate`
- `[✓] Page 3: Transfer Certificate`
- `[✓] Page 4: Reading Certificate`

Quick selector buttons:
- **`All 4 Pages`**: Merges all 4 certificates for the student into a single 4-page print job / PDF.
- **`Only Current`**: Prints or saves only the currently viewed certificate.

### 3. 📂 Dedicated Output Folder
- All exported and printed PDFs are automatically saved in:
  ```
  d:\Certificate app\Output_Certificates\
  ```
- Use the green **`📂 Output Folder`** button on the top bar to open the folder in Windows Explorer with 1 click.

### 4. 📅 Automatic Live Current Date
- The **"Dated, Senapati"** issue date is automatically populated with the live current date (`DD/MM/YYYY`) dynamically on startup, certificate switch, or form reset.

### 5. 🎯 Fixed & Calibrated Text Alignment
- All text fields use baseline positioning (`anchor='ls'`) aligned to the dotted lines of each certificate template.

---

## 📜 The 4 Certificates Supported

| Certificate Type | Key Fields | Description |
| :--- | :--- | :--- |
| **1. 📄 Provisional Certificate** | Sl. No., Student Name, S/o D/o Mr. & Mrs., Inhabitant of, AISSE/AISSCE, Exam Year, Roll No., Grade, Date of Birth, CBSE Reg No., Result Announcement Date, Issue Date | Official CBSE board qualification provisional certificate |
| **2. 📜 Character Certificate** | Sl. No., Student Name, Conduct & Character (Qualified/Disqualified), AISSE/AISSCE, Exam Year, Roll No., Grade, Academic Session, Issue Date | Conduct and character certification |
| **3. 🎓 Transfer Certificate** | Sl. No., Student Name, Father & Mother Name, AISSE/AISSCE, Year, Roll No., Grade, Academic Session Dues Cleared, Date of Birth, CBSE Reg No., Left School On, PEN No., Reasons of Leaving, Issue Date | Official school transfer / clearance certificate |
| **4. 📖 Reading Certificate** | Sl. No., Student Name, Father & Mother Name, Inhabitant of, Class reading in, Stream, Section, Class Roll No., Academic Session, Date of Birth, Issue Date | Bona fide student bonafide / current enrollment reading certificate |

---

## 🚀 How to Launch the Application

### Option A: Double-Click Launcher (Recommended)
Double-click:
```
Launch_Certificate_App.bat
```
*(Runs silently without leaving a black command prompt window open, and places the official school emblem icon in your Windows System Tray).*

### Option B: Terminal / PowerShell
```powershell
cd "d:\Certificate app"
python app.py
```

---

## 💻 Moving the Application to Another PC (Step-by-Step)

If you transfer or copy this application folder to another Windows computer, follow these simple steps:

### 1. Copy the Project Folder
Copy the entire `Certificate app` folder to the new computer (e.g. to `D:\Certificate app` or `C:\Certificate app`).

### 2. Install Python
1. Download and install Python (3.10 to 3.14) from [python.org](https://www.python.org/downloads/).
2. **Important:** On the first installer screen, check the box **"Add python.exe to PATH"**.

### 3. Install Python Dependencies
Open PowerShell or Command Prompt in the project folder and run:
```bash
pip install customtkinter pillow openpyxl reportlab pywin32
```

### 4. 🔤 Bundled Registered Fonts (`assets\fonts\`)
All official fonts required by the school certificates are extracted and stored inside:
```
assets\fonts\
```
* **Commercial Script BT**: `COMSCRTN.TTF` (Registered font family `CommercialScriptBT`)
* **Souvenir Light**: `SOUVNRL.TTF`
* **Souvenir Light Italic**: `SOUVNRLI.TTF`
* **Souvenir Demi**: `SOUVNRD.TTF`
* **Souvenir Demi Italic**: `SOUVNRDI.TTF`
* **Times New Roman & Bold**: `times.ttf`, `timesbd.ttf`

> [!NOTE]
> The Certificate Studio automatically loads and registers all fonts directly from the local `assets\fonts\` folder. It works immediately without requiring any extra setup.

#### (Optional) Install Fonts in Windows System
If you also want these fonts available across Windows (in Microsoft Word, Excel, Photoshop, etc.):
1. Open the `assets\fonts\` folder in Windows Explorer.
2. Select all `.TTF` font files (`Ctrl + A`).
3. Right-click any selected file and choose **"Install for all users"** (or **"Install"**).

### 5. Launch the Application
Double-click `Launch_Certificate_App.bat` to start!

---

## 🛡️ Admin Alignment Portal
- Click the **`🛠️ Admin Alignment`** button on the top right bar.
- Default Password: `1234`
- You can fine-tune text field positions (X, Y) for any certificate and change the admin password inside the portal anytime.
