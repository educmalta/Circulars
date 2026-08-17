import os
from processor import RAW_FOLDERS, scan_folder, DB_PATH
import sqlite3

found = False
for r in RAW_FOLDERS:
    if os.path.isdir(r):
        for root, dirs, files in os.walk(r):
            for f in files:
                if 'international' in f.lower():
                    print('FOUND_ON_DISK:', os.path.join(root, f))
                    found = True

# Trigger a rescan
print('Running programmatic rescan...')
scan_folder(RAW_FOLDERS, DB_PATH)

# Query DB
conn = sqlite3.connect(DB_PATH, timeout=30)
cur = conn.cursor()
cur.execute("SELECT filename, department, year FROM circulars WHERE lower(filename) LIKE ?", ('%international%',))
rows = cur.fetchall()
if not rows:
    print('NO_MATCH_IN_DB')
else:
    for r in rows:
        print('DB_ROW:', r)
conn.close()

if not found:
    print('NO_MATCH_ON_DISK')
