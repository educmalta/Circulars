import os, sqlite3
# Files to remove (as provided)
targets = [
    r"C:\Users\JeffreyZammit\Downloads\TaxStatementPrintout2023.pdf",
    r"C:\Users\JeffreyZammit\Downloads\sunar bikram form.pdf",
    r"C:\Users\JeffreyZammit\Downloads\Invoice_137846.pdf",
    r"C:\Users\JeffreyZammit\Downloads\Jessica Damico - 6Kg DP.pdf",
]
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = os.path.join(repo_root, 'data', 'circulars.db')
removed_files = []
failed_files = []
for p in targets:
    try:
        if os.path.exists(p):
            os.remove(p)
            removed_files.append(p)
        else:
            failed_files.append((p, 'not found'))
    except Exception as e:
        failed_files.append((p, str(e)))

# Remove DB rows referencing those filepaths or filenames
conn = sqlite3.connect(db_path)
cur = conn.cursor()
removed_db = []
for p in targets:
    try:
        cur.execute('SELECT id, filepath, filename FROM circulars WHERE filepath=? OR filename=?', (p, os.path.basename(p)))
        rows = cur.fetchall()
        for r in rows:
            cur.execute('DELETE FROM circulars WHERE id=?', (r[0],))
            removed_db.append((r[0], r[1] or r[2]))
    except Exception as e:
        failed_files.append((p, 'db error: '+str(e)))
conn.commit()
conn.close()

print('files_deleted:', removed_files)
print('db_rows_deleted:', removed_db)
print('failures:', failed_files)
