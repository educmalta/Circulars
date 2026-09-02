import os, sys, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from processor import get_raw_folders

patterns = [re.compile(p, re.IGNORECASE) for p in [r'\bIPS\b', r'\bDFIN\b', r'10[\s/_\\-]?/??23', r'10[\s/_\\-]?/??2023', r'8[\s/_\\-]?/??25', r'8[\s/_\\-]?/??2025']]

roots = get_raw_folders()
print('Checking raw folders:', roots)
found = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for base, dirs, files in os.walk(root):
        for fn in files:
            path = os.path.join(base, fn)
            lower = fn.lower()
            try:
                # quick filename check
                if any(p.search(fn) for p in patterns):
                    found.append((path, 'filename'))
                    continue
                # check small text types directly
                if lower.endswith('.pdf'):
                    # try lightweight check by reading first KB bytes for text
                    try:
                        with open(path, 'rb') as f:
                            head = f.read(4096)
                        try:
                            txt = head.decode('utf-8', errors='ignore')
                        except Exception:
                            txt = ''
                        if any(p.search(txt) for p in patterns):
                            found.append((path, 'pdf-head'))
                            continue
                    except Exception:
                        pass
                elif lower.endswith('.docx'):
                    # treat docx as binary; include by filename only
                    pass
                elif lower.endswith('.eml') or lower.endswith('.msg'):
                    # include for further manual inspection
                    found.append((path, 'email-file'))
            except Exception:
                pass

import sys
print('\nMatches found:')
for p, kind in found:
    try:
        sys.stdout.buffer.write((f"{kind} : {p}\n").encode('utf-8'))
    except Exception:
        try:
            print(kind, ':', p.encode('utf-8', errors='ignore'))
        except Exception:
            pass

if not found:
    try:
        sys.stdout.buffer.write(b'No obvious candidates found. Consider checking Downloads or Outlook temporary paths manually.\n')
    except Exception:
        print('No obvious candidates found. Consider checking Downloads or Outlook temporary paths manually.')
