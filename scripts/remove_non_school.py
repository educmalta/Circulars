import sqlite3, os
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'circulars.db')
conn = sqlite3.connect(DB)
cur = conn.cursor()
# filenames starting with these tokens (case-insensitive)
tokens = ['Tax', 'Sunar', 'Invoice', 'Jessica']
placeholders = ','.join('?' for _ in tokens)
# Find matches
cur.execute(f"SELECT id, filename, filepath FROM circulars")
rows = cur.fetchall()
removed = []
for rid, fn, fp in rows:
    if not fn:
        continue
    for t in tokens:
        if fn.lower().startswith(t.lower()):
            cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
            removed.append((rid, fn, fp))
            break
conn.commit()
conn.close()
print('Removed', len(removed), 'rows:')
for r in removed:
    print(' ', r)
