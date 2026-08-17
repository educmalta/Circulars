import os
import re
import json
import sqlite3
import time
from datetime import datetime
from dateutil import parser as dateparser
from docx import Document
from PyPDF2 import PdfReader

# Primary watch folder(s). These can include a synced OneDrive / SharePoint folder.
DEFAULT_RAW_FOLDER = r"C:\Users\JeffreyZammit\Desktop\AI Projects\Circulars\raw circulars"


def get_raw_folders():
    configured = []
    raw_value = os.environ.get('CIRCULAR_RAW_FOLDERS')
    if raw_value:
        configured.extend(part.strip() for part in re.split(r'[;\n,]', raw_value) if part.strip())
    if DEFAULT_RAW_FOLDER and DEFAULT_RAW_FOLDER not in configured:
        configured.append(DEFAULT_RAW_FOLDER)

    user_home = os.path.expanduser('~')
    candidates = [
        os.path.join(user_home, 'OneDrive'),
        os.path.join(user_home, 'OneDrive - ilearn.edu.mt'),
        os.path.join(user_home, 'OneDrive - Ilearn.edu.mt'),
        os.path.join(user_home, 'OneDrive - Ilearn Education'),
        os.path.join(user_home, 'OneDrive - Ministry for Education, Sport, Youth, Research and Innovation'),
        os.path.join(user_home, 'Documents'),
        os.path.join(user_home, 'Desktop', 'AI Projects', 'Circulars', 'raw circulars'),
    ]
    for candidate in candidates:
        if candidate not in configured:
            configured.append(candidate)

    # Also include any child folder named literally 'Circulars' or 'raw circulars' under the main roots.
    for root in list(configured):
        try:
            if os.path.isdir(root):
                for child in os.listdir(root):
                    full = os.path.join(root, child)
                    if os.path.isdir(full) and child.lower().replace(' ', '') in {'circulars', 'rawcirculars'}:
                        configured.append(full)
        except Exception:
            pass
    return [p for p in configured if p]


RAW_FOLDER = DEFAULT_RAW_FOLDER
RAW_FOLDERS = get_raw_folders()
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "circulars.db")

# include Maltese month names mapping
MALTESE_MONTHS = {
    'Jannar':'January','Frar':'February','Marzu':'March','April':'April','Mejju':'May','Ġunju':'June','Lulju':'July',
    'Awwissu':'August','Settembru':'September','Ottubru':'October','Novembru':'November','Diċembru':'December',
    # lowercase variants will be replaced case-insensitively
}

DATE_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Jannar|Frar|Marzu|April|Mejju|Ġunju|Lulju|Awwissu|Settembru|Ottubru|Novembru|Diċembru)"

FORBIDDEN_DEPARTMENTS = {'MALTA', 'VET', 'ECEC', 'PRIMARY', 'SECONDARY', 'DATE'}

DATE_REGEXES = [
    # numeric dates like 25/09/2026 or 2026-09-25
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    # month-name formats: 'September 25, 2026' or 'Sep 25 2026' or Maltese month names
    rf"\b{DATE_MONTHS}[a-z]*\s+\d{{1,2}},?\s+\d{{4}}\b",
    # day-month-year with month name and optional ordinal and optional Maltese connector (ta’, t’)
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?(?:\s*(?:ta[’']|t[’']|ta|t|of)\s*)?{DATE_MONTHS}[a-z]*\s+\d{{4}}\b",
    # catch written forms like '25th Sep 2026' with separators
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?[\s\-]{DATE_MONTHS}[a-z]*[\s\-]\d{{4}}\b",
]
SENDER_KEYWORDS = ["DGPM", "Directorate", "DG", "Ministry", "Director" ]

def init_db(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS circulars (
            id INTEGER PRIMARY KEY,
            filepath TEXT UNIQUE,
            filename TEXT,
            year INTEGER,
            sender TEXT,
            deadlines TEXT,
            snippet TEXT,
            last_modified REAL,
            department TEXT,
            circular_number INTEGER
        )
    ''')
    # ensure columns exist for older DBs
    cur.execute("PRAGMA table_info(circulars)")
    cols = [r[1] for r in cur.fetchall()]
    if 'department' not in cols:
        try:
            cur.execute("ALTER TABLE circulars ADD COLUMN department TEXT")
        except Exception:
            pass
    if 'circular_number' not in cols:
        try:
            cur.execute("ALTER TABLE circulars ADD COLUMN circular_number INTEGER")
        except Exception:
            pass
    conn.commit()
    conn.close()


def text_from_docx(path):
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""


def text_from_pdf(path):
    try:
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            texts.append(page.extract_text() or "")
        return "\n".join(texts)
    except Exception:
        return ""


def _replace_maltese_months(s):
    for m,k in MALTESE_MONTHS.items():
        s = re.sub(m, k, s, flags=re.IGNORECASE)
    return s


def find_dates(text):
    # pre-clean: remove spaces inside digit groups (e.g., '202 6' -> '2026') to handle PDF extraction artifacts
    text = re.sub(r'(?<=\d)\s+(?=\d)', '', text)
    found = set()
    for rx in DATE_REGEXES:
        for m in re.findall(rx, text, flags=re.IGNORECASE):
            # m can be the full match string; normalize Maltese months
            s = m if isinstance(m, str) else ' '.join(m)
            s = s.replace('\u2019', '\'') if '\u2019' in s else s
            s = _replace_maltese_months(s)
            try:
                dt = dateparser.parse(s, dayfirst=True, fuzzy=True)
                if dt:
                    found.add(dt.date().isoformat())
            except Exception:
                pass
    return sorted(found)


def guess_sender(text):
    # Look for uppercase acronyms first
    for kw in SENDER_KEYWORDS:
        if kw.lower() in text.lower():
            # return nearby context
            m = re.search(r"(.{0,40}" + re.escape(kw) + r".{0,40})", text, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
            return kw
    # fallback - first few lines
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        return lines[0][:120]
    return "Unknown"


def extract_reference_from_text(text):
    patterns = [
        r"(?i)\b(?:ref(?:er(?:en[cz]a|ence))?)\s*[:\-]?\s*([A-Z]{2,8})\s*(\d{1,4})\s*(?:[./-]|\s+)\s*(\d{4})",
        r"(?i)\b([A-Z]{2,8})\s*(\d{1,4})\s*(?:[./-]|\s+)\s*(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            department = match.group(1).upper().strip()
            number = int(match.group(2))
            year = int(match.group(3))
            if number <= 9999 and year >= 2000:
                return department, number, year
    return None


def scan_folder(folder=None, db_path=DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30)
    cur = conn.cursor()
    folder_list = []
    if folder is None:
        folder_list = RAW_FOLDERS
    elif isinstance(folder, (list, tuple, set)):
        folder_list = list(folder)
    else:
        folder_list = [folder]

    for current_folder in folder_list:
        if not current_folder or not os.path.isdir(current_folder):
            continue
        for root, _, files in os.walk(current_folder):
            for fn in files:
                lower = fn.lower()
                if not (lower.endswith('.docx') or lower.endswith('.pdf')):
                    continue
                path = os.path.join(root, fn)
                try:
                    mtime = os.path.getmtime(path)
                except Exception:
                    continue
                cur.execute('SELECT last_modified, deadlines FROM circulars WHERE filepath=?', (path,))
                row = cur.fetchone()
                # If file seen before and not modified AND deadlines already extracted, skip
                if row:
                    last_mod, existing_deadlines = row[0], row[1]
                    if last_mod and last_mod >= mtime and existing_deadlines and len(existing_deadlines) > 2:
                        continue
                if lower.endswith('.docx'):
                    text = text_from_docx(path)
                else:
                    text = text_from_pdf(path)
                snippet = (text[:800] + '...') if len(text) > 800 else text
                dates = find_dates(text)

                # Try to parse filename patterns like 'DGPM 14/2026' or 'DES 23.2025'
                department = None
                circular_num = None
                year = None
                ref = extract_reference_from_text(fn + ' ' + text)
                if ref:
                    department, circular_num, year = ref
                # explicit guard: do not accept standalone 4000 values without a department code
                if circular_num and circular_num > 999:
                    circular_num = None
                    department = None

                # sender fallback
                sender = department if department else guess_sender(text)

                # normalize department to uppercase without surrounding whitespace
                if department:
                    try:
                        department = department.strip().upper()
                    except Exception:
                        pass
                    if department in FORBIDDEN_DEPARTMENTS:
                        department = None

                # derive year if still missing
                if year is None:
                    year_match = re.search(r"(19|20)\d{2}", fn)
                    if year_match:
                        year = int(year_match.group(0))
                    elif dates:
                        try:
                            year = int(dates[0][:4])
                        except Exception:
                            pass
                    else:
                        try:
                            year = datetime.fromtimestamp(mtime).year
                        except Exception:
                            year = None

                cur.execute('''
                    INSERT INTO circulars (filepath, filename, year, sender, deadlines, snippet, last_modified, department, circular_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(filepath) DO UPDATE SET
                      filename=excluded.filename,
                      year=excluded.year,
                      sender=excluded.sender,
                      deadlines=excluded.deadlines,
                      snippet=excluded.snippet,
                      last_modified=excluded.last_modified,
                      department=excluded.department,
                      circular_number=excluded.circular_number
                ''', (path, fn, year, sender, json.dumps(dates), snippet, mtime, department, circular_num))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # quick test run
    scan_folder()
    print('Scan complete')
