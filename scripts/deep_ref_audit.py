import os, re, json, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import get_raw_folders, text_from_pdf, text_from_docx

roots = get_raw_folders()
pattern = re.compile(r"\b([A-Z]{2,8}(?:\s+[A-Z]{2,8})*)[._/\\\s-]*?(\d{1,4})[._/\\\s-]*?((?:19|20)\d{2})\b")
results = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith(('.pdf', '.docx')):
                continue
            path = os.path.join(dirpath, fn)
            try:
                if fn.lower().endswith('.pdf'):
                    txt = text_from_pdf(path)
                else:
                    txt = text_from_docx(path)
            except Exception:
                txt = ''
            hay = (fn + '\n' + (txt or '')).upper()
            for m in pattern.finditer(hay):
                dept = m.group(1).strip()
                num = m.group(2)
                yr = m.group(3)
                results.append({'file': path, 'filename': fn, 'dept': dept, 'num': int(num), 'year': int(yr)})

out = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'deep_ref_audit.json'))
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2)
print('Wrote', out, 'with', len(results), 'matches')
