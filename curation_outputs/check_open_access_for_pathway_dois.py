from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_ROOT = Path("/Users/nana/Desktop/PepDB/PepDatabase")
USB_ROOT = Path("/Volumes/WENTBROKE/Pesticide degradation database/pesticidepdf")
MANIFEST = PROJECT_ROOT / "PesticideDB_Pathway_DOI_Redownload_Manifest.csv"
OUT_DIR = PROJECT_ROOT / "curation_outputs" / "pathway_open_access_check_20260708"

# Unpaywall requires an email parameter. This project contact email is already used
# in the local database setup and keeps requests identifiable without scraping.
UNPAYWALL_EMAIL = "gurungsaru634@gmail.com"
USER_AGENT = "PesticideDB pathway curation; mailto:gurungsaru634@gmail.com"


def request_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def request_binary(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def safe_filename(name: str) -> str:
    keep = []
    for char in name:
        if char.isalnum() or char in "._-":
            keep.append(char)
        else:
            keep.append("_")
    cleaned = "".join(keep).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned[:180] or "paper.pdf"


def target_folder(row: pd.Series) -> Path:
    folder = str(row.get("target_usb_folder") or "").strip()
    if folder:
        return Path(folder)
    return USB_ROOT / str(row["pesticide"])


def check_doi(row: pd.Series) -> dict:
    doi = str(row["doi"]).strip()
    url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={quote(UNPAYWALL_EMAIL)}"
    base = row.to_dict()
    try:
        data = request_json(url)
    except HTTPError as exc:
        return {
            **base,
            "oa_check_status": f"http_error_{exc.code}",
            "is_oa": "",
            "oa_status": "",
            "best_oa_pdf_url": "",
            "best_oa_landing_url": "",
            "best_oa_host_type": "",
            "best_oa_license": "",
            "download_status": "not_attempted",
            "downloaded_pdf_path": "",
        }
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            **base,
            "oa_check_status": f"error: {exc}",
            "is_oa": "",
            "oa_status": "",
            "best_oa_pdf_url": "",
            "best_oa_landing_url": "",
            "best_oa_host_type": "",
            "best_oa_license": "",
            "download_status": "not_attempted",
            "downloaded_pdf_path": "",
        }

    location = data.get("best_oa_location") or {}
    return {
        **base,
        "oa_check_status": "checked",
        "is_oa": data.get("is_oa", ""),
        "oa_status": data.get("oa_status", ""),
        "best_oa_pdf_url": location.get("url_for_pdf") or "",
        "best_oa_landing_url": location.get("url") or "",
        "best_oa_host_type": location.get("host_type") or "",
        "best_oa_license": location.get("license") or "",
        "download_status": "not_attempted",
        "downloaded_pdf_path": "",
    }


def maybe_download(row: dict) -> dict:
    pdf_url = str(row.get("best_oa_pdf_url") or "").strip()
    if not pdf_url:
        row["download_status"] = "no_pdf_url"
        return row
    host = urlparse(pdf_url).netloc.casefold()
    if not host:
        row["download_status"] = "invalid_pdf_url"
        return row

    folder = target_folder(pd.Series(row))
    folder.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(str(row.get("suggested_pdf_filename") or f"{row['pesticide']}_{row['doi']}.pdf"))
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    target = folder / filename
    if target.exists() and target.stat().st_size > 1024 and target.read_bytes()[:4] == b"%PDF":
        row["download_status"] = "already_exists"
        row["downloaded_pdf_path"] = str(target)
        return row

    try:
        content = request_binary(pdf_url)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        row["download_status"] = f"download_error: {exc}"
        return row
    if not content.lstrip().startswith(b"%PDF"):
        row["download_status"] = "downloaded_content_not_pdf"
        return row
    target.write_bytes(content)
    row["download_status"] = "downloaded_open_access_pdf"
    row["downloaded_pdf_path"] = str(target)
    return row


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST).fillna("")
    # Priority 1 first: highest scientific value and most likely to unlock new pathways.
    subset = manifest[manifest["acquisition_priority"].astype(int).eq(1)].copy()
    subset = subset.sort_values(["protein_record_count", "database_record_count", "pesticide"], ascending=[False, False, True])

    csv_path = OUT_DIR / "pesticidedb_priority1_open_access_check.csv"
    existing: dict[str, dict] = {}
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as handle:
            for item in csv.DictReader(handle):
                existing[str(item.get("doi", "")).strip()] = item

    subset_dois = {str(row["doi"]).strip() for _, row in subset.iterrows()}
    rows = [row for doi, row in existing.items() if doi in subset_dois]
    for index, (_, row) in enumerate(subset.iterrows(), start=1):
        doi = str(row["doi"]).strip()
        if doi in existing:
            checked = existing[doi]
            print(f"{index}/{len(subset)} {checked['pesticide']} {checked['doi']} oa={checked.get('is_oa')} status={checked.get('oa_status')} cached", flush=True)
            continue
        checked = check_doi(row)
        rows.append(checked)
        write_csv(csv_path, rows)
        print(f"{index}/{len(subset)} {checked['pesticide']} {checked['doi']} oa={checked['is_oa']} status={checked['oa_status']}", flush=True)
        time.sleep(0.15)

    downloaded = []
    for row in rows:
        if str(row.get("download_status") or "") in {"downloaded_open_access_pdf", "already_exists", "downloaded_content_not_pdf"}:
            downloaded.append(row)
        elif row.get("is_oa") is True or str(row.get("is_oa")).lower() == "true":
            downloaded.append(maybe_download(row.copy()))
            time.sleep(0.15)
        else:
            downloaded.append(row)

    write_csv(csv_path, downloaded)
    pd.DataFrame(downloaded).to_excel(OUT_DIR / "pesticidedb_priority1_open_access_check.xlsx", index=False)

    summary = pd.DataFrame(downloaded).groupby(["pesticide", "is_oa", "download_status"], dropna=False).size().reset_index(name="count")
    summary.to_csv(OUT_DIR / "pesticidedb_priority1_open_access_summary.csv", index=False)
    print(csv_path)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
