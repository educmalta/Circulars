import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import get_raw_folders, text_from_pdf, text_from_docx, extract_reference_from_text

roots = get_raw_folders()
print('Inspecting roots:', roots)
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
            text = ''
            try:
                if lower.endswith('.pdf'):
                    text = text_from_pdf(path)
                else:
                    text = text_from_docx(path)
            except Exception as e:
                text = ''
            ref = extract_reference_from_text(fn + ' ' + (text or ''))
            if ref:
                dept, num, yr = ref
                found.append((path, fn, dept, num, yr))
            else:
                # also look for bare patterns like '10/23' or '8/25'
                sample = (fn + ' ' + (text or ''))[:20000]
                import re
                if re.search(r'\bIPS\b', sample) and re.search(r'10[\s/_\-]?/??(23|2023)\b', sample):
                    found.append((path, fn, 'IPS', 10, 2023))
                if re.search(r'\bDFIN\b', sample) and re.search(r'8[\s/_\-]?/??(25|2025)\b', sample):
                    found.append((path, fn, 'DFIN', 8, 2025))

print('\nDeep search results:')
if not found:
    print('No references found in scanned files')
else:
    for p, fn, dept, num, yr in found:
        try:
            sys.stdout.buffer.write((f"{dept} {num}/{yr} -> {p}\n").encode('utf-8'))
        except Exception:
            print(dept, num, yr, '->', p)
