# collect_dataset_b.py
# Purpose: collect repos with env files + PDFs for SRE evaluation
# Requires: Dockerfile OR conda OR requirements.txt AND accessible PDF

import json, time, base64, requests, os, random
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

OUTPUT_FILE = os.path.join(parent_dir, "dataset_b_validation.json")
CHECKPOINT_FILE = os.path.join(parent_dir, "checkpoint_b.json")
TARGET          = 100
MIN_SCORE       = 3

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
    if rem == 0:
        print("[RATE LIMIT] Exhausted — waiting 60 minutes for reset ...")
        time.sleep(3600)
        return check_rate_limit()
    if rem < 200:
        print(f"[WARNING] Rate limit low — pausing 120s")
        time.sleep(120)
    return rem

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            d = json.load(f)
        print(f"[Resume] {len(d['repos'])} collected, "
              f"{len(d['seen'])} seen, "
              f"{d['checked']} checked")
        return d
    return {"repos": [], "seen": [], "checked": 0}

def save_checkpoint(repos, seen, checked):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({
            "repos":   repos,
            "seen":    list(seen),
            "checked": checked
        }, f)

def parse_owner_repo(url):
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return None, None

def is_recent(row):
    aid = row.get("paper_arxiv_id", "") or ""
    if not aid:
        return True
    try:
        return 19 <= int(aid[:2]) <= 25
    except (ValueError, IndexError):
        return True

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
    if not pdf_url:
        return False, pdf_url
    try:
        r = requests.head(pdf_url, timeout=8, allow_redirects=True)
        return r.status_code == 200, pdf_url
    except Exception:
        return False, pdf_url

# ── GitHub checks — order matters for rate limit efficiency ───────────────────

def get_meta(owner, repo):
    """Single API call — get stars, language, archived status."""
    r = safe_get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=GH_HEADERS
    )
    if r is not None and r.status_code == 200:
        d = r.json()
        return {
            "stars":    d.get("stargazers_count", 0),
            "language": d.get("language", ""),
            "archived": d.get("archived", False),
        }
    return {}

def file_exists(owner, repo, path):
    r = safe_get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
        headers=GH_HEADERS
    )
    return r is not None and r.status_code == 200

def scan_env_files(owner, repo):
    """
    Check for environment files.
    Ordered by value: Dockerfile first (most informative),
    then conda, then requirements.
    Stops as soon as it finds the first file of each type.
    """
    checks = {
        "Dockerfile":       ["Dockerfile", "docker/Dockerfile",
                             ".docker/Dockerfile"],
        "environment.yml":  ["environment.yml", "environment.yaml",
                             "conda.yml"],
        "requirements.txt": ["requirements.txt",
                             "requirements/requirements.txt",
                             "requirements/base.txt"],
        "setup.py":         ["setup.py", "setup.cfg", "pyproject.toml"],
    }
    found = {}
    for ftype, paths in checks.items():
        found[ftype] = False
        for path in paths:
            if file_exists(owner, repo, path):
                found[ftype] = True
                break
            time.sleep(0.05)
    return found

def check_seed(owner, repo):
    for name in ["README.md", "README.rst", "readme.md"]:
        r = safe_get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{name}",
            headers=GH_HEADERS
        )
        if r is not None and r.status_code == 200:
            try:
                content = base64.b64decode(
                    r.json()["content"]
                ).decode("utf-8", errors="ignore").lower()
                keywords = ["random seed", "random_seed", "set_seed",
                           "manual_seed", "--seed", "reproducib", "seed ="]
                if any(kw in content for kw in keywords):
                    return True
            except Exception:
                pass
    return False

def evaluate_repo(owner, repo, paper_info):
    """
    Evaluate a repo for Dataset B.
    Returns (record, score) or (None, 0) if it should be skipped.

    Check order is optimised to fail fast and save API calls:
    1. Metadata (1 call) — skip archived and non-Python immediately
    2. Env files (3-12 calls) — skip if none found
    3. PDF check (0 API calls — HTTP HEAD only)
    4. Seed check (1-3 calls) — only if repo passed all above
    """
    # Step 1: metadata — cheapest check, eliminates many repos immediately
    meta = get_meta(owner, repo)
    if not meta:
        return None, 0
    if meta.get("archived"):
        print(f"     skip: archived")
        return None, 0
    if meta.get("language") not in ["Python", "Jupyter Notebook",
                                     "unknown", None, ""]:
        print(f"     skip: language={meta.get('language')}")
        return None, 0

    # Step 2: env files — skip if none exist (saves seed + PDF checks)
    env     = scan_env_files(owner, repo)
    has_env = (env["Dockerfile"] or
               env["environment.yml"] or
               env["requirements.txt"])
    if not has_env:
        print(f"     skip: no env file")
        return None, 0

    # Step 3: PDF check — no GitHub API call, just HTTP HEAD
    pdf_url        = paper_info.get("pdf_url", "")
    pdf_ok, pdf_url = check_pdf(pdf_url)
    if not pdf_ok and paper_info.get("arxiv_id"):
        fallback       = f"https://arxiv.org/pdf/{paper_info['arxiv_id']}"
        pdf_ok, pdf_url = check_pdf(fallback)
    if not pdf_ok:
        print(f"     skip: no PDF")
        return None, 0

    # Step 4: seed check — only runs if all above passed
    seed = check_seed(owner, repo)

    # Score
    score = 0
    if env["Dockerfile"]:          score += 3
    if env["environment.yml"]:     score += 2
    if env["requirements.txt"]:    score += 1
    if env["setup.py"]:            score += 1
    if seed:                       score += 2
    if meta.get("stars", 0) > 100: score += 1

    tier = "full" if score >= 5 else "build_only"

    print(f"     score={score} tier={tier} | "
          f"docker={env['Dockerfile']} "
          f"conda={env['environment.yml']} "
          f"req={env['requirements.txt']} "
          f"seed={seed} "
          f"stars={meta.get('stars', 0)}")

    if score < MIN_SCORE:
        print(f"     skip: score {score} < {MIN_SCORE}")
        return None, 0

    return {
        "repo":           f"{owner}/{repo}",
        "repo_url":       f"https://github.com/{owner}/{repo}",
        "stars":          meta.get("stars", 0),
        "language":       meta.get("language", ""),
        "env_files":      env,
        "has_env_file":   has_env,
        "has_seed":       seed,
        "paper_title":    paper_info.get("paper_title", ""),
        "paper_url":      paper_info.get("paper_url", ""),
        "paper_url_pdf":  pdf_url,
        "pdf_accessible": pdf_ok,
        "arxiv_id":       paper_info.get("arxiv_id", ""),
        "b_score":        score,
        "b_tier":         tier,
    }, score

# ── Main ─────────────────────────────────────────────────────────────────────

def collect_dataset_b():
    print("=== Dataset B Collector — SRE Validation ===")
    print(f"Target: {TARGET} repos, minimum score: {MIN_SCORE}\n")

    check_rate_limit()

    checkpoint = load_checkpoint()
    repos      = checkpoint["repos"]
    seen       = set(checkpoint["seen"])
    checked    = checkpoint["checked"]

    if len(repos) >= TARGET:
        print(f"Already have {len(repos)} repos.")
        finalise(repos)
        return

    print("[HuggingFace] Loading PWC archive ...")
    dataset = load_dataset(
        "pwc-archive/links-between-paper-and-code",
        split="train"
    )
    print(f"[HuggingFace] {len(dataset):,} entries")

    all_links = [
        row for row in dataset
        if "github.com" in (row.get("repo_url") or "")
        and is_recent(row)
    ]
    print(f"[Filter] {len(all_links):,} GitHub repos from 2019+")
    print(f"[Filter] Already seen: {len(seen)}, "
          f"collected: {len(repos)}/{TARGET}\n")

    random.seed(42)
    random.shuffle(all_links)

    for link in all_links:

        if len(repos) >= TARGET:
            print(f"\n[Done] Reached {TARGET} repos.")
            break

        github_url  = link.get("repo_url", "") or ""
        paper_url   = link.get("paper_url_abs") or link.get("paper_url") or ""
        arxiv_id    = link.get("paper_arxiv_id", "") or ""
        paper_title = link.get("paper_title", "") or ""
        pdf_url     = get_pdf_url(link)

        owner, repo = parse_owner_repo(github_url)
        if not owner or not repo:
            continue

        repo_key = f"{owner}/{repo}"
        if repo_key in seen:
            continue
        seen.add(repo_key)
        checked += 1

        print(f"\n[{checked}] {repo_key}  ({len(repos)}/{TARGET})")

        try:
            record, score = evaluate_repo(owner, repo, {
                "paper_title": paper_title,
                "paper_url":   paper_url,
                "arxiv_id":    arxiv_id,
                "pdf_url":     pdf_url,
            })
        except Exception as e:
            print(f"     [error] {e}")
            record, score = None, 0

        if record:
            repos.append(record)
            print(f"     ✓ Added — {len(repos)}/{TARGET}")
            save_checkpoint(repos, seen, checked)

        time.sleep(0.8)

        # Rate limit check every 50 repos
        if checked % 50 == 0:
            check_rate_limit()

    finalise(repos)

def finalise(repos):
    repos.sort(key=lambda x: x["b_score"], reverse=True)

    final = []
    full_count = build_count = 0
    for r in repos:
        if full_count < 30 and r["b_tier"] == "full":
            r["final_tier"] = "full"
            final.append(r)
            full_count += 1
        elif build_count < 70:
            r["final_tier"] = "build_only"
            final.append(r)
            build_count += 1
        if len(final) >= TARGET:
            break

    with open(OUTPUT_FILE, "w") as f:
        json.dump(final, f, indent=2)

    if os.path.exists(CHECKPOINT_FILE) and len(final) >= TARGET:
        os.remove(CHECKPOINT_FILE)

    scores = [r["b_score"] for r in final]
    print(f"\n=== Dataset B Complete ===")
    print(f"Total saved:     {len(final)}")
    print(f"Full tier:       {full_count}/30")
    print(f"Build-only tier: {build_count}/70")
    if scores:
        print(f"Avg score:       {sum(scores)/len(scores):.1f}")
        print(f"Max / Min:       {max(scores)} / {min(scores)}")
    print(f"\nTop 10:")
    for r in final[:10]:
        print(f"  {r['repo']:45s}  "
              f"score={r['b_score']}  "
              f"tier={r.get('final_tier','?')}")

if __name__ == "__main__":
    collect_dataset_b()
