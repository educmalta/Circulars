# Circulars Dashboard

A local Flask dashboard for organising education circulars by department, circular
number, and year, while displaying valid future deadlines separately.

## Privacy boundary

The application is designed to run locally. Circular files, extracted text,
the SQLite database, SharePoint downloads, email attachments, and scan reports
remain on the local machine and are ignored by Git. Only source code, templates,
scripts, and documentation should be committed. Do not add circular documents,
database backups, credentials, or `.env` files to the repository.

## How it works

1. `processor.py` scans the configured local roots for PDF and DOCX circulars.
   Saved `.eml` files are supported through the standard-library email parser;
   saved `.msg` files are supported when `extract_msg` is installed.
2. References such as `DFIN 8/2025`, `IPS 10/23`, `DGPM/07 /2026`, `DG DES
   24/2026`, and similar department-number-year forms are normalised into
   department, circular number, and four-digit year fields.
3. PDF text is extracted with PyPDF2. An optional OCR fallback is attempted for
   image-only PDFs when `pdf2image`, Pillow, Tesseract, and `pytesseract` are
   available.
4. Results are stored in the local `data/circulars.db` database. Rescans
   recompute extracted references and deadlines, update existing records, and
   remove duplicate department/number/year entries.
5. The dashboard groups circulars by year and sender/department. The deadlines
   page excludes expired dates and orders remaining deadlines from soonest to
   latest. File paths are served through a local, approved-root endpoint and
   open in a new browser tab.
6. A background scan runs every 30 seconds, and **Rescan Now** invokes the same
   scan immediately.

## Quick start

1. Create a virtual environment (recommended) and install requirements:
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt

2. Configure the raw sources. The app checks the legacy local folder and also looks for a synced OneDrive / SharePoint "Circulars" folder automatically. For custom folders, set the environment variable:
   $env:CIRCULAR_RAW_FOLDERS = "C:\path\to\shared\Circulars;C:\path\to\other\Circulars"

3. Run the app:
   python app.py

4. Open http://127.0.0.1:5000 in your browser.

The Windows launcher `run_dashboard.bat` starts the app and opens the dashboard.

## Configuration and sync

- The app polls the configured folders every 30 seconds. A manual rescan is available at `/rescan` and through the dashboard button.
- If your SharePoint library is synced locally to OneDrive, the app will scan that folder automatically as long as it is in the configured roots. If a SharePoint folder is not synced, use the optional SharePoint sync endpoint documented below.
- Extraction is heuristic-based. Department references are intentionally broad, but ambiguous documents should be reviewed rather than treated as circulars automatically.

### Optional direct SharePoint/OneDrive sync

- The app includes an optional Microsoft Graph helper (sharepoint_client.py) that can download files from a remote SharePoint/OneDrive path using MSAL device-code flow.
- To use it:
  1. Install extra dependencies: pip install msal requests
  2. Optionally set GRAPH_CLIENT_ID and GRAPH_TENANT environment variables for your Azure app/tenant.
  3. POST to /sync_sharepoint?remote_path=Circulars/2026 (or open in browser after logging in) — the server will prompt for device-code sign-in once.
  4. Downloaded files are stored under sharepoint_downloads/<remote_path> and are scanned automatically.

Security note: device-code sign-in requires interactive approval and is recommended only for administrators.

## Validation

Run the existing syntax and parser checks from the repository root:

    python -m py_compile processor.py app.py
    python -c "from processor import parse_filename_reference; assert parse_filename_reference('DFIN 8/25.pdf') == ('DFIN', 8, 2025); assert parse_filename_reference('IPS 10/23.pdf') == ('IPS', 10, 2023)"

Do not run a full scan against private folders in CI. Local scans require access
to the configured folders and write only to the ignored local database.
