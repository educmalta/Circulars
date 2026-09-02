import os, sqlite3, time
targets = [
    r"C:\Users\JeffreyZammit\Downloads\TaxStatementPrintout2023.pdf",
    r"C:\Users\JeffreyZammit\Downloads\sunar bikram form.pdf",
    r"C:\Users\JeffreyZammit\Downloads\Invoice_137846.pdf",
    r"C:\Users\JeffreyZammit\Downloads\Jessica Damico - 6Kg DP.pdf",
]
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(repo_root, 'data', 'circulars.db')
removed_db = []
errors = []
for attempt in range(5):
    try:
        conn = sqlite3.connect(db_path, timeout=30)
        cur = conn.cursor()
        for p in targets:
            cur.execute('SELECT id, filepath, filename FROM circulars WHERE filepath=? OR filename=?', (p, os.path.basename(p)))
            rows = cur.fetchall()
            for r in rows:
                cur.execute('DELETE FROM circulars WHERE id=?', (r[0],))
                removed_db.append((r[0], r[1] or r[2]))
        conn.commit()
        conn.close()
        break
    except Exception as e:
        errors.append(str(e))
        time.sleep(1 + attempt*2)

print('removed_db:', removed_db)
print('errors:', errors)
