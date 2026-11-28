# Mount Everest Higher Secondary School — Certificate Printing Studio

A dedicated Windows desktop application for **Mount Everest Higher Secondary School** (CBSE Affiliation No. `1230048`, Taphou, Senapati - 795106, Manipur) to design, preview, manage, and print all four official school certificates.

---

## ✨ Key Features

- **4 Official Certificates Supported**:
  - **Provisional Certificate**
  - **Character Certificate**
  - **Transfer Certificate**
  - **Reading Certificate**
- **Auto-Fill Across Certificate Switches**: Typing or loading a student's details preserves and auto-fills shared fields when switching between Provisional, Character, Transfer, and Reading certificates.
- **Editable Vector Templates & Wording Editor**: Customize school header lines, fonts, font sizes, body wording, and footer signatures with live WYSIWYG preview.
- **Interactive Drag-and-Drop Calibration**: Click and drag either template layout elements or candidate data fields directly on the preview canvas (plus keyboard arrow-key nudging for 1px/5px precision).
- **Direct Printer & Paper Integration**: Reads paper sizes directly from your connected Windows printer (`10.5" × 7.5"`, `Auto (Printer Setup)`, `A4`, `Letter`, or custom dimensions).
- **Batch Processing & Searchable Records**: Import student lists from Excel (`.xlsx`) or `.csv`, generate multi-page PDFs, and search past issued certificates stored locally.
- **In-App Differential Updates**: Checks for new releases and downloads **only modified files** directly inside the app without opening a browser—or via a local shared network folder / offline `.zip`.

---

## 🚀 Quick Start (Windows)

No Python installation is required.

1. Download or copy the **`dist/CertificateStudio`** folder to your Windows PC (for example, `D:\CertificateStudio`).
2. Double-click **`CertificateStudio.exe`** to launch the application.
3. All required fonts and certificate assets are bundled inside `_internal\assets\`.

---

## 🔄 Updating on Any PC

1. Open **Certificate Studio** and click the **Updates** button in the top header.
2. Click **🔄 Check Now**.
3. If a newer version is available, click **🚀 Download & Install Update**.
   - The app downloads only the updated files in the background, preserves your `certificates.db`, `config.json`, `custom_positions.json`, and `Output_Certificates/` folder, and relaunches automatically.
4. For offline PCs, you can also use **📁 Select Update Package (.zip) & Install...** or configure a **Local School Network Folder** in Update Source Settings.

---

## 🛠️ Admin Portal

- Click **🛠️ Admin** on the top right bar (Default PIN: `1234`).
- Inside the Admin Portal you can:
  - Open **✏️ Certificate Templates & Wording Editor** to edit wording, fonts, and drag-and-drop template/field positions.
  - Fine-tune field coordinates (`X`, `Y`) and test-print calibration overlays.
  - Change the Admin PIN anytime.
