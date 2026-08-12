"""Extract FixForward datasets from DC ArcGIS APIs to CSVs for Foundry upload.
Output: ~/Desktop/GitHub/fixforward-data/"""
import json, urllib.request, urllib.parse, csv, os, sys

OUT = os.path.expanduser("~/Desktop/GitHub/fixforward-data")
os.makedirs(OUT, exist_ok=True)
BASE = "https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA"

def q(url, params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=120) as r:
        return json.load(r)

def fetch_all(url, where="1=1", fields="*"):
    out, offset = [], 0
    while True:
        d = q(url + "/query", {"where": where, "outFields": fields, "returnGeometry": "false",
                               "f": "json", "resultOffset": offset, "resultRecordCount": 2000})
        feats = d.get("features", [])
        out += [f["attributes"] for f in feats]
        if not d.get("exceededTransferLimit") or not feats:
            return out
        offset += len(feats)
        print(f"    ...{offset}", flush=True)

def write_csv(rows, name):
    if not rows:
        print(f"  !! {name}: NO ROWS"); return
    cols = list(rows[0].keys())
    for r in rows[1:50]:
        for k in r:
            if k not in cols: cols.append(k)
    path = os.path.join(OUT, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"  OK {name}: {len(rows)} rows, {os.path.getsize(path)//1024} KB", flush=True)

# 1. 311 signal reports 2023-2026
SR_FIELDS = ("SERVICEREQUESTID,SERVICECODE,SERVICECODEDESCRIPTION,SERVICETYPECODEDESCRIPTION,"
             "ORGANIZATIONACRONYM,SERVICECALLCOUNT,ADDDATE,RESOLUTIONDATE,SERVICEDUEDATE,"
             "SERVICEORDERDATE,SERVICEORDERSTATUS,STATUS_CODE,PRIORITY,STREETADDRESS,"
             "LATITUDE,LONGITUDE,ZIPCODE,MARADDRESSREPOSITORYID,WARD")
rows = []
for yr, lid in {2023:15, 2024:16, 2025:18, 2026:21}.items():
    print(f"311 SIGTRAMA {yr}...", flush=True)
    rows += [dict(r, SOURCEYEAR=yr) for r in
             fetch_all(f"{BASE}/ServiceRequests/MapServer/{lid}", "SERVICECODE='SIGTRAMA'", SR_FIELDS)]
write_csv(rows, "service_reports_signals_2023_2026.csv")

SIG = f"{BASE}/Transportation_Signs_Signals_Lights_WebMercator/MapServer"
print("Traffic Signals...", flush=True)
write_csv(fetch_all(f"{SIG}/170"), "traffic_signals.csv")
print("Signal Cabinets...", flush=True)
write_csv(fetch_all(f"{SIG}/27"), "signal_cabinets.csv")
print("Traffic Poles...", flush=True)
write_csv(fetch_all(f"{SIG}/94"), "traffic_poles.csv")
print("APS Buttons...", flush=True)
write_csv(fetch_all(f"{BASE}/Transportation_ADA_WebMercator/MapServer/0"), "aps_buttons.csv")

# 6. Crashes — discover the layer, then pull 2023+
print("Discovering crash layer...", flush=True)
crash_url = None
for svc in ("Public_Safety_WebMercator", "Transportation_WebMercator", "Vision_Zero_WebMercator"):
    try:
        info = json.loads(urllib.request.urlopen(f"{BASE}/{svc}/MapServer?f=json", timeout=60).read())
        for l in info.get("layers", []):
            if "crash" in l["name"].lower() and "detail" not in l["name"].lower():
                crash_url = f"{BASE}/{svc}/MapServer/{l['id']}"
                print(f"  found: {svc} layer {l['id']} ({l['name']})", flush=True)
                break
    except Exception as e:
        print(f"  {svc}: {e}", flush=True)
    if crash_url: break
if crash_url:
    info = json.loads(urllib.request.urlopen(crash_url + "?f=json", timeout=60).read())
    date_fields = [f["name"] for f in info.get("fields", []) if "esriFieldTypeDate" == f["type"]]
    dfield = next((f for f in date_fields if "REPORT" in f.upper() or "FROM" in f.upper()), date_fields[0] if date_fields else None)
    print(f"  date field: {dfield}; fields: {[f['name'] for f in info.get('fields',[])][:25]}", flush=True)
    where = f"{dfield} >= TIMESTAMP '2023-01-01'" if dfield else "1=1"
    write_csv(fetch_all(crash_url, where), "crashes_2023_plus.csv")
else:
    print("  !! crash layer not found — handle separately", flush=True)
print("\nDONE. Files in", OUT, flush=True)
