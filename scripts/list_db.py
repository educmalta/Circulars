import sqlite3, os

db=r'C:\Users\JeffreyZammit\.copilot\repos\copilot-worktrees\Circulars\educmalta-probable-goggles\data\circulars.db'
if not os.path.exists(db):
    print('DB not found', db)
    raise SystemExit(1)
conn=sqlite3.connect(db)
cur=conn.cursor()
cur.execute("SELECT id, filename, filepath, year, department, circular_number FROM circulars ORDER BY year DESC, department")
rows=cur.fetchall()
for r in rows:
    print(r)
conn.close()
