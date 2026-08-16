import os
import re
import json
import sqlite3
import time
from datetime import datetime
from dateutil import parser as dateparser
from docx import Document
from PyPDF2 import PdfReader

# Path to watch (change if needed)
RAW_FOLDER = r"C:\Users\JeffreyZammit\Desktop\AI Projects\Circulars\raw circulars"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "circulars.db")

DATE_REGEXES = [
    # numeric dates like 25/09/2026 or 2026-09-25
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    # month-name formats: 'September 25, 2026' or 'Sep 25 2026'
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    # day-month-year with month name and optional ordinal: '25 September 2026', '25th September 2026'
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
    # catch written forms like '25th Sep 2026'
    r"\b\d{1,2}(?:st|nd|rd|th)?[\s\-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[\s\-]\d{4}\b",
]
SENDER_KEYWORDS = ["DGPM", "Directorate", "DG", "Ministry", "Director" ]

def init_db(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
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


def find_dates(text):
    found = set()
    for rx in DATE_REGEXES:
        for m in re.findall(rx, text, flags=re.IGNORECASE):
            try:
                dt = dateparser.parse(m, dayfirst=True, fuzzy=True)
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


def scan_folder(folder=RAW_FOLDER, db_path=DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for root, _, files in os.walk(folder):
        for fn in files:
            lower = fn.lower()
            if not (lower.endswith('.docx') or lower.endswith('.pdf')):
                continue
            path = os.path.join(root, fn)
            try:
                mtime = os.path.getmtime(path)
            except Exception:
                continue
            cur.execute('SELECT last_modified FROM circulars WHERE filepath=?', (path,))
            row = cur.fetchone()
            if row and row[0] and row[0] >= mtime:
                continue
            if lower.endswith('.docx'):
                text = text_from_docx(path)
            else:
                text = text_from_pdf(path)
            snippet = (text[:800] + '...') if len(text) > 800 else text
            dates = find_dates(text)

            # Try to parse filename patterns like 'DGPM 14/2026' or 'DGPM_14-2026'
            department = None
            circular_num = None
            # common patterns: ABC 14/2026, ABC_14-2026, ABC-14_2026
            file_match = re.search(r"([A-Za-z]{2,10})[\._\-\s]*?(\d{1,4})[\/_\-]?(\d{4})", fn)
            if file_match:
                department = file_match.group(1).upper()
                try:
                    circular_num = int(file_match.group(2))
                except Exception:
                    circular_num = None
                try:
                    year = int(file_match.group(3))
                except Exception:
                    year = None
            else:
                # fallback: look inside text for patterns like DGPM 14/2026
                m2 = re.search(r"([A-Za-z]{2,10})\s+(\d{1,4})/(\d{4})", text)
                if m2:
                    department = m2.group(1).upper()
                    try:
                        circular_num = int(m2.group(2))
                    except Exception:
                        circular_num = None
                    try:
                        year = int(m2.group(3))
                    except Exception:
                        year = None

            # sender fallback
            sender = department if department else guess_sender(text)

            # if department still missing, try to infer from sender or text (look for uppercase acronyms like DGPM, DDLTS)
            if not department:
                # check sender for an uppercase token
                dept_match = re.search(r"\b([A-Z]{2,6})\b", sender or "")
                if not dept_match:
                    # check filename
                    dept_match = re.search(r"\b([A-Z]{2,6})\b", fn)
                if not dept_match:
                    # check text for common 'Ref', 'Referenza' patterns
                    dept_match = re.search(r"\bRefer(?:en[cz]a|ence)[:\s]*([A-Z]{2,6})\b", text, flags=re.IGNORECASE)
                if dept_match:
                    candidate = dept_match.group(1).upper()
                    # filter out short common words
                    if len(candidate) >= 2 and candidate.isalpha():
                        department = candidate

            # derive year if still missing
            if 'year' not in locals() or year is None:
                year = None
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
