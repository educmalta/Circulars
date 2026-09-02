import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import scan_folder, DB_PATH, get_raw_folders, text_from_pdf, text_from_docx, extract_reference_from_text
import sqlite3
folders = get_raw_folders()
print('Folders to scan:', folders)
scan_folder(folders, DB_PATH)
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
patterns = ['%DGPM%','%NLA%','%DES%','%DG PM%']
for p in patterns:
    cur.execute('SELECT filename, department, circular_number, year, filepath FROM circulars WHERE filename LIKE ? OR department LIKE ? ORDER BY year DESC', (p,p))
    rows = cur.fetchall()
    print(p, '->', len(rows), 'rows')
    for r in rows[:20]:
        print('  ', r)
# Specific exact NLA 65/2025 or DGPM 07/2026
cur.execute("SELECT filename, department, circular_number, year, filepath FROM circulars WHERE (department='NLA' AND circular_number=65 AND year=2025) OR (department='DGPM' AND circular_number=7 AND year=2026)")
rows = cur.fetchall()
print('Exact matches:', rows)

# If exact matches missing, scan raw folders for any file containing those tokens
targets = [('DGPM', '07', '2026'), ('NLA', '65', '2025')]
for dept, num_str, yr_str in targets:
    found = []
    for root in folders:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.lower().endswith(('.pdf', '.docx')):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    if fn.lower().endswith('.pdf'):
                        txt = text_from_pdf(path)
                    else:
                        txt = text_from_docx(path)
                except Exception:
                    txt = ''
                hay = (fn + '\n' + txt).upper()
                pattern1 = f"{dept} {num_str}/{yr_str}".upper()
                pattern2 = f"{dept} {num_str} {yr_str}".upper()
                pattern3 = f"{dept}/{num_str}/{yr_str}".upper()
                if pattern1 in hay or pattern2 in hay or pattern3 in hay:
                    found.append((path, fn))
    print(f"Search for {dept} {num_str}/{yr_str}: {len(found)} files")
    for f in found[:10]:
        print('  ', f)

# Show any files where deep_extract_reference finds department but numeric differs
cur = con.cursor()
cur.execute("SELECT filename, department, circular_number, year, filepath FROM circulars WHERE department IS NOT NULL ORDER BY year DESC LIMIT 200")
rows = cur.fetchall()
mismatches = [r for r in rows if r[1] is not None and (int(r[2])>999 or r[3] is None)]
print('Sample rows with possible parsing issues (>999 num or missing year):', len(mismatches))
for r in rows[:20]:
    print('  ', r)
con.close()
