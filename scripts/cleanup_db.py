import os, sqlite3
repo = os.getcwd()
db = os.path.join(repo, 'data', 'circulars.db')
allowed = [
    os.path.abspath(r"C:\Users\JeffreyZammit\Desktop\AI Projects\Circulars\raw circulars"),
    os.path.abspath(os.path.join(repo, 'sharepoint_downloads', 'Circulars_2026'))
]
print('DB:', db)
print('Allowed roots:')
for a in allowed:
    print(' -', a)

if not os.path.exists(db):
    print('No DB found')
    raise SystemExit(0)

bak = db + '.autocleanup.bak'
print('Backing up DB ->', bak)
import shutil
shutil.copy2(db, bak)

conn = sqlite3.connect(db, timeout=30)
cur = conn.cursor()
cur.execute('SELECT id, filepath FROM circulars')
rows = cur.fetchall()
removed = []
for rid, fp in rows:
    if not fp:
        removed.append((rid, fp))
        cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
        continue
    fpl = os.path.abspath(fp)
    if not any(fpl.startswith(a) for a in allowed):
        removed.append((rid, fp))
        cur.execute('DELETE FROM circulars WHERE id=?', (rid,))
conn.commit()
conn.close()
print('Removed count from DB:', len(removed))
for r in removed[:50]:
    print('REMOVED:', r)
print('Cleanup done. DB backup at', bak)
