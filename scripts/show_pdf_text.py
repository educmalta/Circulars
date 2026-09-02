import os
from processor import text_from_pdf

p = r'C:\Users\JeffreyZammit\OneDrive - Ministry for Education and Sport\Circulars\2026\International Events  Circular.pdf'
if not os.path.exists(p):
    print('File not found:', p)
    raise SystemExit(1)

text = text_from_pdf(p)
print('----BEGIN TEXT (first 4000 chars)----')
print(text[:4000])
print('----END TEXT----')
