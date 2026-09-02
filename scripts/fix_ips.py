"""Locate International Events PDF(s), extract reference like 'IPS No. 02/2026' from content and update DB record to set department, circular_number, year accordingly.
"""
import sqlite3, os
from processor import DB_PATH, text_from_pdf, extract_reference_from_text

search_paths = [
    r'C:\Users\JeffreyZammit\OneDrive - Ministry for Education and Sport\Circulars',
    r'C:\Users\JeffreyZammit\Desktop\AI Projects\Circulars\raw circulars'
]

found = []
for base in search_paths:
    for root, _, files in os.walk(base):
        for fn in files:
            if 'International' in fn and fn.lower().endswith('.pdf'):
                found.append(os.path.join(root, fn))

if not found:
    print('No International PDFs found in approved roots')
    raise SystemExit(0)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
updated = 0
for path in found:
    print('Parsing', path)
    try:
        text = text_from_pdf(path)
    except Exception as e:
        print('Failed to read', path, e)
        continue
    ref = extract_reference_from_text(text)
    if not ref:
        print('No reference found in', path)
        continue
    dept, num, year = ref
    print('Found ref:', dept, num, year)
    # find DB entry with this filepath (or filename match)
    cur.execute('SELECT id FROM circulars WHERE filepath=?', (path,))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE circulars SET department=?, circular_number=?, year=? WHERE id=?', (dept, num, year, row[0]))
        updated += 1
        print('Updated DB id', row[0])
    else:
        # try filename match
        fn = os.path.basename(path)
        cur.execute('SELECT id FROM circulars WHERE filename=?', (fn,))
        row2 = cur.fetchone()
        if row2:
            cur.execute('UPDATE circulars SET department=?, circular_number=?, year=? WHERE id=?', (dept, num, year, row2[0]))
            updated += 1
            print('Updated DB id by filename', row2[0])
        else:
            # insert new record minimally
            mtime = os.path.getmtime(path)
            cur.execute('INSERT OR IGNORE INTO circulars (filepath, filename, year, sender, deadlines, snippet, last_modified, department, circular_number) VALUES (?,?,?,?,?,?,?,?,?)', (path, os.path.basename(path), int(year), dept, '[]', text[:800], mtime, dept, int(num)))
            if cur.rowcount:
                updated += 1
                print('Inserted new DB record for', path)

conn.commit()
conn.close()
print('Done, updated/inserted', updated, 'records')