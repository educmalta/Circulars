import os
import threading
import time
import sqlite3
import json
from flask import Flask, render_template, redirect, url_for, jsonify
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # group by year and sender
    cur.execute("SELECT year, sender, COUNT(*) FROM circulars GROUP BY year, sender ORDER BY year DESC")
    groups = cur.fetchall()
    # full list
    cur.execute('SELECT id, filename, filepath, year, sender FROM circulars ORDER BY year DESC')
    rows = cur.fetchall()
    conn.close()
    grouped = []
    for y, s, c in groups:
        grouped.append({'year': y, 'sender': s, 'count': c})
    items = [{'id': r[0], 'filename': r[1], 'filepath': r[2], 'year': r[3], 'sender': r[4]} for r in rows]
    return render_template('dashboard.html', groups=grouped, items=items)


@app.route('/deadlines')
def deadlines():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, filename, filepath, deadlines FROM circulars ORDER BY year DESC')
    rows = cur.fetchall()
    conn.close()
    items = []
    for r in rows:
        deadlines = []
        try:
            deadlines = json.loads(r[3]) if r[3] else []
        except Exception:
            deadlines = []
        if deadlines:
            items.append({'id': r[0], 'filename': r[1], 'filepath': r[2], 'deadlines': deadlines})
    return render_template('deadlines.html', items=items)


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
