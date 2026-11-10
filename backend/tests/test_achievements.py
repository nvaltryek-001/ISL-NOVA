"""Streaks, points and badges are derived only from the user's own attempts."""
A = "/api/v1"


def test_streak_computation():
    from app.routers.personal import _streaks
    assert _streaks([], "2026-11-10") == (0, 0)
    assert _streaks(["2026-11-08", "2026-11-09", "2026-11-10"], "2026-11-10") == (3, 3)
    assert _streaks(["2026-11-08", "2026-11-09"], "2026-11-10") == (2, 2)      # yesterday keeps the streak
    assert _streaks(["2026-11-01", "2026-11-02", "2026-11-03", "2026-11-07"], "2026-11-10") == (0, 3)
    assert _streaks(["2026-11-10", "2026-11-10"], "2026-11-10") == (1, 1)


def test_achievements_from_real_attempts(app_env):
    c, api, admin, _ = app_env
    u = api.user(admin)
    empty = c.get(f"{A}/learning/achievements", headers=u).json()
    assert empty["attempts"] == 0 and empty["points"] == 0 and not any(b["earned"] for b in empty["badges"])
    signs = [f"ISL{n:03d}" for n in range(1, 12)]
    for sid in signs:
        assert c.post(f"{A}/learning/attempts", json={"sign_id": sid, "mode": "quiz", "correct": True}, headers=u).status_code == 201
    c.post(f"{A}/learning/attempts", json={"sign_id": "ISL001", "mode": "coach", "correct": False}, headers=u)
    a = c.get(f"{A}/learning/achievements", headers=u).json()
    assert a["attempts"] == 12 and a["correct"] == 11 and a["signs_practised"] == 11
    assert a["points"] == 11 * 10 + 2 and a["current_streak"] == 1 and a["this_week"] == 12
    earned = {b["id"] for b in a["badges"] if b["earned"]}
    assert earned == {"first_step", "ten_signs"}
    # another user's attempts never count
    assert c.get(f"{A}/learning/achievements", headers=api.user(admin)).json()["attempts"] == 0
    assert c.get(f"{A}/learning/achievements").status_code == 401
