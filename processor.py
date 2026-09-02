import os
import re
import json
import sqlite3
import threading
import time
from datetime import datetime
from dateutil import parser as dateparser
from docx import Document
from PyPDF2 import PdfReader

# Primary watch folder(s). These can include a synced OneDrive / SharePoint folder.
DEFAULT_RAW_FOLDER = r"C:\Users\JeffreyZammit\Desktop\AI Projects\Circulars\raw circulars"


def get_raw_folders():
    """Return ONLY the explicitly approved local folder(s):
    - Desktop raw circulars folder
    - Local OneDrive 'Ministry for Education and Sport\Circulars' folder
    Environment variable CIRCULAR_RAW_FOLDERS may override, but only approved roots are used.
    """
    configured = []
    # allow environment override but validate entries against approved set
    raw_value = os.environ.get('CIRCULAR_RAW_FOLDERS')
    if raw_value:
        for part in re.split(r'[;\n,]', raw_value):
            p = part.strip()
            if p:
                configured.append(p)
    # ensure the desktop raw folder is present
    if DEFAULT_RAW_FOLDER and DEFAULT_RAW_FOLDER not in configured:
        configured.append(DEFAULT_RAW_FOLDER)
    # include local sharepoint download target (kept but optional)
    repo_root = os.path.dirname(__file__)
    sp_local = os.path.join(repo_root, 'sharepoint_downloads', 'Circulars_2026')
    if sp_local not in configured:
        configured.append(sp_local)
    # add user-requested OneDrive path (Ministry for Education and Sport)
    user_home = os.path.expanduser('~')
    onedrive_ministry = os.path.join(user_home, 'OneDrive - Ministry for Education and Sport', 'Circulars')
    if onedrive_ministry not in configured:
        configured.append(onedrive_ministry)
    # also include the user's Downloads folder to catch email attachments saved locally
    downloads = os.path.join(user_home, 'Downloads')
    if downloads not in configured:
        configured.append(downloads)

    # filter out non-existing entries but return normalized absolute paths
    out = []
    for p in configured:
        try:
            ap = os.path.abspath(os.path.expanduser(p))
            out.append(ap)
        except Exception:
            pass
    # unique preserve order
    seen = set()
    final = []
    for p in out:
        if p and p not in seen:
            final.append(p)
            seen.add(p)

    # Keep authoritative roots if they exist; order: desktop raw, OneDrive ministry, Downloads
    allowed = []
    desktop = os.path.abspath(os.path.expanduser(DEFAULT_RAW_FOLDER)) if DEFAULT_RAW_FOLDER else None
    if desktop and desktop in final:
        allowed.append(desktop)
    onedrive_min = os.path.abspath(os.path.expanduser(os.path.join(user_home, 'OneDrive - Ministry for Education and Sport', 'Circulars')))
    if onedrive_min and onedrive_min in final:
        allowed.append(onedrive_min)
    if downloads and downloads in final and downloads not in allowed:
        allowed.append(downloads)
    # fallback: if none exist, return whatever final resolved
    return allowed if allowed else final


# helper to validate filenames: must start with DEPT NUM[._/- or space]YEAR e.g. DSVP 01/2026 or RSIRD 04_2026_EN
FILENAME_PATTERN = re.compile(r"^\s*(?:[A-Z]{2,8}(?:\s+[A-Z]{2,8})*)[._/\-\s]*\d{1,4}[._/\-\s]*\d{4}", re.IGNORECASE)


def parse_filename_reference(filename):
    name = os.path.splitext(filename)[0]
    # Accept multi-token uppercase departments like 'DG DES' or 'NLA' but require uppercase tokens
    match = re.search(r"\b((?:[A-Z]{2,8}(?:\s+[A-Z]{2,8})*))[._/\-\s]*?(?:No\s*\.?\s*)?(\d{1,4})[._/\-\s]*?(\d{4})\b", name)
    if not match:
        return None
    dept_raw = match.group(1)
    if any(c.islower() for c in dept_raw):
        return None
    department = dept_raw.upper().strip()
    number = int(match.group(2))
    year = int(match.group(3))
    if number <= 9999 and year >= 2000:
        return department, number, year
    return None


def is_allowed_filename(filename):
    """Return True if filename starts with Dept + number + separator + year (e.g., DSVP 01/2026 or RSIRD 04_2026_EN)"""
    name = os.path.splitext(filename)[0]
    return bool(FILENAME_PATTERN.match(name)) or parse_filename_reference(filename) is not None



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

MONTH_LITERAL = "Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December"
DATE_REGEXES = [
    # numeric dates like 25/09/2026 or 2026-09-25
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
    # weekday + date, e.g. 'Friday 28th August 2026'
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|January|Feb|February|Mar|March|Apr|April|May|Jun|June|Jul|July|Aug|August|Sep|Sept|September|Oct|October|Nov|November|Dec|December)[a-z]*\s+\d{4}\b",
    # month-name formats: 'September 25, 2026' or 'Sep 25 2026'
    rf"\b(?:{MONTH_LITERAL})[a-z]*\s+\d{{1,2}},?\s*\d{{4}}\b",
    # day-month-year with month name and optional ordinal
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTH_LITERAL})[a-z]*\s*\d{{4}}\b",
    # catch written forms like '25th Sep 2026' with separators
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?[\s\-](?:{MONTH_LITERAL})[a-z]*[\s\-]\d{{4}}\b",
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


def is_maltese_filename(filename):
    """Check filename for obvious Maltese-language indicators. Prefer filename-based detection over body text."""
    if not filename:
        return False
    lower = filename.lower()
    maltese_indicators = ['talbiet', 'għall', 'għas', 'settembru', 'diċembru', 'awwissu', 'novembru', 'ġunju', 'mejju', 'marzu', 'frar', 'jannar', 'Ġ', 'ċ', 'ż', 'ħ', 'għ']
    for token in maltese_indicators:
        if token in lower:
            return True
    return False


def is_maltese_text(text):
    """Detect if text is Maltese by looking for genuine Maltese-specific characters or words."""
    if not text:
        return False
    if re.search(r'(?:Ġ|ġ|Ċ|ċ|Ż|ż|ħ|għ)', text):
        return True
    lowered = text.lower()
    maltese_indicators = ['għall', 'għas', 'tal-', 'tal ', 'talb', 'talbiet', 'settembru', 'mejju', 'diċembru', 'ġunju', 'awwissu', 'ottubru']
    for w in maltese_indicators:
        if w in lowered:
            return True
    return False


def find_dates(text):
    # pre-clean: remove spaces inside digit groups (e.g., '202 6' -> '2026') to handle PDF extraction artifacts
    if not text:
        return []
    cleaned = re.sub(r'(?<=\d)\s+(?=\d)', '', text)
    lowered = cleaned.lower()
    deadline_keywords = [
        'deadline', 'not later than', 'latest date', 'latest by', 'must be received by',
        'submitted by', 'submit by', 'to be submitted by', 'to be received by',
        'application closing date', 'closing date', 'reply by', 'date of submission',
        'submission date', 'by end of', 'before', 'forwarded by', 'by no later than', 'no later than', 'closing date is'
    ]
    issue_keywords = ['date:', 'issued on', 'issue date', 'date of issue', 'circular date', 'publication date', 'issued:']
    all_matches = []
    seen = set()

    for rx in DATE_REGEXES:
        for match in re.finditer(rx, cleaned, flags=re.IGNORECASE):
            s = match.group(0)
            s = s.replace('\u2019', "'") if '\u2019' in s else s
            s = _replace_maltese_months(s)
            try:
                dt = dateparser.parse(s, dayfirst=True, fuzzy=True)
            except Exception:
                continue
            if not dt:
                continue
            # normalize to date object
            dt_date = dt.date()
            iso = dt_date.isoformat()
            if iso in seen:
                continue
            seen.add(iso)
            pos = match.start()
            window_start = max(0, pos - 180)
            window_end = min(len(cleaned), pos + len(match.group(0)) + 220)
            window = lowered[window_start:window_end]
            is_deadline = any(k in window for k in deadline_keywords)
            is_issue = any(k in window for k in issue_keywords)
            all_matches.append((dt_date, is_deadline, is_issue))

    # Prefer explicit deadline mentions and exclude obvious issue/publication dates.
    deadline_dates = sorted({d for d, is_deadline, is_issue in all_matches if is_deadline and not is_issue})
    if deadline_dates:
        # return ISO strings sorted ascending (soonest first)
        return [d.isoformat() for d in deadline_dates]

    # fallback: accept dates that are not marked as issue/publication and return sorted ascending
    fallback = sorted({d for d, is_deadline, is_issue in all_matches if not is_issue})
    if fallback:
        return [d.isoformat() for d in fallback]

    # as last resort return all discovered dates (ascending)
    all_dates = sorted({d for d, _, _ in all_matches})
    return [d.isoformat() for d in all_dates]


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


def deep_extract_reference(text):
    """Aggressively find department-number-year sequences anywhere in the text, tolerating non-ASCII prefixes.
    Matches multi-token uppercase departments like 'DG DES', 'DGPM', 'NLA' followed by number and year."""
    if not text:
        return None
    # Normalize spacing
    try:
        s = ' '.join(text.split())
    except Exception:
        s = text
    # Look for patterns like 'DG DES 24/2026' or 'NLA 43 June 2026'
    # First try strict numeric year
    patt = re.compile(r"([A-Z]{2,8}(?:\s+[A-Z]{2,8})*)[._/\-\s]*?(?:No\s*\.?\s*)?(\d{1,4})[._/\-\s]*?(\d{4})")
    m = patt.search(s)
    if m:
        dept_raw = m.group(1)
        # ensure matched tokens are uppercase in original
        if any(c.islower() for c in dept_raw):
            pass
        else:
            dept = dept_raw.upper().strip()
            num = int(m.group(2))
            yr = int(m.group(3))
            if num <= 9999 and yr >= 2000:
                return dept, num, yr
    # Fallback: department + number + month/year (e.g., 'NLA 43 June 2026')
    patt2 = re.compile(r"([A-Z]{2,8}(?:\s+[A-Z]{2,8})*)[._/\-\s]+(\d{1,4})\s+([A-Za-z]{3,}\s+\d{4})")
    m2 = patt2.search(s)
    if m2:
        dept_raw = m2.group(1)
        if any(c.islower() for c in dept_raw):
            pass
        else:
            dept = dept_raw.upper().strip()
            num = int(m2.group(2))
            # try to extract year from group3
            yr_match = re.search(r"(19|20)\d{2}", m2.group(3))
            if yr_match:
                yr = int(yr_match.group(0))
                if num <= 9999 and yr >= 2000:
                    return dept, num, yr
    return None


def extract_reference_from_text(text):
    # Accept variations like 'IPS No. 02/2026', 'IPS No . 02/2026', 'DGPM 14 2026', 'Ref: DGPM 14/2026' and multi-token departments
    patterns = [
        r"\b(?:ref(?:er(?:en[cz]a|ence))?)\s*[:\-]?\s*(([A-Z]{2,8}(?:\s+[A-Z]{2,8})*))[._/\-\s]*?(?:No\s*\.?\s*)?(\d{1,4})[._/\-\s]*?(\d{4})",
        r"\b(([A-Z]{2,8}(?:\s+[A-Z]{2,8})*))[._/\-\s]*?(?:No\s*\.?\s*)?(\d{1,4})[._/\-\s]*?(\d{4})",
        r"\b(([A-Z]{2,8}(?:\s+[A-Z]{2,8})*))[._/\-\s]+No\s*\.?\s*(\d{1,4})[._/\-\s]*?(\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            # Ensure the matched department tokens are all uppercase in the original text
            dept_text = match.group(1)
            if any(c.islower() for c in dept_text):
                continue
            department = dept_text.upper().strip()
            number = int(match.group(3))
            year = int(match.group(4))
            if number <= 9999 and year >= 2000:
                return department, number, year
    # fallback for file stems such as 'RSIRD 04_2026_EN'
    if isinstance(text, str):
        ref = parse_filename_reference(text)
        if ref:
            return ref
    # aggressive deep scan
    return deep_extract_reference(text)



SCAN_LOCK = threading.Lock()


def scan_folder(folder=None, db_path=DB_PATH):
    with SCAN_LOCK:
        init_db(db_path)
        conn = sqlite3.connect(db_path, timeout=60)
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
                    # only accept PDF/DOCX
                    if not (lower.endswith('.docx') or lower.endswith('.pdf')):
                        continue
                    path = os.path.join(root, fn)
                    try:
                        mtime = os.path.getmtime(path)
                    except Exception:
                        continue

                    # Read text early so we can accept files where the content contains a department ref
                    if lower.endswith('.docx'):
                        text = text_from_docx(path)
                    else:
                        text = text_from_pdf(path)

                    # If filename doesn't match, allow the file only if content contains a valid reference like 'IPS 02/2026'
                    ref_from_content = extract_reference_from_text(fn + ' ' + text)
                    if not is_allowed_filename(fn) and not ref_from_content:
                        # skip unrelated attachments or exports
                        continue
                    if is_maltese_filename(fn):
                        continue

                    cur.execute('SELECT last_modified, deadlines FROM circulars WHERE filepath=?', (path,))
                    row = cur.fetchone()

                    snippet = (text[:800] + '...') if len(text) > 800 else text
                    dates = find_dates(text)

                    # Try to parse filename patterns like 'DGPM 14/2026' or 'DES 23.2025'
                    department = None
                    circular_num = None
                    year = None
                    ref = ref_from_content
                    if not ref:
                        ref = extract_reference_from_text(fn + ' ' + text)
                    if ref:
                        department, circular_num, year = ref

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

                    # If we have department, number, year, prefer single DB record per group.
                    if department and circular_num and year:
                        cur.execute('SELECT id, last_modified FROM circulars WHERE department=? AND circular_number=? AND year=?', (department, circular_num, year))
                        grp = cur.fetchone()
                        if grp:
                            existing_id, existing_mtime = grp[0], grp[1] or 0
                            # Remove any stale row that points at the same filepath before updating.
                            cur.execute('DELETE FROM circulars WHERE filepath=? AND id<>?', (path, existing_id))
                            # Recompute data on every rescan so corrected deadline parsing is reflected immediately.
                            cur.execute('''UPDATE circulars SET filepath=?, filename=?, year=?, sender=?, deadlines=?, snippet=?, last_modified=?, department=?, circular_number=? WHERE id=?''', (path, fn, year, sender, json.dumps(dates), snippet, mtime, department, circular_num, existing_id))
                            # remove any other records in the group (keep this updated one)
                            cur.execute('DELETE FROM circulars WHERE department=? AND circular_number=? AND year=? AND id<>?', (department, circular_num, year, existing_id))
                        else:
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
                            # after insert, remove other duplicates leaving the inserted row
                            cur.execute('SELECT id FROM circulars WHERE department=? AND circular_number=? AND year=?', (department, circular_num, year))
                            ids = [r[0] for r in cur.fetchall()]
                            if len(ids) > 1:
                                # keep the most recent id
                                cur.execute('SELECT id FROM circulars WHERE department=? AND circular_number=? AND year=? ORDER BY last_modified DESC LIMIT 1', (department, circular_num, year))
                                keep = cur.fetchone()[0]
                                cur.execute('DELETE FROM circulars WHERE department=? AND circular_number=? AND year=? AND id<>?', (department, circular_num, year, keep))
                    else:
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

                    # finished processing this file; continue to next
                    continue


        # After walking all files/folders, cleanup DB and close connection
        _cleanup_db(cur, folder_list)
        conn.commit()
        conn.close()

# After scanning all files, perform DB cleanup when scan_folder is called normally
def _cleanup_db(cur, folder_list):
    approved_roots = [os.path.abspath(p) for p in (folder_list if isinstance(folder_list, list) else list(folder_list))]
    try:
        # Remove rows that are clearly not official circulars.
        cur.execute('SELECT id, filepath, filename, year, department, circular_number, snippet FROM circulars')
        rows = cur.fetchall()
        for rid, fp, fn, year, dept, num, snippet in rows:
            try:
                ap = os.path.abspath(fp)
            except Exception:
                ap = fp
            if not any(ap.startswith(root) for root in approved_roots):
                cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
                continue
            if not fn or os.path.splitext(fn)[1].lower() not in ('.pdf', '.docx'):
                cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
                continue
            if dept is None or num is None or year is None:
                cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
                continue
            if not is_allowed_filename(fn) and not extract_reference_from_text((fn or '') + ' ' + (snippet or '')):
                cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
                continue
            if is_maltese_filename(fn or ''):
                # Keep Maltese files only if there is no English counterpart for the same (department, number, year).
                # If the row lacks department/number/year, retain it for manual review.
                if dept and num and year:
                    cur.execute('SELECT id, snippet FROM circulars WHERE department=? AND circular_number=? AND year=?', (dept, num, year))
                    others = [r for r in cur.fetchall() if r[0] != rid]
                    deleted = False
                    for oid, osnip in others:
                        # if any other item in the group is not Maltese, it's safe to drop this Maltese file
                        if not is_maltese_text(osnip or ''):
                            cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
                            deleted = True
                            break
                    if deleted:
                        continue
                    # otherwise keep this Maltese record (no English counterpart found)
                else:
                    # keep files without clear dept/number/year so an admin can review them
                    pass
                
                        


        # Keep exactly one row for each (department, circular_number, year), preferring English / most recent.
        cur.execute('SELECT id, department, circular_number, year, snippet, last_modified FROM circulars ORDER BY year DESC, department ASC, circular_number ASC')
        rows = cur.fetchall()
        groups = {}
        for rid, dept, num, year, snippet, lm in rows:
            key = (dept, int(num), int(year))
            groups.setdefault(key, []).append({'id': rid, 'snippet': snippet or '', 'lm': float(lm or 0)})
        for key, items in groups.items():
            if len(items) <= 1:
                continue
            best = max(items, key=lambda x: (0 if not is_maltese_text(x['snippet']) else -1, x['lm']))
            for item in items:
                if item['id'] != best['id']:
                    cur.execute('DELETE FROM circulars WHERE id=?', (item['id'],))
    except Exception:
        pass

if __name__ == '__main__':
    # quick test run
    scan_folder()
    # perform cleanup of DB entries after scanning default roots
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    _cleanup_db(cur, RAW_FOLDERS)
    conn.commit()
    conn.close()
    print('Scan complete')
