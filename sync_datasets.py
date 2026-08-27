#!/usr/bin/env python3
"""
Automated Data Synchronizer for Bosch Program Performance Dashboard
Downloads the latest live dataset directly from SharePoint export URL,
extracts sheet 'vm_rank_report' (VM rankings and AOM performance),
embeds the parsed structured dataset into index.html, and optionally
pushes updates to GitHub.
"""

import urllib.request
import http.cookiejar
from pyxlsb import open_workbook
import io
import json
import datetime
import os
import subprocess
import sys

SHAREPOINT_URL = "https://teamchannelplay-my.sharepoint.com/:x:/g/personal/bikash_roy1_channelplay_in/IQC5rvkJBy1dRYzVkAjdHFo6AaOSY7IoFmC7EVtBuJZzCAA?e=u5PYBz&download=1"

LOCAL_FALLBACK_PATHS = [
    "/Users/bikash/Library/CloudStorage/OneDrive-ChannelplayLimited/My Laptop/0 Active Projects/Bosch VM/Dashboard Data/Downloads/Bosch AOM's Report Aug'26.xlsb",
    "/Users/bikash/Downloads/Bosch AOM's Report Aug'26.xlsb",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Bosch AOM's Report Aug'26.xlsb")
]

def get_opener():
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPRedirectHandler
    )

def fetch_workbook():
    print(f"Fetching latest report from SharePoint...")
    opener = get_opener()
    req = urllib.request.Request(
        SHAREPOINT_URL,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    )
    try:
        data = opener.open(req, timeout=45).read()
        if len(data) > 5000:
            print(f"✓ Downloaded {len(data):,} bytes from SharePoint")
            return io.BytesIO(data)
    except Exception as e:
        print(f"SharePoint fetch failed: {e}. Checking local fallbacks...")

    for path in LOCAL_FALLBACK_PATHS:
        if os.path.exists(path):
            print(f"✓ Using local fallback: {path}")
            with open(path, "rb") as f:
                return io.BytesIO(f.read())

    raise FileNotFoundError("Could not download from SharePoint or locate local fallback file.")

def parse_dataset(wb_stream):
    with open_workbook(wb_stream) as wb:
        sheet_name = "vm_rank_report" if "vm_rank_report" in wb.sheets else wb.sheets[0]
        print(f"Reading sheet: {sheet_name}")
        with wb.get_sheet(sheet_name) as s:
            rows = list(s.rows())

    if len(rows) < 2:
        raise ValueError("Sheet does not contain enough rows.")

    # Header in row 1
    headers = [cell.v for cell in rows[1][:39]]
    vm_records = []
    
    for r in rows[2:]:
        vals = [cell.v for cell in r[:39]]
        if len(vals) > 3 and vals[0] and vals[3]:  # AOM Name and VM Name present
            rec = {}
            for idx, h in enumerate(headers):
                if h:
                    v = vals[idx] if idx < len(vals) else None
                    rec[h] = v
                    # Standardize productive visit headers
                    if "unproductive visit" in str(h).lower():
                        if "%" in str(h):
                            rec["Productive Visit %"] = v
                        else:
                            rec["Productive Visits"] = v
            vm_records.append(rec)

    # AOM performance summarized from mapped VM performance parameters
    aom_base_towns = {
        'Irfan Ali': 'Hyderabad',
        'Najeeb Hydrose': 'Cochin',
        'Pratik Kumar  Pandey': 'Delhi',
        'Pratik Kumar Pandey': 'Delhi',
        'Danish Khan': 'Mumbai'
    }
    aom_dict = {}
    for r in vm_records:
        aom = r.get('AOM Name')
        if not aom:
            continue
        if aom not in aom_dict:
            aom_dict[aom] = {
                'Aom Name': aom,
                'Base Town': aom_base_towns.get(aom, r.get('Base Town', '--')),
                'cov_tgt': 0, 'cov_ach': 0,
                'cata_tgt': 0, 'cata_ach': 0,
                'md_tgt': 0, 'md_ach': 0,
                'visits_ach': 0,
                'adh_sum': 0,
                'final_sum': 0,
                'count': 0
            }
        acc = aom_dict[aom]
        acc['count'] += 1
        acc['cov_tgt'] += float(r.get('Coverage Target') or 0)
        acc['cov_ach'] += float(r.get('Coverage Achievement') or 0)
        acc['cata_tgt'] += float(r.get('Cat A Target') or 0)
        acc['cata_ach'] += float(r.get('Cat A 1st visit') or 0)
        acc['md_tgt'] += float(r.get('Target Man-days') or 0)
        acc['md_ach'] += float(r.get('Man-days Achieved') or 0)
        acc['visits_ach'] += float(r.get('Visits Achieved') or 0)
        acc['adh_sum'] += float(r.get('First Visit Time Adherence (11:30 AM)') or 0)
        acc['final_sum'] += float(r.get('Final Achievement') or 0)

    aom_records = []
    for aom, acc in aom_dict.items():
        n = acc['count'] or 1
        cov_pct = acc['cov_ach'] / acc['cov_tgt'] if acc['cov_tgt'] else 0
        cata_pct = acc['cata_ach'] / acc['cata_tgt'] if acc['cata_tgt'] else 0
        md_pct = acc['md_ach'] / acc['md_tgt'] if acc['md_tgt'] else 0
        prod = acc['visits_ach'] / acc['md_ach'] if acc['md_ach'] else 0
        adh = acc['adh_sum'] / n
        final_ach = acc['final_sum'] / n
        aom_records.append({
            'Aom Name': aom,
            'Base Town': acc['Base Town'],
            'Coverage %': cov_pct,
            'Cat A Coverage': cata_pct,
            'Achi Mandays %': md_pct,
            'Productivity': prod,
            'First Visit Time Adherence (11:30 AM)': adh,
            'Final Achievement': final_ach
        })

    # Sort by Final Achievement descending and assign ranks
    aom_records.sort(key=lambda x: x['Final Achievement'], reverse=True)
    for idx, item in enumerate(aom_records):
        item['Rank'] = idx + 1

    return {
        "lastSynced": datetime.datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "timestamp": datetime.datetime.now().isoformat(),
        "totalVMs": len(vm_records),
        "totalAOMs": len(aom_records),
        "vms": vm_records,
        "aoms": aom_records
    }

def embed_into_html(data, html_file="index.html"):
    if not os.path.exists(html_file):
        print(f"HTML file {html_file} does not exist yet. Writing data.json instead.")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()

    compact_json = json.dumps(data, separators=(",", ":"))
    tag_start = '<script id="sample-data" type="application/json">'
    tag_end = '</script>'

    # Also write data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("✓ Saved data.json")

    idx1 = html.find(tag_start)
    if idx1 != -1:
        idx2 = html.find(tag_end, idx1)
        if idx2 != -1:
            html = html[:idx1 + len(tag_start)] + compact_json + html[idx2:]
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"✓ Embedded {data['totalVMs']} VMs and {data['totalAOMs']} AOMs into {html_file}")
            return

    # Also save data.json as a standalone file
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print("✓ Saved data.json")

def auto_push_to_github():
    print("\n--- Checking for GitHub updates ---")
    try:
        subprocess.run(["git", "add", "index.html", "data.json"], check=True)
        res = subprocess.run(["git", "diff", "--staged", "--quiet"])
        if res.returncode != 0:
            msg = f"chore(data): auto-sync latest live SharePoint dataset ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})"
            subprocess.run(["git", "commit", "-m", msg], check=True)
            subprocess.run(["git", "push", "origin", "main"], check=True)
            print("🚀 Successfully pushed updated datasets to GitHub main branch!")
        else:
            print("No data changes detected. Remote repository is already up-to-date.")
    except Exception as e:
        print("Note: Could not push to git automatically:", e)

def main():
    print("=== Bosch VM Dashboard: Data Synchronizer ===")
    stream = fetch_workbook()
    dataset = parse_dataset(stream)
    print(f"Successfully parsed: {dataset['totalVMs']} VMs, {dataset['totalAOMs']} AOMs")
    embed_into_html(dataset, "index.html")

    if "--push" in sys.argv:
        auto_push_to_github()

if __name__ == "__main__":
    main()
