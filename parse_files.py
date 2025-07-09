import os
import time
import json
import threading
import sqlite3
import requests
import csv
from pystray import Icon, MenuItem as item, Menu
from PIL import Image, ImageDraw

# === CONFIGURATION ===
SOURCE_DIRECTORY = r"C:\Users\chets\OneDrive - aquacal.com\Desktop\ChlorSync Powercenter Test Results"
SHAREPOINT_CSV_PATH = r"O:\Files\AutoPilot\Power Center EoL Database\parsed_log_data.csv"

# === SETUP DATABASE TO TRACK PARSED FILES ===
conn = sqlite3.connect("local_cache.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS processed_logs (
    file_path TEXT PRIMARY KEY
)
""")
conn.commit()
conn.close()

# === UTILITIES ===

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

def append_to_csv(new_data):
    if not new_data:
        return

    # Filter only records with "Failure Reason" == "None"
    filtered_data = [
        record for record in new_data
        if record.get("Failure Reason", "").strip().lower() == "none"
    ]

    if not filtered_data:
        return

    file_exists = os.path.isfile(SHAREPOINT_CSV_PATH)

    # Determine headers from all data
    all_headers = set()
    for record in filtered_data:
        all_headers.update(record.keys())
    headers = list(all_headers)

    # Write to CSV (append mode)
    with open(SHAREPOINT_CSV_PATH, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        for record in filtered_data:
            writer.writerow(record)

def parse_and_process():
    new_data = []
    conn = sqlite3.connect("local_cache.db")
    cursor = conn.cursor()

    for root, dirs, files in os.walk(SOURCE_DIRECTORY):
        for file in files:
            if file.endswith('.log'):
                file_path = os.path.join(root, file)

                cursor.execute("SELECT 1 FROM processed_logs WHERE file_path = ?", (file_path,))
                if cursor.fetchone():
                    continue

                parsed = parse_log_file(file_path)
                new_data.append(parsed)
                cursor.execute("INSERT OR IGNORE INTO processed_logs (file_path) VALUES (?)", (file_path,))

    for record in new_data:
        cursor.execute("INSERT INTO logs (data) VALUES (?)", (json.dumps(record),))

    conn.commit()
    conn.close()

    if new_data:
        append_to_csv(new_data)

def periodic_loop():
    while True:
        parse_and_process()
        time.sleep(120)  # Every 2 minutes

# === TRAY ICON ===

def setup_tray_icon():
    # Create tray icon
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

    threading.Thread(target=periodic_loop, daemon=True).start()
    icon.run()

# === START TRAY APP ===
setup_tray_icon()
