import sqlite3
DB='data/circulars.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
cur.execute("SELECT filename, filepath, year, department, circular_number FROM circulars WHERE department='DFIN' ORDER BY year DESC")
rows=cur.fetchall()
print('rows_count=', len(rows))
import sys
for r in rows:
    try:
        sys.stdout.buffer.write((repr(r) + '\n').encode('utf-8'))
    except Exception:
        print('ENC_ERR', r[0])
conn.close()
