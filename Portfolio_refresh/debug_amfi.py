"""
debug_amfi.py — Run this ONCE to print raw AMFI data so we can fix the parser.
Copy the output and share it — we will use it to find correct scheme codes.
"""
import urllib.request, datetime

def fetch(date_str):
    url = (f"https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
           f"?frmdt={date_str}&todt={date_str}")
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='ignore')

# Get last business day
d = datetime.date.today()
while d.weekday() >= 5:
    d -= datetime.timedelta(days=1)
date_str = d.strftime("%d-%b-%Y")

print(f"Fetching {date_str}...")
text = fetch(date_str)
lines = [l for l in text.splitlines() if l.strip()]
print(f"Total lines: {len(lines)}")
print("\n=== FIRST 30 LINES (raw) ===")
for l in lines[:30]:
    print(repr(l))

print("\n=== SEARCH FOR 'SBI SMALL CAP' ===")
for l in lines:
    if 'SBI' in l.upper() and 'SMALL' in l.upper():
        print(repr(l))

print("\n=== SEARCH FOR 'BANDHAN FLEXI' ===")
for l in lines:
    if 'BANDHAN' in l.upper() and 'FLEXI' in l.upper():
        print(repr(l))

print("\n=== SEARCH FOR 'PARAG PARIKH' ===")
for l in lines:
    if 'PARAG' in l.upper():
        print(repr(l))

print("\n=== SEARCH FOR 'HDFC MID' ===")
for l in lines:
    if 'HDFC' in l.upper() and 'MID' in l.upper() and 'DIRECT' in l.upper():
        print(repr(l))