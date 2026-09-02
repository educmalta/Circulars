import re, os, sqlite3
from processor import DB_PATH, text_from_pdf, extract_reference_from_text

p = r'C:\Users\JeffreyZammit\OneDrive - Ministry for Education and Sport\Circulars\2026\International Events  Circular.pdf'
if not os.path.exists(p):
    print('File not found:', p)
    raise SystemExit(1)

text = text_from_pdf(p)
# normalize common spacing artifacts: 'No . 02/2026' -> 'No. 02/2026', remove double spaces
nt = re.sub(r'No\s*\.\s*', 'No. ', text, flags=re.IGNORECASE)
nt = re.sub(r'\s{2,}', ' ', nt)
# also normalize 'IPS No . 02/2026' variants
nt = re.sub(r'([A-Z]{2,8})\s+No\s*\.\s*(\d{1,4})', lambda m: f"{m.group(1)} No. {m.group(2)}", nt)

ref = extract_reference_from_text(nt)
print('Reference found:', ref)
if not ref:
    # fallback: try looser regex
    m = re.search(r"\b([A-Z]{2,8})\b[^\d\n]{0,10}(\d{1,4})\s*[./-]\s*(\d{4})", nt)
    if m:
        ref = (m.group(1).upper(), int(m.group(2)), int(m.group(3)))
        print('Fallback ref:', ref)

if not ref:
    print('No reference parsed')
    raise SystemExit(0)

dept, num, year = ref
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
# update matching DB row by filepath
cur.execute('SELECT id FROM circulars WHERE filepath=?', (p,))
row = cur.fetchone()
if row:
    cur.execute('UPDATE circulars SET department=?, circular_number=?, year=? WHERE id=?', (dept, num, year, row[0]))
    print('Updated id', row[0])
else:
    # try filename
    fn = os.path.basename(p)
    cur.execute('SELECT id FROM circulars WHERE filename=?', (fn,))
    row2 = cur.fetchone()
    if row2:
        cur.execute('UPDATE circulars SET department=?, circular_number=?, year=? WHERE id=?', (dept, num, year, row2[0]))
        print('Updated id by filename', row2[0])
    else:
        mtime = os.path.getmtime(p)
        cur.execute('INSERT OR IGNORE INTO circulars (filepath, filename, year, sender, deadlines, snippet, last_modified, department, circular_number) VALUES (?,?,?,?,?,?,?,?,?)', (p, fn, int(year), dept, '[]', text[:800], mtime, dept, int(num)))
        print('Inserted new record')

conn.commit()
conn.close()
print('Done')
