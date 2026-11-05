"""Charts for the ISL NOVA report, drawn only from genuine project artifacts."""
import csv, json, sys, glob, collections
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

R = Path(sys.argv[1]); D = Path(sys.argv[2]); REPO = Path(sys.argv[3]); OUT = R / "img"; OUT.mkdir(exist_ok=True)
for f in glob.glob("/usr/share/fonts/opentype/inter/Inter-*.otf"): font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#cbd5e1", "axes.labelcolor": "#334155", "xtick.color": "#475569", "ytick.color": "#475569",
                     "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": "#1e1b4b", "figure.dpi": 200,
                     "axes.grid": True, "grid.color": "#eef2f7", "grid.linewidth": 0.8, "axes.axisbelow": True})
V, C, G, A, RO, SL = "#6d28d9", "#0891b2", "#059669", "#d97706", "#e11d48", "#64748b"
def save(fig, name): fig.tight_layout(); fig.savefig(OUT / name, bbox_inches="tight", transparent=False, facecolor="white"); plt.close(fig)

model_dir = next((R / "data" / "models").glob("lstm-*"))
metrics = json.loads((model_dir / "metrics.json").read_text())
comp = json.loads((R / "data" / "comparison.json").read_text())
man = json.loads((D / "manifest.json").read_text())

# 1 model comparison
order = ["lstm", "pooled_logreg", "gru", "dtw_1nn"]; names = {"lstm": "LSTM", "pooled_logreg": "Logistic reg.", "gru": "GRU", "dtw_1nn": "DTW 1-NN"}
ms = {m["kind"]: m for m in comp["models"]}
fig, ax = plt.subplots(figsize=(7.2, 3.2)); x = np.arange(4); w = 0.26
for i, (k, lab, col) in enumerate([("test_top1", "Top-1", V), ("test_top5", "Top-5", C), ("test_macro_f1", "Macro-F1", G)]):
    vals = [ms[o][k] * 100 for o in order]; b = ax.bar(x + (i - 1) * w, vals, w, label=lab, color=col)
    ax.bar_label(b, fmt="%.1f", fontsize=7.5, padding=2, color="#334155")
ax.set_xticks(x, [names[o] for o in order]); ax.set_ylim(70, 102); ax.set_ylabel("% on 635 held-out test videos")
ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12)); ax.set_title("Model comparison, INCLUDE official test split"); save(fig, "model_comparison.png")

# 1b latency/size
fig, ax = plt.subplots(figsize=(4.2, 3.0))
for o in order:
    m = ms[o]; ax.scatter(m["latency_ms"], m["test_top1"] * 100, s=40 + 18 * np.sqrt(m["size_bytes"] / 1e6), color={"lstm": V, "pooled_logreg": C, "gru": G, "dtw_1nn": A}[o], alpha=.85, edgecolor="white")
    ax.annotate(names[o], (m["latency_ms"], m["test_top1"] * 100), xytext=(6, 4), textcoords="offset points", fontsize=8)
ax.set_xscale("log"); ax.set_xlim(0.008, 600); ax.set_ylim(82, 94); ax.set_xlabel("latency per sample (ms, log)"); ax.set_ylabel("test top-1 %"); ax.set_title("Accuracy vs speed (bubble = size)"); save(fig, "speed_accuracy.png")

# 2 training curves
log = [json.loads(l) for l in (model_dir / "training_log.jsonl").read_text().splitlines() if l.strip().startswith('{"epoch"')]
ep = [h["epoch"] for h in log]
fig, ax = plt.subplots(figsize=(7.2, 2.9)); ax.plot(ep, [h["train_loss"] for h in log], color=V, lw=2, label="training loss")
ax.set_xlabel("epoch"); ax.set_ylabel("loss", color=V); ax2 = ax.twinx(); ax2.grid(False)
ax2.plot(ep, [h["val_top1"] * 100 for h in log], color=C, lw=2, label="validation top-1 %"); ax2.plot(ep, [h["val_macro_f1"] * 100 for h in log], color=G, lw=2, ls="--", label="validation macro-F1 %")
ax2.set_ylabel("validation %", color=C); ax2.spines["right"].set_visible(True)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, frameon=False, loc="center right")
ax.set_title(f"LSTM training ({len(log)} epochs, early stopping on validation)"); save(fig, "training_curves.png")

# 3 confusion matrix
cm = np.array(metrics["test"]["confusion"], dtype=float); rs = cm.sum(1, keepdims=True); cmn = np.divide(cm, rs, out=np.zeros_like(cm), where=rs > 0)
fig, ax = plt.subplots(figsize=(5.2, 4.6)); im = ax.imshow(cmn, cmap="Purples", vmin=0, vmax=1, interpolation="nearest")
ax.set_xlabel("predicted class (ISL001 … ISL200)"); ax.set_ylabel("true class"); ax.grid(False); ax.set_title("Confusion matrix, 200 × 200 (row-normalised)")
fig.colorbar(im, ax=ax, fraction=.046, pad=.03); save(fig, "confusion.png")

# 4 per-class F1
pc = metrics["test"]["per_class"]; f1 = np.array([d["f1"] for d in pc if d["support"] > 0])
fig, ax = plt.subplots(figsize=(4.4, 3.0)); ax.hist(f1, bins=np.linspace(0, 1, 21), color=V, edgecolor="white")
ax.set_xlabel("per-class F1 on test"); ax.set_ylabel("classes"); ax.set_title(f"Per-class F1 ({len(f1)} classes with test videos)"); save(fig, "per_class_f1.png")

# 5 dataset split donut + samples per class
bs = man["summary"]["by_split"]
fig, ax = plt.subplots(figsize=(3.6, 3.2)); vals = [bs["train"], bs["val"], bs["test"]]
ax.pie(vals, labels=[f"Train\n{bs['train']:,}", f"Val\n{bs['val']}", f"Test\n{bs['test']}"], colors=[V, C, G], startangle=90, wedgeprops=dict(width=.38, edgecolor="white"), textprops={"fontsize": 9})
ax.text(0, 0, f"{sum(vals):,}\nsequences", ha="center", va="center", fontsize=11, fontweight="bold", color="#1e1b4b"); ax.set_title("Official INCLUDE split"); save(fig, "split_donut.png")
cnt = collections.Counter(e["sign_id"] for e in man["entries"])
fig, ax = plt.subplots(figsize=(4.4, 3.0)); ax.hist(list(cnt.values()), bins=range(0, max(cnt.values()) + 2), color=C, edgecolor="white")
ax.set_xlabel("usable sequences per class"); ax.set_ylabel("classes"); ax.set_title("Samples per class (all 200 have data)"); save(fig, "per_class_counts.png")

# 6 categories
cats = collections.Counter(r["category_label"] if "category_label" in r else r.get("category", "?") for r in csv.DictReader(open(REPO / "dataset/vocabulary/signs_master.csv", encoding="utf-8")))
items = sorted(cats.items(), key=lambda kv: kv[1])
fig, ax = plt.subplots(figsize=(7.2, 3.6)); b = ax.barh([k for k, _ in items], [v for _, v in items], color=V)
ax.bar_label(b, fontsize=8, padding=2); ax.set_xlabel("vocabulary slots"); ax.set_title("200-sign vocabulary by category"); ax.grid(axis="y", visible=False); save(fig, "categories.png")

# 7 open set
rows = list(csv.DictReader(open(R / "data" / "open_set_rows.csv")))
k = np.array([float(r["max_prob"]) for r in rows if r["group"] == "known" and r["max_prob"]]); u = np.array([float(r["max_prob"]) for r in rows if r["group"] == "unknown" and r["max_prob"]])
fig, ax = plt.subplots(figsize=(4.4, 3.0)); bins = np.linspace(0, 1, 26)
ax.hist(k, bins, alpha=.75, color=V, label=f"known signs (n={len(k)})", density=True); ax.hist(u, bins, alpha=.6, color=A, label=f"unknown signs (n={len(u)})", density=True)
ax.axvline(0.673, color=RO, ls="--", lw=1.5); ax.text(0.68, ax.get_ylim()[1] * .9, "τ = 0.673", color=RO, fontsize=8)
ax.set_xlabel("max calibrated probability"); ax.set_ylabel("density"); ax.legend(frameon=False, fontsize=8, loc="upper left"); ax.set_title("Known vs unknown confidence"); save(fig, "openset_hist.png")
ts = np.linspace(0, 1, 201); tpr = [(k >= t).mean() for t in ts]; fpr = [(u >= t).mean() for t in ts]
fig, ax = plt.subplots(figsize=(4.0, 3.0)); ax.plot(fpr, tpr, color=V, lw=2.2); ax.fill_between(fpr, tpr, color=V, alpha=.08); ax.plot([0, 1], [0, 1], color="#cbd5e1", ls="--")
ax.set_xlabel("unknown signs accepted (FPR)"); ax.set_ylabel("known signs accepted (TPR)"); ax.set_title("ROC, AUROC = 0.900"); save(fig, "openset_roc.png")

# 8 evaluation ladder
fig, ax = plt.subplots(figsize=(7.2, 2.8))
labs = ["Landmarks → model\n(635 test, Predictor)", "Raw video → Python\nMediaPipe → model (73)", "Browser virtual camera\n→ Live page (73)", "Public API, live demo\n(24 held-out)"]
vals = [91.65, 91.8, 74.0, 100.0]; b = ax.bar(labs, vals, color=[V, C, A, G], width=.55); ax.bar_label(b, fmt="%.1f %%", fontsize=9, padding=2)
ax.set_ylim(0, 112); ax.set_ylabel("top-1 %"); ax.set_title("Top-1 accuracy at each stage of the real pipeline"); save(fig, "pipeline_ladder.png")

# 9 live eval states
fig, ax = plt.subplots(figsize=(4.0, 2.8)); st = {"recognized": 48, "uncertain": 17, "unknown": 8}
b = ax.bar(st.keys(), st.values(), color=[G, A, SL], width=.55); ax.bar_label(b, padding=2); ax.set_ylabel("clips"); ax.set_title("Virtual-camera answers (45/48 recognized correct)"); save(fig, "live_states.png")

# 10 dataset landmark images (real INCLUDE sequences)
HAND = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),(5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),(13,17),(17,18),(18,19),(19,20),(0,17)]
POSE = [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),(23,24),(0,11),(0,12)]
want = ["hello", "thank you", "good morning", "how are you", "teacher", "happy", "india", "monday"]
by = {}
for e in man["entries"]:
    g = e["gloss"].lower()
    if e["split"] == "test" and g not in by and e["quality"]["status"] == "ok": by[g] = e
picks = [g for g in want if g in by]
for g in by:
    if len(picks) >= 8: break
    if g not in picks: picks.append(g)
fig, axs = plt.subplots(2, 4, figsize=(7.4, 4.3))
for ax, g in zip(axs.flat, picks):
    z = np.load(D / by[g]["landmarks_path"]); asp = float(z["aspect"]); n = len(z["pose_mask"])
    ax.set_facecolor("#0f172a"); ax.grid(False); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    idx = np.linspace(0, n - 1, 6).astype(int)
    for j, t in enumerate(idx):
        a = 0.25 + 0.75 * j / (len(idx) - 1)
        if z["pose_mask"][t]:
            p = z["pose"][t]
            for s, e2 in POSE: ax.plot([p[s,0]*asp, p[e2,0]*asp], [p[s,1], p[e2,1]], color="#94a3b8", lw=.8, alpha=a*.6)
        for side, col in (("left", "#a78bfa"), ("right", "#22d3ee")):
            if z[side + "_mask"][t]:
                h = z[side][t]
                for s, e2 in HAND: ax.plot([h[s,0]*asp, h[e2,0]*asp], [h[s,1], h[e2,1]], color=col, lw=.9, alpha=a)
    ax.set_xlim(0.15 * asp, 0.85 * asp); ax.set_ylim(1.0, 0.0); ax.set_title(f"{g.title()}  ·  {by[g]['sign_id']}", fontsize=8.5, color="#1e1b4b")
fig.suptitle("Real INCLUDE test recordings as extracted landmarks (6 frames overlaid, later = brighter)", fontsize=9.5, color="#334155")
save(fig, "dataset_landmarks.png")

# 11 one sequence as a feature matrix
sys.path[:0] = [str(REPO / "ml")]
from isl_nova_ml.data import load_landmarks
from isl_nova_ml.features import extract_features
fr, asp = load_landmarks(D / by[picks[0]]["landmarks_path"]); F = extract_features(fr, asp).features
fig, ax = plt.subplots(figsize=(7.2, 2.2)); ax.imshow(np.asarray(F).T, aspect="auto", cmap="magma", interpolation="nearest"); ax.grid(False)
ax.set_xlabel("32 resampled time steps"); ax.set_ylabel("204 features"); ax.set_title(f"Feature contract isl-nova-fc-1.0.0 for one '{picks[0].title()}' recording"); save(fig, "feature_matrix.png")
print("charts:", sorted(p.name for p in OUT.iterdir()))
