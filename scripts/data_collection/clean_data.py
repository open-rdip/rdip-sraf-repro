import json, re, os

current_dir = os.path.dirname(__file__)

parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

DATASET_A = os.path.join(parent_dir, "dataset_a_kg_population.json")
DATASET_B = os.path.join(parent_dir, "dataset_b_validation.json")

def is_valid_arxiv_id(arxiv_id: str) -> bool:
    if not arxiv_id:
        return False
    return bool(re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", arxiv_id))

def clean_arxiv_id(arxiv_id: str) -> str:
    """Strip version suffix from arxiv ID: 2303.08302v3 → 2303.08302"""
    if not arxiv_id:
        return ""
    return re.sub(r"v\d+$", "", arxiv_id.strip())

def clean_pdf_url(pdf_url: str) -> str:
    """Normalise arxiv PDF URLs to canonical form."""
    if not pdf_url:
        return ""
    # Strip version from arxiv PDF URLs: .../2303.08302v3.pdf → .../2303.08302.pdf
    pdf_url = re.sub(r"(arxiv\.org/pdf/[\d.]+)v\d+(\.pdf)?", r"\1.pdf", pdf_url)
    # Ensure .pdf suffix
    if "arxiv.org/pdf/" in pdf_url and not pdf_url.endswith(".pdf"):
        pdf_url = pdf_url + ".pdf"
    return pdf_url.strip()

def clean_dataset_a(data: list) -> tuple[list, dict]:
    """
    Clean Dataset A (KG population papers).
    Rules:
    - Must have paper_url_pdf
    - Deduplicate by arxiv_id, then by paper_url_pdf
    - Fix arxiv_id format
    - Normalise PDF URLs
    """
    stats = {
        "input":          len(data),
        "missing_pdf":    0,
        "duplicate_arxiv":0,
        "duplicate_url":  0,
        "cleaned":        0,
    }

    cleaned  = []
    seen_arxiv = set()
    seen_pdf   = set()

    for paper in data:
        # Must have PDF URL
        if not paper.get("paper_url_pdf"):
            stats["missing_pdf"] += 1
            continue

        # Clean fields
        paper["arxiv_id"]      = clean_arxiv_id(paper.get("arxiv_id", ""))
        paper["paper_url_pdf"] = clean_pdf_url(paper.get("paper_url_pdf", ""))
        paper["paper_title"]   = (paper.get("paper_title") or "").strip()
        paper["paper_url"]     = (paper.get("paper_url") or "").strip()
        paper["repo_url"]      = (paper.get("repo_url") or "").strip()

        # Deduplicate by arxiv ID
        if paper["arxiv_id"] and paper["arxiv_id"] in seen_arxiv:
            stats["duplicate_arxiv"] += 1
            continue

        # Deduplicate by PDF URL
        if paper["paper_url_pdf"] in seen_pdf:
            stats["duplicate_url"] += 1
            continue

        if paper["arxiv_id"]:
            seen_arxiv.add(paper["arxiv_id"])
        seen_pdf.add(paper["paper_url_pdf"])
        cleaned.append(paper)

    stats["cleaned"] = len(cleaned)
    return cleaned, stats


def clean_dataset_b(data: list) -> tuple[list, dict]:
    """
    Clean Dataset B (validation repos).
    Rules:
    - Must have repo_url
    - Must have at least one env file (Docker, Conda, or requirements.txt)
    - Must have accessible PDF
    - Deduplicate by repo_url
    - Fix arxiv_id format
    - Normalise PDF URLs
    - Ensure b_score and final_tier are consistent
    """
    stats = {
        "input":          len(data),
        "missing_repo":   0,
        "missing_env":    0,
        "missing_pdf":    0,
        "duplicate_repo": 0,
        "score_fixed":    0,
        "cleaned":        0,
    }

    cleaned   = []
    seen_repos = set()

    for repo in data:
        # Must have repo_url
        if not repo.get("repo_url"):
            stats["missing_repo"] += 1
            continue

        # Must have at least one env file
        env = repo.get("env_files", {})
        has_env = (
            env.get("Dockerfile", False) or
            env.get("environment.yml", False) or
            env.get("requirements.txt", False)
        )
        if not has_env:
            stats["missing_env"] += 1
            continue

        # Must have accessible PDF
        if not repo.get("pdf_accessible", False):
            stats["missing_pdf"] += 1
            continue

        # Deduplicate by repo_url
        repo_key = repo["repo_url"].rstrip("/").lower()
        if repo_key in seen_repos:
            stats["duplicate_repo"] += 1
            continue
        seen_repos.add(repo_key)

        # Fix fields
        repo["arxiv_id"]      = clean_arxiv_id(repo.get("arxiv_id", ""))
        repo["paper_url_pdf"] = clean_pdf_url(repo.get("paper_url_pdf", ""))
        repo["paper_title"]   = (repo.get("paper_title") or "").strip()
        repo["paper_url"]     = (repo.get("paper_url") or "").strip()
        repo["has_seed"]      = bool(repo.get("has_seed", False))
        repo["has_env_file"]  = has_env

        # Recompute b_score to ensure consistency
        original_score = repo.get("b_score", 0)
        computed_score = 0
        if env.get("Dockerfile"):       computed_score += 3
        if env.get("environment.yml"):  computed_score += 2
        if env.get("requirements.txt"): computed_score += 1
        if env.get("setup.py"):         computed_score += 1
        if repo.get("has_seed"):        computed_score += 2
        if repo.get("stars", 0) > 100:  computed_score += 1

        if computed_score != original_score:
            repo["b_score"] = computed_score
            stats["score_fixed"] += 1

        # Ensure final_tier is consistent with score
        if "final_tier" not in repo:
            repo["final_tier"] = "full" if computed_score >= 5 else "build_only"

        cleaned.append(repo)

    stats["cleaned"] = len(cleaned)
    return cleaned, stats


def print_stats(name: str, stats: dict):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    for k, v in stats.items():
        print(f"  {k:20s}: {v}")


def main():
    print("=== Dataset Cleaner ===\n")

    # ── Dataset A ──────────────────────────────────────────────────────────
    if not os.path.exists(DATASET_A):
        print(f"[ERROR] {DATASET_A} not found.")
    else:
        with open(DATASET_A) as f:
            data_a = json.load(f)
        cleaned_a, stats_a = clean_dataset_a(data_a)
        print_stats("Dataset A — KG Population", stats_a)

        with open(DATASET_A, "w") as f:
            json.dump(cleaned_a, f, indent=2)
        print(f"\n  Saved cleaned Dataset A → {DATASET_A}")

    # ── Dataset B ──────────────────────────────────────────────────────────
    if not os.path.exists(DATASET_B):
        print(f"[ERROR] {DATASET_B} not found.")
    else:
        with open(DATASET_B) as f:
            data_b = json.load(f)
        cleaned_b, stats_b = clean_dataset_b(data_b)
        print_stats("Dataset B — Validation Repos", stats_b)

        with open(DATASET_B, "w") as f:
            json.dump(cleaned_b, f, indent=2)
        print(f"\n  Saved cleaned Dataset B → {DATASET_B}")

        # Summary of cleaned B
        full       = [r for r in cleaned_b if r.get("final_tier") == "full"]
        build_only = [r for r in cleaned_b if r.get("final_tier") == "build_only"]
        scores     = [r["b_score"] for r in cleaned_b]
        print(f"\n  Final Dataset B summary:")
        print(f"    Full tier:       {len(full)}")
        print(f"    Build-only tier: {len(build_only)}")
        if scores:
            print(f"    Avg score:       {sum(scores)/len(scores):.1f}")
            print(f"    Max / Min:       {max(scores)} / {min(scores)}")

    print("\n=== Done ===")


if __name__ == "__main__":
    main()