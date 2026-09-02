import sqlite3
from datetime import datetime

db=r'C:\Users\JeffreyZammit\.copilot\repos\copilot-worktrees\Circulars\educmalta-probable-goggles\data\circulars.db'
conn=sqlite3.connect(db)
cur=conn.cursor()
cur.execute("SELECT id, filepath, filename, last_modified, snippet FROM circulars WHERE department='DDLTS' AND circular_number=17")
rows=cur.fetchall()
for r in rows:
    rid, fp, fn, lm, sn = r
    print('ID', rid)
    print('File:', fp)
    print('Filename:', fn)
    print('Last modified:', lm)
    print('Snippet sample:', (sn or '')[:400])
    print('---')
conn.close()
