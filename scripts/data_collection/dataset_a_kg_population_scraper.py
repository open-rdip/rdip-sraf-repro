# collect_dataset_a.py
# Purpose: collect papers with accessible PDFs for KG population
# Does NOT require environment files — just needs a readable PDF

import json, time, requests, os, random
from datasets import load_dataset
from dotenv import load_dotenv

load_dotenv()

current_dir = os.path.dirname(__file__)

parent_dir = os.path.abspath(os.path.join(current_dir, "../.."))


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GH_HEADERS   = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json"
}

OUTPUT_FILE = os.path.join(parent_dir, "dataset_a_kg_population.json")
CHECKPOINT_FILE = os.path.join(parent_dir, "checkpoint_a.json")
TARGET          = 500

# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_get(url, headers=None, timeout=10):
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        return r
    except Exception as e:
        print(f"     [net] {str(e)[:60]}")
        time.sleep(2)
        return None

def check_rate_limit():
    import datetime
    r = safe_get("https://api.github.com/rate_limit", headers=GH_HEADERS)
    if not r:
        return 5000
    d = r.json()
    if "resources" not in d:
        print(f"Token error: {d}")
        raise SystemExit(1)
    rem   = d["resources"]["core"]["remaining"]
    reset = datetime.datetime.fromtimestamp(
        d["resources"]["core"]["reset"]
    ).strftime("%H:%M:%S")
    print(f"[GitHub] {rem}/5000 remaining (resets {reset})")
    if rem < 50:
        wait = 60
        print(f"[WARNING] Rate limit critically low — pausing {wait}s")
        time.sleep(wait)
    return rem

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            d = json.load(f)
        print(f"[Resume] {len(d['papers'])} collected, "
              f"{len(d['seen'])} seen")
        return d
    return {"papers": [], "seen": []}

def save_checkpoint(papers, seen):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"papers": papers, "seen": list(seen)}, f)

def get_pdf_url(link):
    if link.get("paper_url_pdf"):
        return link["paper_url_pdf"]
    aid = link.get("paper_arxiv_id", "") or ""
    if aid:
        return f"https://arxiv.org/pdf/{aid}"
    abs_url = link.get("paper_url_abs", "") or ""
    if "arxiv.org/abs/" in abs_url:
        aid = abs_url.split("/abs/")[-1].split("v")[0]
        return f"https://arxiv.org/pdf/{aid}"
    return ""

def check_pdf(pdf_url):
    """HEAD request only — does not download the file."""
    if not pdf_url:
        return False
    try:
        r = requests.head(pdf_url, timeout=8, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False

def parse_owner_repo(url):
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None, None

def is_recent(row):
    """Keep only papers from 2019 onwards."""
    aid = row.get("paper_arxiv_id", "") or ""
    if not aid:
        return True
    try:
        return 19 <= int(aid[:2]) <= 25
    except (ValueError, IndexError):
        return True

# ── Main ─────────────────────────────────────────────────────────────────────

def collect_dataset_a():
    print("=== Dataset A Collector — KG Population ===")
    print(f"Target: {TARGET} papers with accessible PDFs\n")

    check_rate_limit()

    checkpoint = load_checkpoint()
    papers     = checkpoint["papers"]
    seen       = set(checkpoint["seen"])

    if len(papers) >= TARGET:
        print(f"Already have {len(papers)} papers. Done.")
        return

    print("[HuggingFace] Loading PWC archive ...")
    dataset = load_dataset(
        "pwc-archive/links-between-paper-and-code",
        split="train"
    )
    print(f"[HuggingFace] {len(dataset):,} total entries")

    all_links = [
        row for row in dataset
        if "github.com" in (row.get("repo_url") or "")
        and is_recent(row)
    ]
    print(f"[Filter] {len(all_links):,} GitHub repos from 2019+")
    print(f"[Filter] Already seen: {len(seen)}\n")

    random.seed(42)
    random.shuffle(all_links)

    checked = 0
    for link in all_links:

        if len(papers) >= TARGET:
            print(f"\n[Done] Reached {TARGET} papers.")
            break

        github_url  = link.get("repo_url", "") or ""
        paper_url   = link.get("paper_url_abs") or link.get("paper_url") or ""
        arxiv_id    = link.get("paper_arxiv_id", "") or ""
        paper_title = link.get("paper_title", "") or ""
        pdf_url     = get_pdf_url(link)

        owner, repo = parse_owner_repo(github_url)
        if not owner or not repo:
            continue

        # Use paper arxiv_id as dedup key — same paper can have multiple repos
        dedup_key = arxiv_id or f"{owner}/{repo}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        checked += 1

        print(f"[{checked}] {paper_title[:60]}")

        # Dataset A only needs an accessible PDF — no GitHub API calls needed
        # This is much faster and does not burn rate limit
        pdf_ok = check_pdf(pdf_url)

        # Try arxiv fallback if direct URL fails
        if not pdf_ok and arxiv_id:
            fallback = f"https://arxiv.org/pdf/{arxiv_id}"
            if check_pdf(fallback):
                pdf_url = fallback
                pdf_ok  = True

        if not pdf_ok:
            print(f"     skip: no accessible PDF")
            continue

        papers.append({
            "paper_title":   paper_title,
            "paper_url":     paper_url,
            "paper_url_pdf": pdf_url,
            "arxiv_id":      arxiv_id,
            "repo_url":      f"https://github.com/{owner}/{repo}",
        })
        print(f"     ✓ Added — {len(papers)}/{TARGET}")
        save_checkpoint(papers, seen)

        time.sleep(0.3)   # polite delay for PDF server

        if checked % 100 == 0:
            check_rate_limit()

    # Save final output
    with open(OUTPUT_FILE, "w") as f:
        json.dump(papers, f, indent=2)

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print(f"\n=== Dataset A Complete ===")
    print(f"Papers collected: {len(papers)}")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    collect_dataset_a()
