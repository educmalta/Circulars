Circulars Dashboard

This small Flask app watches a local folder for uploaded circulars (DOCX and PDF), extracts year, sender and any dates (deadlines), and provides a web dashboard.

Quick start

1. Create a virtual environment (recommended) and install requirements:
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt

2. Edit processor.RAW_FOLDER in processor.py to point to the folder where circulars are saved (default is set to your provided path).

3. Run the app:
   python app.py

4. Open http://127.0.0.1:5000 in your browser.

Notes
- The app polls the folder every 30 seconds. A manual rescan is available at /rescan.
- Extraction is heuristic-based. For improved accuracy add NLP/OCR or tune the DATE_REGEXES and SENDER_KEYWORDS.
