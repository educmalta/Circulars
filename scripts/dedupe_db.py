"""Deduplicate circulars in DB by (department, circular_number, year).
Keeps the preferred record per group: prefer non-Maltese (English) and the most recent last_modified.
Deletes other rows from the circulars table (DB-only, no file deletions).
"""
import sqlite3, os
from processor import DB_PATH, is_maltese_text

db = DB_PATH
if not os.path.exists(db):
    print('DB not found', db)
    raise SystemExit(1)

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT id, filepath, filename, year, department, circular_number, snippet, last_modified FROM circulars")
rows = cur.fetchall()

# Group
groups = {}
for r in rows:
    rid, fp, fn, year, dept, num, snippet, lm = r
    if not (dept and num and year):
        continue
    key = (dept, int(num), int(year))
    groups.setdefault(key, []).append({'id': rid, 'filepath': fp, 'filename': fn, 'snippet': snippet or '', 'last_modified': lm or 0})

deleted = 0
for key, items in groups.items():
    # pick preferred: non-maltese preferred, then max last_modified
    for it in items:
        it['maltese'] = is_maltese_text(it['snippet'])
    # prefer items where maltese==False
    non_maltese = [it for it in items if not it['maltese']]
    candidates = non_maltese if non_maltese else items
    best = max(candidates, key=lambda x: x.get('last_modified') or 0)
    # delete others
    for it in items:
        if it['id'] == best['id']:
            continue
        cur.execute('DELETE FROM circulars WHERE id=?', (it['id'],))
        deleted += 1

conn.commit()
conn.close()
print('Dedup complete. Deleted', deleted, 'rows')