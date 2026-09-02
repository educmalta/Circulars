import sqlite3, os

db=r'C:\Users\JeffreyZammit\.copilot\repos\copilot-worktrees\Circulars\educmalta-probable-goggles\data\circulars.db'
if not os.path.exists(db):
    print('DB not found:', db)
    raise SystemExit(1)
conn=sqlite3.connect(db)
cur=conn.cursor()
cur.execute("SELECT id, filename, filepath, year, department, deadlines FROM circulars WHERE filename LIKE '%International%'")
rows=cur.fetchall()
if not rows:
    print('No DB entries with International in filename')
else:
    for r in rows:
        print('ID:', r[0])
        print('Filename:', r[1])
        print('Path:', r[2])
        print('Year:', r[3], 'Dept:', r[4])
        print('Deadlines:', r[5])
        print('---')
conn.close()
