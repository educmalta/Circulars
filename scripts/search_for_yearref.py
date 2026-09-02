import os, sys, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import get_raw_folders, text_from_pdf, text_from_docx

roots = get_raw_folders()
print('Searching for 10/23 or 10/2023 in roots:', roots)
pattern = re.compile(r"\b10[\s/_\-]?(?:/)?(23|2023)\b", re.IGNORECASE)
ips_pat = re.compile(r"\bIPS\b", re.IGNORECASE)
found = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for base, dirs, files in os.walk(root):
        for fn in files:
            lower = fn.lower()
            if not (lower.endswith('.pdf') or lower.endswith('.docx')):
                continue
            path = os.path.join(base, fn)
            try:
                text = text_from_pdf(path) if lower.endswith('.pdf') else text_from_docx(path)
            except Exception:
                text = ''
            sample = (fn + ' ' + (text or ''))[:50000]
            if pattern.search(sample):
                has_ips = bool(ips_pat.search(sample))
                found.append((path, fn, has_ips))

print('\nMatches for 10/23 or 10/2023:')
import sys
for p, fn, has_ips in found:
    try:
        sys.stdout.buffer.write((f"{fn} | IPS_present={has_ips} -> {p}\n").encode('utf-8'))
    except Exception:
        print(fn, '| IPS_present=', has_ips, '->', p)
if not found:
    print('None found.')
