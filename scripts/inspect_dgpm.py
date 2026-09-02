import sqlite3, os
from datetime import datetime

db=r'C:\Users\JeffreyZammit\.copilot\repos\copilot-worktrees\Circulars\educmalta-probable-goggles\data\circulars.db'
conn=sqlite3.connect(db)
cur=conn.cursor()
cur.execute("SELECT id, filepath, filename, last_modified, snippet FROM circulars WHERE department='DGPM' AND circular_number=14")
rows=cur.fetchall()
for r in rows:
    rid, fp, fn, lm, sn = r
    print('ID', rid)
    print('File:', fp)
    print('Filename:', fn)
    print('Last modified:', lm, '=>', datetime.fromtimestamp(lm))
    print('Snippet sample:', (sn or '')[:300])
    print('---')
conn.close()
