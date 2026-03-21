import json, csv, os, sys

current_dir = os.path.dirname(__file__)

parent_dir = os.path.abspath(os.path.join(current_dir, ".."))

DATASET_A = os.path.join(parent_dir, "dataset_a_kg_population.json")
DATASET_B = os.path.join(parent_dir, "dataset_b_validation.json")
OUTPUT_A      = os.path.join(parent_dir, "validation/dataset_a.csv")
OUTPUT_B      = os.path.join(parent_dir, "validation/repo_list.csv")

os.makedirs("validation", exist_ok=True)


def convert_dataset_a(data: list, output_path: str):
    """
    Convert Dataset A to CSV.
    Each row is one paper with its PDF URL.
    """
    fields = [
        "study_id",
        "paper_title",
        "paper_url",
        "paper_url_pdf",
        "arxiv_id",
        "repo_url",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, paper in enumerate(data):
            writer.writerow({
                "study_id":      f"paper{i+1:04d}",
                "paper_title":   paper.get("paper_title", ""),
                "paper_url":     paper.get("paper_url", ""),
                "paper_url_pdf": paper.get("paper_url_pdf", ""),
                "arxiv_id":      paper.get("arxiv_id", ""),
                "repo_url":      paper.get("repo_url", ""),
            })

    print(f"[CSV] Dataset A → {output_path}  ({len(data)} rows)")


def convert_dataset_b(data: list, output_path: str):
    """
    Convert Dataset B to CSV.
    Each row is one repo with full reproducibility metadata.
    This is the file Phase IV reads to know what to build and test.
    """
    fields = [
        "study_id",
        "repo_url",
        "paper_url",
        "paper_url_pdf",
        "arxiv_id",
        "paper_title",
        "has_docker",
        "has_conda",
        "has_requirements",
        "has_setup_py",
        "has_seed",
        "pdf_accessible",
        "stars",
        "language",
        "b_score",
        "final_tier",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for i, repo in enumerate(data):
            env = repo.get("env_files", {})
            writer.writerow({
                "study_id":        f"study{i+1:03d}",
                "repo_url":        repo.get("repo_url", ""),
                "paper_url":       repo.get("paper_url", ""),
                "paper_url_pdf":   repo.get("paper_url_pdf", ""),
                "arxiv_id":        repo.get("arxiv_id", ""),
                "paper_title":     repo.get("paper_title", ""),
                "has_docker":      env.get("Dockerfile", False),
                "has_conda":       env.get("environment.yml", False),
                "has_requirements":env.get("requirements.txt", False),
                "has_setup_py":    env.get("setup.py", False),
                "has_seed":        repo.get("has_seed", False),
                "pdf_accessible":  repo.get("pdf_accessible", False),
                "stars":           repo.get("stars", 0),
                "language":        repo.get("language", ""),
                "b_score":         repo.get("b_score", 0),
                "final_tier":      repo.get("final_tier", ""),
            })

    print(f"[CSV] Dataset B → {output_path}  ({len(data)} rows)")


def print_dataset_b_summary(data: list):
    """Print a quick breakdown of the validation dataset."""
    full  = [r for r in data if r.get("final_tier") == "full"]
    build = [r for r in data if r.get("final_tier") == "build_only"]
    scores = [r.get("b_score", 0) for r in data]

    print(f"\n  Dataset B summary:")
    print(f"    Total repos:     {len(data)}")
    print(f"    Full tier:       {len(full)}")
    print(f"    Build-only tier: {len(build)}")
    if scores:
        print(f"    Avg score:       {sum(scores)/len(scores):.1f}")
        print(f"    Max / Min:       {max(scores)} / {min(scores)}")
    print(f"    Has Docker:      {sum(1 for r in data if r.get('env_files',{}).get('Dockerfile'))}")
    print(f"    Has Conda:       {sum(1 for r in data if r.get('env_files',{}).get('environment.yml'))}")
    print(f"    Has req.txt:     {sum(1 for r in data if r.get('env_files',{}).get('requirements.txt'))}")
    print(f"    Has seed docs:   {sum(1 for r in data if r.get('has_seed'))}")
    print(f"    Has PDF:         {sum(1 for r in data if r.get('pdf_accessible'))}")


def main():
    print("=== Dataset CSV Converter ===\n")

    # ── Dataset A ──────────────────────────────────────────────────────────
    if not os.path.exists(DATASET_A):
        print(f"[SKIP] {DATASET_A} not found — run data collection first.")
    else:
        with open(DATASET_A) as f:
            data_a = json.load(f)
        convert_dataset_a(data_a, OUTPUT_A)

    # ── Dataset B ──────────────────────────────────────────────────────────
    if not os.path.exists(DATASET_B):
        print(f"[SKIP] {DATASET_B} not found — run data collection first.")
    else:
        with open(DATASET_B) as f:
            data_b = json.load(f)
        convert_dataset_b(data_b, OUTPUT_B)
        print_dataset_b_summary(data_b)

    print("\n=== Done ===")
    print(f"\nOutputs:")
    if os.path.exists(OUTPUT_A):
        print(f"  {OUTPUT_A}")
    if os.path.exists(OUTPUT_B):
        print(f"  {OUTPUT_B}")


if __name__ == "__main__":
    main()