Circulars Dashboard

This small Flask app watches one or more raw circular folders (DOCX and PDF), extracts year, sender and any dates (deadlines), and provides a web dashboard.

Quick start

1. Create a virtual environment (recommended) and install requirements:
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt

2. Configure the raw sources. The app checks the legacy local folder and also looks for a synced OneDrive / SharePoint "Circulars" folder automatically. For custom folders, set the environment variable:
   $env:CIRCULAR_RAW_FOLDERS = "C:\path\to\shared\Circulars;C:\path\to\other\Circulars"

3. Run the app:
   python app.py

4. Open http://127.0.0.1:5000 in your browser.

Notes
- The app polls the configured folders every 30 seconds. A manual rescan is available at /rescan.
- If your SharePoint library is synced locally to OneDrive, the app will scan that folder automatically as long as it is in the configured roots. If a SharePoint folder is not synced, use the optional SharePoint sync endpoint documented below.
- Extraction is heuristic-based. For improved accuracy add NLP/OCR or tune the DATE_REGEXES and SENDER_KEYWORDS.

Optional: direct SharePoint/OneDrive sync
- The app includes an optional Microsoft Graph helper (sharepoint_client.py) that can download files from a remote SharePoint/OneDrive path using MSAL device-code flow.
- To use it:
  1. Install extra dependencies: pip install msal requests
  2. Optionally set GRAPH_CLIENT_ID and GRAPH_TENANT environment variables for your Azure app/tenant.
  3. POST to /sync_sharepoint?remote_path=Circulars/2026 (or open in browser after logging in) — the server will prompt for device-code sign-in once.
  4. Downloaded files are stored under sharepoint_downloads/<remote_path> and are scanned automatically.

Security note: device-code sign-in requires interactive approval and is recommended only for administrators.
