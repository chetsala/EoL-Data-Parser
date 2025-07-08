import os
import time
import json
import threading
import sqlite3
import openpyxl
import requests
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw

# Set your paths here
SOURCE_DIRECTORY = r"C:\Users\chets\OneDrive - aquacal.com\Desktop\ChlorSync Powercenter Test Results"
SHAREPOINT_EXCEL_PATH = r"O:\Files\AutoPilot\Power Center EoL Database\parsed_log_data.xlsx"

# SQLite setup
conn = sqlite3.connect("local_cache.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT
)
""")
conn.commit()

def is_connected():
    try:
        requests.get('https://www.google.com', timeout=3)
        return True
    except:
        return False

def parse_log_file(file_path):
    data = {}
    with open(file_path, 'r') as file:
        for line in file:
            if ':' in line:
                key, value = line.split(':', 1)
                data[key.strip()] = value.strip()
    return data

def cache_locally(data):
    # Open a new connection in the current thread
    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()

    cursor.execute("DELETE FROM logs")
    for record in data:
        cursor.execute("INSERT INTO logs (data) VALUES (?)", (json.dumps(record),))

    conn.commit()
    conn.close()


def export_to_excel():
    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()

    cursor.execute("SELECT data FROM logs")
    rows = cursor.fetchall()
    conn.close()

    # Keep only rows where 'Failure Reason' == 'None'
    all_data = []
    for row in rows:
        record = json.loads(row[0])
        if record.get("Failure Reason", "").strip().lower() == "none":
            all_data.append(record)

    if not all_data:
        return  # Nothing to export

    wb = openpyxl.Workbook()
    ws = wb.active

    headers = set()
    for data in all_data:
        headers.update(data.keys())
    headers = list(headers)
    ws.append(headers)

    for data in all_data:
        row = [data.get(h, "") for h in headers]
        ws.append(row)

    wb.save(SHAREPOINT_EXCEL_PATH)




def parse_and_process():
    all_data = []
    for root, dirs, files in os.walk(SOURCE_DIRECTORY):
        for file in files:
            if file.endswith('.log'):
                file_path = os.path.join(root, file)
                parsed = parse_log_file(file_path)
                all_data.append(parsed)

    if all_data:
        cache_locally(all_data)
        export_to_excel()

def periodic_loop():
    while True:
        parse_and_process()
        time.sleep(20)  # Every 2 minutes

def setup_tray_icon():
    # Create a small tray icon image
    img = Image.new('RGB', (64, 64), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 54, 54], fill="blue")
    d.text((15, 20), "LOG", fill="white")

    icon = Icon("LogParser", img)

    def on_parse_now(icon, item):
        threading.Thread(target=parse_and_process, daemon=True).start()

    def on_quit(icon, item):
        icon.stop()

    icon.menu = Menu(
        item('Parse Now', on_parse_now),
        item('Quit', on_quit)
    )

    # Start periodic thread
    threading.Thread(target=periodic_loop, daemon=True).start()

    icon.run()

# Run the tray app
setup_tray_icon()
