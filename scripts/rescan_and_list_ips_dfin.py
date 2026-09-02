import sqlite3
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import scan_folder, DB_PATH, get_raw_folders
DB='data/circulars.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
print('Rescanning with possible OCR (if lib present)')
try:
    scan_folder(get_raw_folders(), DB_PATH)
except Exception as e:
    print('rescan error', e)

for dept in ('IPS','DFIN'):
    cur.execute("SELECT filename, filepath, year, department, circular_number FROM circulars WHERE department=? ORDER BY year DESC", (dept,))
    rows=cur.fetchall()
    print('\nDEPT',dept,'rows:',len(rows))
    for r in rows:
        try:
            sys.stdout.buffer.write((repr(r)+'\n').encode('utf-8'))
        except Exception:
            print('ERR', r[0])
conn.close()
print('Done')
