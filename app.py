import os
import threading
import time
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, jsonify, request
from dateutil import parser as dateparser
from processor import scan_folder, DB_PATH, RAW_FOLDER, init_db

app = Flask(__name__)

# ensure DB exists
init_db(DB_PATH)

SCAN_INTERVAL = 30  # seconds


def background_scanner():
    while True:
        try:
            scan_folder(RAW_FOLDER, DB_PATH)
        except Exception as e:
            print('Scan error:', e)
        time.sleep(SCAN_INTERVAL)


@app.route('/')
def index():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    selected_year = request.args.get('year')
    selected_dept = request.args.get('department')
    conn = sqlite3.connect(DB_PATH)
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

    # full list with same filters
    cur.execute(f'SELECT id, filename, filepath, year, sender, department, circular_number FROM circulars {where_sql} ORDER BY year DESC', params)
    rows = cur.fetchall()

    conn.close()
    grouped = []
    for y, s, c in groups:
        grouped.append({'year': y, 'sender': s, 'count': c})
    items = [{'id': r[0], 'filename': r[1], 'filepath': r[2], 'year': r[3], 'sender': r[4], 'department': r[5], 'circular_number': r[6]} for r in rows]
    return render_template('dashboard.html', groups=grouped, items=items, years=years, departments=departments, selected_year=selected_year, selected_dept=selected_dept)


@app.route('/deadlines')
def deadlines():
    selected_year = request.args.get('year')
    selected_dept = request.args.get('department')
    conn = sqlite3.connect(DB_PATH)
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
        # choose the nearest upcoming date, else the most recent past
        future = sorted([p for p in parsed if p >= now])
        if future:
            best = future[0]
        else:
            best = sorted(parsed, reverse=True)[0]
        # compute distance for sorting
        delta = (best - now).days
        # use absolute distance for sorting magnitude but keep sign to prefer upcoming
        items.append({'id': r[0], 'filename': r[1], 'filepath': r[2], 'best_deadline': best.isoformat(), 'best_deadline_display': best.strftime('%d %b %Y'), 'days_distance': abs(delta), 'days_until': delta})
    # sort by upcoming first (negative distances mean past); prefer soonest upcoming then closest past
    items.sort(key=lambda x: (x['days_until'] < 0, abs(x['days_until']), x['best_deadline']))
    return render_template('deadlines.html', items=items, years=years, departments=departments)


@app.route('/rescan')
def rescan():
    try:
        scan_folder(RAW_FOLDER, DB_PATH)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


if __name__ == '__main__':
    # start background scanner thread
    t = threading.Thread(target=background_scanner, daemon=True)
    t.start()
    app.run(host='127.0.0.1', port=5000, debug=True)
