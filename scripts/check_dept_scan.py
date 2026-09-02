import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import sqlite3
from processor import scan_folder, DB_PATH, get_raw_folders
DB = r"data\circulars.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()
import time
print('Starting rescan (with retries)...')
for attempt in range(6):
    try:
        scan_folder(get_raw_folders(), DB_PATH)
        break
    except Exception as e:
        print('scan attempt', attempt+1, 'failed:', e)
        time.sleep(1.5)
else:
    print('scan failed after retries')
for dept in ('DFIN','IPS'):
    cur.execute('SELECT filename, filepath, year, department, circular_number FROM circulars WHERE department=? ORDER BY year DESC', (dept,))
    rows = cur.fetchall()
    print('\nDEPT', dept, 'found:', len(rows))
    for r in rows[:20]:
        print(r)
conn.close()
print('Done')
