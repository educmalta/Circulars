import sqlite3
DB='data/circulars.db'
conn=sqlite3.connect(DB)
cur=conn.cursor()
query = "SELECT filename, filepath, year, department, circular_number FROM circulars WHERE department='IPS' AND circular_number=10 AND year=2023"
cur.execute(query)
rows=cur.fetchall()
print('exact match rows:', len(rows))
for r in rows:
    print(repr(r))
# broad search
cur.execute("SELECT filename, filepath, year, department, circular_number FROM circulars WHERE department='IPS' AND (filename LIKE '%10%' OR filename LIKE '%10/23%' OR filename LIKE '%10/2023%')")
rows=cur.fetchall()
print('broad rows:', len(rows))
for r in rows:
    print(repr(r))
conn.close()
