import sqlite3, os
conn = sqlite3.connect(os.path.join('data', 'circulars.db'))
cur = conn.cursor()
cur.execute("SELECT department, circular_number, year FROM circulars ORDER BY year DESC, department")
print(cur.fetchall())
conn.close()
