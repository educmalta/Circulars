from processor import scan_folder, RAW_FOLDERS, DB_PATH
import sqlite3, time
print('Scanning', len(RAW_FOLDERS), 'roots...')
scan_folder(RAW_FOLDERS, DB_PATH)
now=time.time()
conn=sqlite3.connect(DB_PATH, timeout=30)
cur=conn.cursor()
cur.execute('SELECT filename, department, year, last_modified FROM circulars ORDER BY last_modified DESC LIMIT 30')
rows=cur.fetchall()
print('\nRecent files:')
for fn, dept, yr, lm in rows:
    try:
        ts=float(lm)
    except:
        ts=0
    age_hours=(now-ts)/3600 if ts>0 else None
    if age_hours is not None:
        print("{} | dept={} | year={} | age_hours={:.1f}".format(fn, dept, yr, age_hours))
    else:
        print("{} | dept={} | year={} | modified={}".format(fn, dept, yr, lm))
conn.close()
