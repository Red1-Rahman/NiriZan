# .github/scripts/virustotal_scan.py
#!/usr/bin/env python3
import glob
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

VT_API_KEY = os.environ.get("VT_API_KEY")
if not VT_API_KEY:
    print("❌ VT_API_KEY environment variable is missing.")
    sys.exit(1)

HEADERS = {
    "x-apikey": VT_API_KEY,
    "Accept": "application/json",
}


def get_file_sha256(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def make_vt_request(
    url: str, method: str = "GET", data: bytes = None, content_type: str = None
) -> tuple[int, dict]:
    headers = HEADERS.copy()
    if content_type:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return resp.status, body
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"raw": err_body}
        return e.code, parsed


def poll_analysis(analysis_id: str, timeout: int = 300) -> dict:
    url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
    start = time.time()
    while time.time() - start < timeout:
        status, body = make_vt_request(url)
        if status == 200:
            attributes = body.get("data", {}).get("attributes", {})
            if attributes.get("status") == "completed":
                return attributes.get("stats", {})
        time.sleep(15)
    print(f"⚠️ Polling timed out for analysis {analysis_id}")
    return {}


def scan_file(file_path: str):
    file_hash = get_file_sha256(file_path)
    print(f"\n🔍 Processing: {file_path} (SHA-256: {file_hash[:12]}...)")

    # Step 1: Check if report already exists via Hash
    status, body = make_vt_request(f"https://www.virustotal.com/api/v3/files/{file_hash}")

    if status == 200:
        stats = body.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        print(f"✅ Existing VirusTotal report found. Stats: {stats}")
        # Optional: Trigger re-analysis if desired
        status, re_body = make_vt_request(
            f"https://www.virustotal.com/api/v3/files/{file_hash}/analyse", method="POST"
        )
        if status == 200:
            analysis_id = re_body.get("data", {}).get("id")
            stats = poll_analysis(analysis_id)
            print(f"📊 Re-analysis complete: {stats}")
        elif status == 409:
            print("⏳ Re-analysis already in progress on VirusTotal. Waiting for current scan...")
        return

    # Step 2: Upload if missing
    print("📤 Uploading new file artifact to VirusTotal...")
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    boundary = f"----WebKitFormBoundary{hashlib.md5(str(time.time()).encode()).hexdigest()}"
    body_data = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{os.path.basename(file_path)}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8")
        + file_bytes
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )

    status, resp = make_vt_request(
        "https://www.virustotal.com/api/v3/files",
        method="POST",
        data=body_data,
        content_type=f"multipart/form-data; boundary={boundary}",
    )

    if status == 200:
        analysis_id = resp.get("data", {}).get("id")
        print(f"📡 Analysis queued (ID: {analysis_id}). Polling for results...")
        stats = poll_analysis(analysis_id)
        print(f"📊 Upload analysis complete: {stats}")
    elif status == 409 or "AlreadySubmittedError" in str(resp):
        print("⏳ File is already undergoing analysis on VirusTotal. Fetching report...")
        time.sleep(10)
        _, report = make_vt_request(f"https://www.virustotal.com/api/v3/files/{file_hash}")
        stats = report.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        print(f"📊 Analysis complete: {stats}")
    else:
        print(f"❌ Failed to process file. Status: {status}, Response: {resp}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python virustotal_scan.py <file_glob1> [<file_glob2> ...]")
        sys.exit(1)

    files_to_scan = []
    for arg in sys.argv[1:]:
        files_to_scan.extend(glob.glob(arg))

    if not files_to_scan:
        print("⚠️ No matching files found to scan.")
        sys.exit(0)

    for file_path in files_to_scan:
        scan_file(file_path)


if __name__ == "__main__":
    main()
