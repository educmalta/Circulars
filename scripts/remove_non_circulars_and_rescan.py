import sqlite3
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import scan_folder, DB_PATH, get_raw_folders

DB = r"data\circulars.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

# filenames to remove
to_delete = [
    'Extension Solstice Residence - Apartment 19.docx',
    'Counting Staff - 2024_application-0084572M.pdf'
]
for fn in to_delete:
    cur.execute('DELETE FROM circulars WHERE filename=?', (fn,))
# also remove loose matches
cur.execute("DELETE FROM circulars WHERE filename LIKE 'Counting Staff%'")
conn.commit()
cur.execute('SELECT COUNT(*) FROM circulars')
print('total_before_rescan:', cur.fetchone()[0])

# perform rescan of configured raw folders
scan_folder(get_raw_folders(), DB_PATH)

cur.execute('SELECT COUNT(*) FROM circulars')
print('total_after_rescan:', cur.fetchone()[0])

cur.execute("SELECT filename, filepath FROM circulars WHERE filename LIKE 'Extension Solstice%' OR filename LIKE 'Counting Staff%'")
rows = cur.fetchall()
for r in rows:
    print('REMAINING:', r)

conn.close()
