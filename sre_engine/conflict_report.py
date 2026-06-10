# sre_engine/conflict_report.py
import json
from datetime import datetime

SEVERITY_ICON = {
    "CRITICAL": "✖ CRITICAL",
    "HIGH":     "▲ HIGH",
    "WARNING":  "● WARNING",
    "UNKNOWN":  "? UNKNOWN",
}


def generate_report(diff_result: dict, output_json: str = None) -> str:
    if diff_result.get("status") == "error":
        return f"ERROR: {diff_result.get('message', 'Unknown error')}"

    lines = []
    sep   = "=" * 60

    # ── Define all variables first ────────────────────────────────────────────
    cc       = diff_result.get("conflict_counts", {})
    shacl    = diff_result.get("shacl_violations", {})
    critical = shacl.get("critical", [])
    warnings = shacl.get("warnings", [])
    stage2   = sum(cc.values())
    stage3   = len(critical)
    total    = stage2 + stage3
    fully_clean = (total == 0 and len(warnings) == 0)

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append(sep)
    lines.append("  RDIP SEMANTIC REPRODUCIBILITY REPORT")
    lines.append(sep)
    lines.append(f"  Generated:    {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"  Original:     {diff_result['original_study_id']}")
    lines.append(f"  Reproduction: {diff_result['reproduction_study_id']}")
    lines.append(sep)

    # ── Overall verdict ───────────────────────────────────────────────────────
    if fully_clean:
        lines.append("\n  ✔ NO CONFLICTS DETECTED")
        lines.append("  The reproduction environment matches the original.")
        lines.append("  SHACL validation passed — this study is audit-ready.")
    else:
        lines.append(f"\n  TOTAL ISSUES: {total} "
                     f"({len(warnings)} additional warning(s))")
        if total > 0:
            lines.append("  Pre-execution reproduction is AT RISK.\n")

    # ── Stage 2 conflicts ─────────────────────────────────────────────────────
    if any(cc.values()):
        lines.append("─" * 60)
        lines.append("  STAGE 2 — Semantic Diff Conflicts")
        lines.append("─" * 60)

        if cc.get("version_conflicts", 0) > 0:
            lines.append(f"\n  {SEVERITY_ICON['HIGH']} "
                         f"Dependency version mismatches: "
                         f"{cc['version_conflicts']}")
            lines.append("  → Query the conflict graph for details:")
            lines.append(f"    GRAPH <{diff_result.get('conflict_graph_uri', '')}>")
            lines.append("    WHERE { ?c a rdip:VersionConflict ; rdip:message ?m }")

        if cc.get("digest_conflicts", 0) > 0:
            lines.append(f"\n  {SEVERITY_ICON['CRITICAL']} "
                         f"Image digest conflicts: "
                         f"{cc['digest_conflicts']}")
            lines.append("  → The container image cannot be guaranteed identical.")
            lines.append("  → Pin to the original digest: FROM image@sha256:...")

        if cc.get("seed_conflicts", 0) > 0:
            lines.append(f"\n  {SEVERITY_ICON['HIGH']} "
                         f"Random seed conflicts: "
                         f"{cc['seed_conflicts']}")
            lines.append("  → Stochastic results will differ from the original.")

        if cc.get("hardware_conflicts", 0) > 0:
            lines.append(f"\n  {SEVERITY_ICON['HIGH']} "
                         f"Hardware / environment conflicts: "
                         f"{cc['hardware_conflicts']}")
            lines.append("  → CUDA / GPU / OS divergence may alter numerical results.")
            lines.append("  → Query the conflict graph for details:")
            lines.append(f"    GRAPH <{diff_result.get('conflict_graph_uri', '')}>")
            lines.append("    WHERE { ?c a rdip:HardwareConflict ; rdip:message ?m }")

    # ── Stage 3 SHACL violations ──────────────────────────────────────────────
    if critical or warnings:
        lines.append("\n" + "─" * 60)
        lines.append("  STAGE 3 — SHACL Validation")
        lines.append("─" * 60)

        if critical:
            lines.append(f"\n  {SEVERITY_ICON['CRITICAL']} "
                         f"{len(critical)} critical constraint(s) violated:\n")
            for v in critical:
                lines.append(f"  • {v['message']}")
                if v.get("path"):
                    lines.append(f"    Path: {v['path']}")

        if warnings:
            lines.append(f"\n  {SEVERITY_ICON['WARNING']} "
                         f"{len(warnings)} warning(s):\n")
            for v in warnings:
                lines.append(f"  • {v['message']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    lines.append("\n" + sep)
    lines.append("  SUMMARY")
    lines.append(sep)
    lines.append(f"  Original triples:     {diff_result.get('original_triples', 0)}")
    lines.append(f"  Reproduction triples: {diff_result.get('reproduction_triples', 0)}")
    lines.append(f"  Version conflicts:    {cc.get('version_conflicts', 0)}")
    lines.append(f"  Digest conflicts:     {cc.get('digest_conflicts', 0)}")
    lines.append(f"  Seed conflicts:       {cc.get('seed_conflicts', 0)}")
    lines.append(f"  Hardware conflicts:   {cc.get('hardware_conflicts', 0)}")
    lines.append(f"  SHACL critical:       {len(critical)}")
    lines.append(f"  SHACL warnings:       {len(warnings)}")
    lines.append(f"  SHACL conforms:       {diff_result.get('shacl_conforms', False)}")
    lines.append(sep + "\n")

    report = "\n".join(lines)
    print(report)

    if output_json:
        with open(output_json, "w") as f:
            json.dump({
                **diff_result,
                "report_generated": datetime.utcnow().isoformat(),
            }, f, indent=2)
        print(f"[ConflictReport] JSON saved to {output_json}")

    return report