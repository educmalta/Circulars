import os
import threading
import time
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, jsonify, request, send_file, abort
from dateutil import parser as dateparser
from processor import scan_folder, DB_PATH, RAW_FOLDER, RAW_FOLDERS, init_db, is_maltese_filename, get_raw_folders


def file_url_for(local_path):
    try:
        return url_for('open_file', path=local_path, _external=False)
    except Exception:
        return '/open-file?path=' + local_path.replace('\\', '/')

app = Flask(__name__)

# ensure DB exists
init_db(DB_PATH)

SCAN_INTERVAL = 30  # seconds


def scan_with_retry():
    last_error = None
    for attempt in range(3):
        try:
            scan_folder(get_raw_folders(), DB_PATH)
            return
        except sqlite3.OperationalError as exc:
            last_error = exc
            if 'database is locked' not in str(exc).lower() or attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error


def background_scanner():
    while True:
        try:
            scan_with_retry()
        except Exception as e:
            print('Scan error:', e)
        time.sleep(SCAN_INTERVAL)


@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/open-file')
def open_file():
    local_path = request.args.get('path')
    if not local_path:
        abort(400)

    abs_path = os.path.abspath(os.path.expanduser(local_path))
    # Recompute approved roots at request time to avoid stale/import-time values
    allowed_roots = [os.path.abspath(root) for root in get_raw_folders()]
    if not any(abs_path == root or abs_path.startswith(root + os.sep) for root in allowed_roots):
        abort(403)
    if not os.path.isfile(abs_path):
        abort(404)
    return send_file(abs_path, as_attachment=False)


@app.route('/dashboard')
def dashboard():
    selected_year = request.args.get('year')
    selected_dept = request.args.get('department')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    # list available years and departments for selectors
    cur.execute('SELECT DISTINCT year FROM circulars WHERE year IS NOT NULL ORDER BY year DESC')
    years = [r[0] for r in cur.fetchall()]
    cur.execute('SELECT DISTINCT department FROM circulars WHERE department IS NOT NULL ORDER BY department')
    departments = [r[0] for r in cur.fetchall() if r[0]]

    filters = []
    where_clauses = []
    params = []
    if selected_year:
        where_clauses.append('year=?')
        params.append(int(selected_year))
    if selected_dept:
        where_clauses.append('department=?')
        params.append(selected_dept)

    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    # group by year and sender (apply filters)
    cur.execute(f"SELECT year, sender, COUNT(*) FROM circulars {where_sql} GROUP BY year, sender ORDER BY year DESC", params)
    groups = cur.fetchall()

    # full list with same filters (include snippet and last_modified to help dedupe and language detection)
    cur.execute(f'SELECT id, filename, filepath, year, sender, department, circular_number, snippet, last_modified FROM circulars {where_sql} ORDER BY year DESC, last_modified DESC', params)
    rows = cur.fetchall()

    conn.close()
    grouped = []
    for y, s, c in groups:
        grouped.append({'year': y, 'sender': s, 'count': c})

    # dedupe: keep one circular per (department, circular_number, year), prefer English (not Maltese) and latest modified
    seen = {}
    items = []
    for r in rows:
        rid, filename, filepath, year, sender, department, circular_number, snippet, last_modified = r
        key = (department, circular_number, year)
        # skip if department or circular_number missing (shouldn't happen because scanner restricts filenames)
        if not department or not circular_number or not year:
            continue
        # detect Maltese via filename; this is more reliable than body-text scanning.
        maltese = is_maltese_filename(filename or '')
        if key in seen:
            prev = seen[key]
            if prev.get('maltese') and not maltese:
                seen[key] = {'rid': rid, 'filename': filename, 'filepath': filepath, 'year': year, 'sender': sender, 'department': department, 'circular_number': circular_number, 'maltese': maltese, 'last_modified': last_modified}
        else:
            if maltese:
                continue
            seen[key] = {'rid': rid, 'filename': filename, 'filepath': filepath, 'year': year, 'sender': sender, 'department': department, 'circular_number': circular_number, 'maltese': maltese, 'last_modified': last_modified}

    # collect items sorted by year desc then last_modified desc
    items = sorted([
        {
            'id': v['rid'],
            'filename': v['filename'],
            'filepath': v['filepath'],
            'filepath_url': file_url_for(v['filepath']),
            'year': v['year'],
            'sender': v['sender'],
            'department': v['department'],
            'circular_number': v['circular_number'],
        }
        for v in seen.values()
    ], key=lambda x: (-(x['year'] or 0), -int(x.get('circular_number') or 0)))
    return render_template('dashboard.html', groups=grouped, items=items, years=years, departments=departments, selected_year=selected_year, selected_dept=selected_dept)


@app.route('/deadlines')
def deadlines():
    selected_year = request.args.get('year')
    selected_dept = request.args.get('department')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    cur = conn.cursor()
    # lists for selectors
    cur.execute('SELECT DISTINCT year FROM circulars WHERE year IS NOT NULL ORDER BY year DESC')
    years = [r[0] for r in cur.fetchall()]
    cur.execute('SELECT DISTINCT department FROM circulars WHERE department IS NOT NULL ORDER BY department')
    departments = [r[0] for r in cur.fetchall() if r[0]]

    where_clauses = []
    params = []
    if selected_year:
        where_clauses.append('year=?')
        params.append(int(selected_year))
    if selected_dept:
        where_clauses.append('department=?')
        params.append(selected_dept)
    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    cur.execute(f'SELECT id, filename, filepath, deadlines FROM circulars {where_sql}', params)
    rows = cur.fetchall()
    conn.close()
    items = []
    now = datetime.now().date()
    for r in rows:
        raw = r[3]
        ds = []
        try:
            ds = json.loads(raw) if raw else []
        except Exception:
            ds = []
        parsed = []
        for d in ds:
            try:
                parsed.append(datetime.fromisoformat(d).date())
            except Exception:
                try:
                    parsed.append(dateparser.parse(d).date())
                except Exception:
                    pass
        if not parsed:
            continue
        # Only show valid future deadlines. Ignore issue dates and other non-deadline dates.
        future = sorted([p for p in parsed if p >= now])
        if not future:
            continue
        best = future[0]
        delta = (best - now).days
        items.append({
            'id': r[0],
            'filename': r[1],
            'filepath': r[2],
            'filepath_url': file_url_for(r[2]),
            'best_deadline': best.isoformat(),
            'best_deadline_display': best.strftime('%d %b %Y'),
            'days_distance': abs(delta),
            'days_until': delta,
        })
    items.sort(key=lambda x: x['best_deadline'])
    return render_template('deadlines.html', items=items, years=years, departments=departments)


@app.route('/rescan', methods=['GET', 'POST'])
def rescan():
    try:
        scan_with_retry()
    except Exception:
        pass
    return redirect(url_for('dashboard'))


@app.route('/api/rescan')
def api_rescan():
    try:
        scan_with_retry()
        conn = sqlite3.connect(DB_PATH, timeout=30)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM circulars')
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM circulars WHERE deadlines IS NOT NULL AND length(deadlines) > 2")
        with_deadlines = cur.fetchone()[0]
        cur.execute("SELECT department, COUNT(*) FROM circulars GROUP BY department")
        depts = { (r[0] if r[0] else 'Unknown'): r[1] for r in cur.fetchall() }
        conn.close()
        return jsonify({'status': 'ok', 'total': total, 'with_deadlines': with_deadlines, 'departments': depts})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# Optional: trigger a SharePoint/OneDrive remote sync into a local folder, then scan
try:
    from sharepoint_client import sync_sharepoint_folder
except Exception:
    sync_sharepoint_folder = None

@app.route('/sync_sharepoint', methods=['POST'])
def sync_sharepoint():
    if sync_sharepoint_folder is None:
        return jsonify({'status': 'error', 'error': 'sharepoint_client not available; install msal and requests'}), 500
    remote_path = request.form.get('remote_path') or request.args.get('remote_path')
    if not remote_path:
        return jsonify({'status': 'error', 'error': 'remote_path parameter required'}), 400
    # local target
    target_root = os.path.join(os.path.dirname(__file__), 'sharepoint_downloads')
    safe_name = remote_path.replace('/', '_').replace('\\', '_')
    local_target = os.path.join(target_root, safe_name)
    try:
        files = sync_sharepoint_folder(remote_path, local_target)
        # scan both the downloaded folder and the normal RAW_FOLDERS so items are recorded
        scan_folder([local_target] + RAW_FOLDERS, DB_PATH)
        return jsonify({'status': 'ok', 'downloaded': len(files), 'sample': files[:10]})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


if __name__ == '__main__':
    # start background scanner thread
    t = threading.Thread(target=background_scanner, daemon=True)
    t.start()
    app.run(host='127.0.0.1', port=5000, debug=True)
