"""Charts for the v2/v3 chapter, drawn from genuine release artifacts.

    python docs/report/src/charts_v3.py <out_dir> <v3 comparison.json> <v3 open_set_v3.json> <browser_v3_top1>
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(sys.argv[1]) / "img"
OUT.mkdir(parents=True, exist_ok=True)
comp = json.loads(Path(sys.argv[2]).read_text())
osr = json.loads(Path(sys.argv[3]).read_text())
browser_v3 = float(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != "none" else None
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 200,
                     "axes.grid": True, "grid.color": "#eef2f7", "axes.axisbelow": True})
V, C, G, A, SL = "#6d28d9", "#0891b2", "#059669", "#d97706", "#94a3b8"

# 1. best test top-1 per architecture (single models: the best seed by validation) + releases
rows = comp["models"]
best_kind = {}
for r in sorted(rows, key=lambda r: -r["val_macro_f1"]):
    key = r["kind"] + (" + other" if r["classes"] == 201 else "")
    best_kind.setdefault(key, r)
items = sorted(best_kind.items(), key=lambda kv: kv[1]["test_top1"])
fig, ax = plt.subplots(figsize=(7.2, 3.6))
cols = [G if r["model_id"] == comp["best"] else (A if k.startswith("ensemble") else C) for k, r in items]
ax.barh([k for k, _ in items], [100 * r["test_top1"] for _, r in items], color=cols)
for i, (_, r) in enumerate(items):
    ax.text(100 * r["test_top1"] + 0.1, i, f"{100 * r['test_top1']:.1f} %", va="center", fontsize=8)
ax.axvline(91.7, color=SL, ls="--", lw=1)
ax.text(91.8, -0.45, "v1 LSTM 91.7 %", fontsize=7, color="#475569", va="center")
ax.set_xlim(88, 99)
ax.set_xlabel("Test top-1 (%), INCLUDE official split, best seed by validation")
ax.set_title("v3 candidates (green = selected by validation)")
fig.tight_layout()
fig.savefig(OUT / "v3_models.png", facecolor="white")
plt.close(fig)

# 2. unknown-sign false acceptance / false rejection by version
labels = ["v1 max-prob\n(all 62 glosses)", "v2 max-prob\n(all 62 glosses)", "v3 max-prob\n(part B)", "v3 detector\n(part B, shipped)"]
far = [29.3, 34.0, 100 * osr["max_probability_rule"]["false_acceptance"], 100 * osr["open_set_detector_rule"]["false_acceptance"]]
frr = [12.1, None, 100 * osr["max_probability_rule"]["false_rejection"], 100 * osr["open_set_detector_rule"]["false_rejection"]]
fig, ax = plt.subplots(figsize=(7.2, 3.2))
x = range(len(labels))
ax.bar([i - 0.2 for i in x], far, 0.4, color=A, label="Unknown signs accepted (FAR)")
ax.bar([i + 0.2 for i in x], [f or 0 for f in frr], 0.4, color=C, label="Known signs not recognized (FRR)")
for i, (a, b) in enumerate(zip(far, frr, strict=True)):
    ax.text(i - 0.2, a + 0.6, f"{a:.1f}", ha="center", fontsize=8)
    if b is not None:
        ax.text(i + 0.2, b + 0.6, f"{b:.1f}", ha="center", fontsize=8)
ax.axhline(10, color="#e11d48", ls="--", lw=1)
ax.text(-0.55, 10.6, "FAR target 10 %", fontsize=7, color="#e11d48", ha="left")
ax.set_xticks(list(x), labels, fontsize=8)
ax.set_ylabel("%")
ax.set_title("Saying \"I don't know\": unknown-sign errors by version")
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(OUT / "v3_openset.png", facecolor="white")
plt.close(fig)

# 3. browser pipeline top-1 by version
vals = [("v1 LSTM", 74.0), ("v2 LSTM\n(fps aug)", 83.6)] + ([("v3 BiLSTM-att", browser_v3)] if browser_v3 else [])
fig, ax = plt.subplots(figsize=(5.2, 2.8))
ax.bar([v[0] for v in vals], [v[1] for v in vals], color=[SL, C, G][:len(vals)])
for i, v in enumerate(vals):
    ax.text(i, v[1] + 1, f"{v[1]:.1f} %", ha="center", fontsize=9)
ax.axhline(85, color="#e11d48", ls="--", lw=1)
ax.text(-0.45, 87, "target 85 %", fontsize=7, color="#e11d48", ha="left")
ax.set_ylim(0, 105)
ax.set_ylabel("Top-1 (%)")
ax.set_title("Held-out clips through the browser (virtual camera)")
fig.tight_layout()
fig.savefig(OUT / "v3_browser.png", facecolor="white")
plt.close(fig)
print("charts: v3_models.png v3_openset.png v3_browser.png")
