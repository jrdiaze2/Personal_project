#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent Trainer — Extrae patrones reales de las DBs y actualiza CR_LEARNING_GUIDE.md
====================================================================================
Analiza datos reales acumulados (CRs generados, patrones, feedback, Jira CRs)
y actualiza la guía de aprendizaje para que todos los agentes tengan contexto real.

Uso:
    python3 agent_trainer.py                  # Análisis y actualización completa
    python3 agent_trainer.py --stats          # Solo mostrar estadísticas
    python3 agent_trainer.py --dry-run        # Mostrar cambios sin escribir
    python3 agent_trainer.py --min-conf 0.5   # Cambiar umbral de confianza (default: 0.5)
"""

import sqlite3
import json
import argparse
import re
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# Paths
TOOLS_DIR = Path(__file__).parent
REPO_ROOT = TOOLS_DIR.parent
GUIDE_PATH = REPO_ROOT / '.github' / 'CR_LEARNING_GUIDE.md'

DB_AI = TOOLS_DIR / 'cr_ai_learning.db'
DB_LEARN = TOOLS_DIR / 'cr_learning.db'
DB_RESOL = TOOLS_DIR / 'cr_resolutions.db'


# ─── Helpers ──────────────────────────────────────────────────────────────────

def db_connect(path: Path):
    if not path.exists():
        print(f"⚠️  DB not found: {path}")
        return None
    return sqlite3.connect(str(path))


def pct(count, total):
    return f"{100 * count / total:.1f}%" if total else "0%"


# ─── Data Extraction ──────────────────────────────────────────────────────────

def extract_generated_cr_stats(conn) -> dict:
    """Estadísticas de generated_crs (cr_ai_learning.db)."""
    total = conn.execute("SELECT COUNT(*) FROM generated_crs").fetchone()[0]
    if total == 0:
        return {"total": 0}

    classifications = conn.execute(
        "SELECT classification, COUNT(*) FROM generated_crs "
        "WHERE classification IS NOT NULL "
        "GROUP BY classification ORDER BY COUNT(*) DESC"
    ).fetchall()

    top_tests = conn.execute(
        "SELECT test_case, COUNT(*) FROM generated_crs "
        "GROUP BY test_case ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall()

    # Only last 30 days
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    recent = conn.execute(
        "SELECT COUNT(*) FROM generated_crs WHERE created_at >= ?", (cutoff,)
    ).fetchone()[0]

    feedback_stats = conn.execute(
        "SELECT verdict, COUNT(*) FROM decision_feedback GROUP BY verdict ORDER BY COUNT(*) DESC"
    ).fetchall()

    return {
        "total": total,
        "recent_30d": recent,
        "classifications": classifications,
        "top_tests": top_tests,
        "feedback_stats": feedback_stats,
    }


def extract_error_pattern_stats(conn) -> dict:
    """Estadísticas de error_patterns (cr_learning.db)."""
    total = conn.execute("SELECT COUNT(*) FROM error_patterns").fetchone()[0]

    high_conf = conn.execute(
        "SELECT error_type, pattern_text, confidence, success_count, fail_count "
        "FROM error_patterns WHERE confidence >= 0.5 "
        "ORDER BY confidence DESC, success_count DESC LIMIT 30"
    ).fetchall()

    by_type = conn.execute(
        "SELECT error_type, COUNT(*), ROUND(AVG(confidence),3) "
        "FROM error_patterns GROUP BY error_type ORDER BY COUNT(*) DESC"
    ).fetchall()

    return {
        "total": total,
        "high_confidence": high_conf,
        "by_type": by_type,
    }


def extract_jira_stats(conn) -> dict:
    """Estadísticas de jira_known_crs (cr_learning.db)."""
    total = conn.execute("SELECT COUNT(*) FROM jira_known_crs").fetchone()[0]

    projects = conn.execute(
        "SELECT project, COUNT(*) FROM jira_known_crs "
        "GROUP BY project ORDER BY COUNT(*) DESC"
    ).fetchall()

    statuses = conn.execute(
        "SELECT status, COUNT(*) FROM jira_known_crs "
        "GROUP BY status ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()

    components = conn.execute(
        "SELECT components, COUNT(*) FROM jira_known_crs "
        "WHERE components IS NOT NULL AND components != '' "
        "GROUP BY components ORDER BY COUNT(*) DESC LIMIT 15"
    ).fetchall()

    return {
        "total": total,
        "projects": projects,
        "statuses": statuses,
        "components": components,
    }


def extract_jira_comments_stats(conn) -> dict:
    """Estadísticas de jira_comments_learned (cr_learning.db)."""
    total = conn.execute("SELECT COUNT(*) FROM jira_comments_learned").fetchone()[0]
    with_root_cause = conn.execute(
        "SELECT COUNT(*) FROM jira_comments_learned WHERE root_cause IS NOT NULL AND root_cause != ''"
    ).fetchone()[0]
    with_fix = conn.execute(
        "SELECT COUNT(*) FROM jira_comments_learned WHERE fix_description IS NOT NULL AND fix_description != ''"
    ).fetchone()[0]
    return {"total": total, "with_root_cause": with_root_cause, "with_fix": with_fix}


def extract_resolution_stats(conn) -> dict:
    """Estadísticas de resolved_crs (cr_resolutions.db)."""
    if conn is None:
        return {"total": 0}
    total = conn.execute("SELECT COUNT(*) FROM resolved_crs").fetchone()[0]
    if total == 0:
        return {"total": 0}
    by_type = conn.execute(
        "SELECT resolution_type, COUNT(*) FROM resolved_crs "
        "GROUP BY resolution_type ORDER BY COUNT(*) DESC"
    ).fetchall()
    return {"total": total, "by_type": by_type}


def extract_top_signatures(conn_learn) -> list:
    """Top error signatures más frecuentes de url_analyses."""
    rows = conn_learn.execute(
        "SELECT error_extracted, error_type, COUNT(*) as n "
        "FROM url_analyses "
        "WHERE error_extracted IS NOT NULL AND error_extracted != '' "
        "GROUP BY error_extracted ORDER BY n DESC LIMIT 20"
    ).fetchall()
    return rows


def extract_component_project_rules(conn_learn) -> list:
    """Extraer reglas proyecto/componente desde jira_known_crs."""
    rows = conn_learn.execute(
        "SELECT components, project, COUNT(*) as n "
        "FROM jira_known_crs "
        "WHERE components IS NOT NULL AND components != '' "
        "GROUP BY components, project ORDER BY n DESC LIMIT 20"
    ).fetchall()
    return rows


# ─── Guide Builder ────────────────────────────────────────────────────────────

def build_guide(stats: dict, min_conf: float = 0.5) -> str:
    cr = stats["generated_crs"]
    ep = stats["error_patterns"]
    jira = stats["jira_stats"]
    comments = stats["jira_comments"]
    resol = stats["resolution_stats"]
    sigs = stats["top_signatures"]
    comp_rules = stats["component_project_rules"]

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    total_crs = cr.get("total", 0)
    recent_30d = cr.get("recent_30d", 0)

    # Classification breakdown
    classification_lines = ""
    for cls, cnt in cr.get("classifications", []):
        classification_lines += f"- **{cls}**: {cnt} ({pct(cnt, total_crs)})\n"

    # Top failing tests
    top_tests_lines = ""
    for i, (tc, cnt) in enumerate(cr.get("top_tests", [])[:15], 1):
        top_tests_lines += f"| {i} | `{tc}` | {cnt} |\n"

    # Feedback summary
    feedback_lines = ""
    for verdict, cnt in cr.get("feedback_stats", []):
        feedback_lines += f"- **{verdict}**: {cnt} decisions\n"

    # Error pattern types
    pattern_type_lines = ""
    for etype, count, avg_conf in ep.get("by_type", []):
        badge = "✅" if avg_conf >= 0.7 else ("⚠️" if avg_conf >= 0.5 else "❌")
        pattern_type_lines += f"| {badge} | `{etype}` | {count} | {avg_conf:.2f} |\n"

    # High confidence patterns
    high_conf_lines = ""
    seen = set()
    for etype, ptext, conf, succ, fail in ep.get("high_confidence", []):
        if conf < min_conf:
            continue
        key = ptext[:60]
        if key in seen:
            continue
        seen.add(key)
        total_uses = succ + fail
        acc = f"{100*succ/total_uses:.0f}%" if total_uses > 0 else "N/A"
        badge = "🔥" if conf >= 0.8 else "✅"
        high_conf_lines += f"- {badge} `[{etype}]` {ptext[:80]} _(conf={conf:.2f}, acc={acc})_\n"

    # Jira project rules
    jira_project_lines = ""
    for proj, cnt in jira.get("projects", []):
        jira_project_lines += f"- **{proj}**: {cnt} CRs ({pct(cnt, jira['total'])})\n"

    jira_status_lines = ""
    for status, cnt in jira.get("statuses", []):
        jira_status_lines += f"- {status}: {cnt}\n"

    # Component → project rules
    comp_rule_lines = ""
    for comp, proj, cnt in comp_rules[:15]:
        comp_parsed = comp.replace("[", "").replace("]", "").replace("'", "").replace('"', '').strip()
        comp_rule_lines += f"- `{comp_parsed[:50]}` → **{proj}** ({cnt} CRs)\n"

    # Top signatures
    sig_lines = ""
    for sig, etype, cnt in sigs[:15]:
        sig_lines += f"- `{str(sig)[:90]}` ({etype}, {cnt}x)\n"

    # Resolution stats
    resol_lines = ""
    if resol.get("total", 0) > 0:
        for rtype, cnt in resol.get("by_type", []):
            resol_lines += f"- {rtype}: {cnt}\n"
    else:
        resol_lines = "_No resolved CRs synced yet. Run `auto_sync_resolutions.py` to populate._\n"

    # Compute validation pass rate from feedback
    cr_created = next((cnt for v, cnt in cr.get("feedback_stats", []) if v == "CR_CREATED"), 0)
    monitor = next((cnt for v, cnt in cr.get("feedback_stats", []) if v == "MONITOR"), 0)
    total_feedback = cr_created + monitor
    pass_rate = f"{100*cr_created/total_feedback:.1f}%" if total_feedback > 0 else "N/A"

    guide = f"""# CR Learning Guide

> **Auto-generated by `agent_trainer.py`** — Do not edit manually.
> Last Updated: {now}
> Confidence Threshold Applied: ≥ {min_conf:.0%}

---

## 📊 Real System Metrics

| Metric | Value |
|--------|-------|
| Total CRs Generated | {total_crs:,} |
| CRs (last 30 days) | {recent_30d:,} |
| Known Jira CRs | {jira.get("total", 0):,} |
| Error Patterns Learned | {ep.get("total", 0):,} |
| Jira Comments Analyzed | {comments.get("total", 0):,} |
| Comments with Root Cause | {comments.get("with_root_cause", 0):,} |
| Comments with Fix | {comments.get("with_fix", 0):,} |
| Resolved CRs in DB | {resol.get("total", 0):,} |
| Decision Feedbacks | {total_feedback:,} |
| CR Creation Rate | {pass_rate} |

---

## 🗂️ CR Classification Distribution (Real Data)

{classification_lines}
---

## 🔥 Top Failing Tests (Most Frequent)

| # | Test Case | Count |
|---|-----------|-------|
{top_tests_lines}
---

## 🤖 Decision Feedback Summary

{feedback_lines}
---

## 🧠 Error Pattern Types (with Confidence)

| Status | Type | Patterns | Avg Confidence |
|--------|------|----------|---------------|
{pattern_type_lines}
---

## ✅ High-Confidence Patterns (≥ {min_conf:.0%})

These patterns were learned from real CRs and should be prioritized:

{high_conf_lines}
---

## 🗺️ Jira Project Assignment Rules (Real Data)

{jira_project_lines}
### Status Distribution in Known CRs

{jira_status_lines}
---

## 🔧 Component → Project Mapping (Learned from {jira.get("total", 0):,} CRs)

{comp_rule_lines}
---

## 📋 Top Error Signatures (Most Recurring)

{sig_lines}
---

## ✅ CR Quality Checklist (Validated Against Real CRs)

- [ ] Classification matches learned types: PRODUCT_BUGS / TEST_ISSUES / INFRA_ISSUES / UNSUPPORTED_FEATURES
- [ ] Test case in top-failing list → higher priority
- [ ] Include at least 2 source URLs (test execution links)
- [ ] Signature ≤ 120 chars
- [ ] Test cases: list top 3 failing tests with filter
- [ ] Evidence: quote relevant log snippets
- [ ] Impact: estimate % of runs affected
- [ ] Project: CNX for UI/CXBASIC failures, CCXA for Phase2/VSF/VSX

---

## 🔍 Resolved CR Knowledge Base

{resol_lines}
---

## 🔄 Recommended CR Template

```
**Summary**: [Signature line, ≤80 chars]

**Classification**: [PRODUCT_BUGS | TEST_ISSUES | INFRA_ISSUES | UNSUPPORTED_FEATURES]

**Frequency**: [X% of runs across Y clusters]

**Affected Targets**: [List: CXBASIC.UI, Phase2, Phase2 Extended, ...]

**Failing Tests** (top 3):
1. [Test Path/Name] — [Status: Failed/Blocked/etc]
2. ...

**Evidence**:
- TRC URL: [Direct filter link to failing results]
- Log Pattern: [Key error message or snippet]
- Source: [Humio log link if available]

**Impact**: [Brief assessment of user impact or scope]

**Suggested Next** (if known):
- Link to related CR or ticket
- Known workaround or fix status
```

---

## ⚙️ How to Update This Guide

```bash
# Full update from all DBs
cd tools && python3 agent_trainer.py

# Only show stats without writing
python3 agent_trainer.py --stats

# Change confidence threshold
python3 agent_trainer.py --min-conf 0.6

# Sync resolved CRs from Jira first, then train
python3 auto_sync_resolutions.py && python3 agent_trainer.py
```

---

## 📈 Legend

- 🔥 Very high confidence (≥ 0.80) — use always
- ✅ High confidence (≥ 0.70) — use with low risk
- ⚠️ Medium confidence (≥ 0.50) — use cautiously
- ❌ Low confidence (< 0.50) — avoid or re-evaluate
"""
    return guide


# ─── Main ─────────────────────────────────────────────────────────────────────

def run(min_conf: float = 0.5, dry_run: bool = False, stats_only: bool = False):
    print("=" * 70)
    print("🧠 AGENT TRAINER — Extracting real patterns from DBs")
    print("=" * 70)

    conn_ai = db_connect(DB_AI)
    conn_learn = db_connect(DB_LEARN)
    conn_resol = db_connect(DB_RESOL)

    if not conn_ai or not conn_learn:
        print("❌ Critical DBs not found. Aborting.")
        sys.exit(1)

    print("📦 Extracting stats from cr_ai_learning.db ...")
    cr_stats = extract_generated_cr_stats(conn_ai)
    print(f"   → {cr_stats['total']:,} CRs total, {cr_stats.get('recent_30d', 0):,} last 30d")

    print("📦 Extracting stats from cr_learning.db ...")
    ep_stats = extract_error_pattern_stats(conn_learn)
    jira_stats = extract_jira_stats(conn_learn)
    comments_stats = extract_jira_comments_stats(conn_learn)
    top_sigs = extract_top_signatures(conn_learn)
    comp_rules = extract_component_project_rules(conn_learn)
    print(f"   → {ep_stats['total']:,} patterns, {jira_stats['total']:,} Jira CRs")

    print("📦 Extracting stats from cr_resolutions.db ...")
    resol_stats = extract_resolution_stats(conn_resol)
    print(f"   → {resol_stats['total']} resolved CRs")

    all_stats = {
        "generated_crs": cr_stats,
        "error_patterns": ep_stats,
        "jira_stats": jira_stats,
        "jira_comments": comments_stats,
        "resolution_stats": resol_stats,
        "top_signatures": top_sigs,
        "component_project_rules": comp_rules,
    }

    if stats_only:
        print()
        print("=== SUMMARY ===")
        print(f"  CRs generated    : {cr_stats['total']:,}")
        print(f"  Error patterns   : {ep_stats['total']:,}")
        print(f"  Jira known CRs   : {jira_stats['total']:,}")
        print(f"  Jira comments    : {comments_stats['total']:,}")
        print(f"  Resolved CRs DB  : {resol_stats['total']}")
        print()
        print("  Classifications:")
        for cls, cnt in cr_stats.get("classifications", []):
            print(f"    {cls}: {cnt}")
        print()
        print("  Decision feedback:")
        for v, cnt in cr_stats.get("feedback_stats", []):
            print(f"    {v}: {cnt}")
        conn_ai.close()
        conn_learn.close()
        if conn_resol:
            conn_resol.close()
        return

    # Build guide
    print()
    print(f"📝 Building CR_LEARNING_GUIDE.md (min_conf={min_conf}) ...")
    guide_content = build_guide(all_stats, min_conf=min_conf)

    if dry_run:
        print()
        print("--- DRY RUN: Guide preview (first 80 lines) ---")
        for line in guide_content.splitlines()[:80]:
            print(line)
        print("...")
        print(f"--- Total: {len(guide_content.splitlines())} lines ---")
    else:
        GUIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GUIDE_PATH, "w", encoding="utf-8") as f:
            f.write(guide_content)
        print(f"✅ Guide updated: {GUIDE_PATH}")
        print(f"   Lines written: {len(guide_content.splitlines())}")

    conn_ai.close()
    conn_learn.close()
    if conn_resol:
        conn_resol.close()

    print()
    print("=" * 70)
    print("✅ Agent Trainer complete")
    print("   Next steps:")
    print("   1. Run auto_sync_resolutions.py to populate resolved CRs")
    print("   2. Commit .github/CR_LEARNING_GUIDE.md so agents pick it up")
    print("   3. Run periodically (e.g. weekly) after new CRs are generated")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Trainer — Update CR_LEARNING_GUIDE.md from real data")
    parser.add_argument("--stats", action="store_true", help="Only show statistics, don't write guide")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be written without saving")
    parser.add_argument("--min-conf", type=float, default=0.5, help="Minimum confidence threshold (default: 0.5)")
    args = parser.parse_args()

    run(min_conf=args.min_conf, dry_run=args.dry_run, stats_only=args.stats)
