from processor import scan_folder, DB_PATH
import os, sqlite3
root = os.path.abspath(r'C:\Users\JeffreyZammit\OneDrive - Ministry for Education and Sport\Circulars')
print('Scanning', root)
scan_folder([root], DB_PATH)
con = sqlite3.connect(DB_PATH)
cur = con.cursor()
cur.execute('SELECT filename, department, circular_number, year FROM circulars WHERE filename LIKE ? OR filename LIKE ? OR department LIKE ? ORDER BY year DESC', ('%NLA%','%NLA %','NLA%'))
rows = cur.fetchall()
print('NLA rows:', rows)
cur.execute("SELECT filename, department, circular_number, year FROM circulars WHERE department LIKE 'NLA%' OR department LIKE 'DG%' OR department LIKE 'DES%' ORDER BY year DESC LIMIT 50")
print('sample:', cur.fetchall())
con.close()
