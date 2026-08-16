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
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
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
            last_modified REAL
        )
    ''')
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
            sender = guess_sender(text)
            year = None
            # derive year from filename or dates or mtime
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
                INSERT INTO circulars (filepath, filename, year, sender, deadlines, snippet, last_modified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                  filename=excluded.filename,
                  year=excluded.year,
                  sender=excluded.sender,
                  deadlines=excluded.deadlines,
                  snippet=excluded.snippet,
                  last_modified=excluded.last_modified
            ''', (path, fn, year, sender, json.dumps(dates), snippet, mtime))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    # quick test run
    scan_folder()
    print('Scan complete')
