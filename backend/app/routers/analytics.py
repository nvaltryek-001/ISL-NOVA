"""Analytics v2: aggregate usage and learning statistics from the database (no per-user data).

Only counts over real rows are returned; days without activity are zero. Recognition
history is included only for results users chose to save.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from ..api import Ctx, Router

router = Router("analytics")


class Window(BaseModel):
    days: int = Field(default=30, ge=1, le=365)


@router.get("/analytics/overview", summary="Usage over time, most practised and hardest signs, corrections",
            perm="analytics:read", query=Window)
def overview(ctx: Ctx):
    days = ctx.query.days
    start_dt = datetime.now(UTC) - timedelta(days=days - 1)
    start = start_dt.strftime("%Y-%m-%dT00:00:00Z")
    axis = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    names = {s["sign_id"]: s["canonical_sign_name"] for s in ctx.db.all("SELECT sign_id, canonical_sign_name FROM signs")}

    def per_day(rows, key="created_at"):
        c = Counter(str(r[key])[:10] for r in rows)
        return [c.get(d, 0) for d in axis]

    attempts = ctx.db.all("SELECT user_id, sign_id, mode, correct, created_at FROM learning_attempts WHERE created_at >= ?",
                          (start,))
    history = ctx.db.all("SELECT user_id, state, chosen_sign, corrected_sign, top, created_at FROM recognition_history "
                         "WHERE created_at >= ?", (start,))
    signups = ctx.db.all("SELECT created_at FROM users WHERE created_at >= ?", (start,))
    active = defaultdict(set)
    for r in attempts + history:
        active[str(r["created_at"])[:10]].add(r["user_id"])

    sign_stats = defaultdict(lambda: [0, 0])
    for r in attempts:
        sign_stats[r["sign_id"]][0] += 1
        sign_stats[r["sign_id"]][1] += bool(r["correct"])
    most = sorted(sign_stats.items(), key=lambda kv: -kv[1][0])[:10]
    hardest = sorted(((s, v) for s, v in sign_stats.items() if v[0] >= 5), key=lambda kv: kv[1][1] / kv[1][0])[:10]
    corrections = Counter((r["chosen_sign"], r["corrected_sign"]) for r in history
                          if r["corrected_sign"] and r["corrected_sign"] != r["chosen_sign"])
    return {
        "days": axis,
        "series": {"learning_attempts": per_day(attempts), "saved_recognitions": per_day(history),
                   "active_users": [len(active.get(d, ())) for d in axis], "new_users": per_day(signups)},
        "totals": {"learning_attempts": len(attempts), "saved_recognitions": len(history),
                   "active_users": len({r["user_id"] for r in attempts + history}), "new_users": len(signups),
                   "attempt_accuracy": round(sum(bool(r["correct"]) for r in attempts) / len(attempts), 3) if attempts else None},
        "modes": dict(Counter(r["mode"] for r in attempts)),
        "recognition_states": dict(Counter(r["state"] for r in history)),
        "most_practised": [{"sign_id": s, "name": names.get(s, s), "attempts": a, "accuracy": round(k / a, 3)}
                           for s, (a, k) in most],
        "hardest": [{"sign_id": s, "name": names.get(s, s), "attempts": a, "accuracy": round(k / a, 3)}
                    for s, (a, k) in hardest],
        "corrections": [{"model_said": names.get(a, a), "user_corrected_to": names.get(b, b), "count": n}
                        for (a, b), n in corrections.most_common(10)],
        "note": "Aggregates only. Recognition counts include only results users saved to their history.",
    }
