"""Teacher classes, spaced-repetition review and analytics v2."""
A = "/api/v1"


def _me(c, h):
    return c.get(f"{A}/me", headers=h).json()


def test_teacher_class_lifecycle_and_privacy(app_env):
    c, api, admin, _ = app_env
    teacher = api.user(admin, "teacher")
    learner = api.user(admin)
    other = api.user(admin)
    assert c.post(f"{A}/classes", json={"name": "7B"}, headers=learner).status_code == 403
    cls = c.post(f"{A}/classes", json={"name": "Class 7B"}, headers=teacher).json()
    assert len(cls["join_code"]) == 8
    assert c.post(f"{A}/classes/join", json={"code": "ZZZZZZZZ"}, headers=learner).status_code == 404
    assert c.post(f"{A}/classes/join", json={"code": cls["join_code"].lower()}, headers=learner).json()["id"] == cls["id"]
    for sid, ok in (("ISL001", True), ("ISL001", False), ("ISL002", False), ("ISL002", False), ("ISL002", True)):
        c.post(f"{A}/learning/attempts", json={"sign_id": sid, "mode": "quiz", "correct": ok}, headers=learner)
    c.post(f"{A}/learning/attempts", json={"sign_id": "ISL003", "mode": "quiz", "correct": True}, headers=other)  # not a member
    prog = c.get(f"{A}/classes/{cls['id']}/progress", headers=teacher).json()
    assert [x["name"] for x in prog["learners"]] == [_me(c, learner)["display_name"]]
    row = prog["learners"][0]
    assert row["attempts"] == 5 and row["accuracy"] == 0.4 and row["signs_practised"] == 2 and row["hardest"][0] == "ISL002"
    assert prog["hard_signs"][0]["sign_id"] == "ISL002" and prog["hard_signs"][0]["accuracy"] == round(1 / 3, 3)
    assert "history" not in str(row)
    # another teacher cannot see it; a learner cannot see it
    t2 = api.user(admin, "teacher")
    assert c.get(f"{A}/classes/{cls['id']}/progress", headers=t2).status_code == 404
    assert c.get(f"{A}/classes/{cls['id']}/progress", headers=learner).status_code == 403
    mine = c.get(f"{A}/classes", headers=learner).json()
    assert mine["joined"][0]["name"] == "Class 7B" and mine["can_teach"] is False
    # leaving removes the learner from the teacher's view
    c.delete(f"{A}/classes/{cls['id']}/membership", headers=learner)
    assert c.get(f"{A}/classes/{cls['id']}/progress", headers=teacher).json()["learners"] == []
    assert c.delete(f"{A}/classes/{cls['id']}", headers=teacher).json()["ok"] is True


def test_spaced_repetition_review_and_daily_goal(app_env):
    c, api, admin, _ = app_env
    u = api.user(admin)
    r = c.post(f"{A}/learning/attempts", json={"sign_id": "ISL005", "mode": "quiz", "correct": False}, headers=u).json()
    assert r["review_box"] == 0
    r = c.post(f"{A}/learning/attempts", json={"sign_id": "ISL006", "mode": "quiz", "correct": True}, headers=u).json()
    assert r["review_box"] == 1
    r = c.post(f"{A}/learning/attempts", json={"sign_id": "ISL006", "mode": "quiz", "correct": True}, headers=u).json()
    assert r["review_box"] == 2
    q = c.get(f"{A}/learning/review", headers=u).json()
    assert [d["sign_id"] for d in q["due"]] == ["ISL005"] and q["upcoming"] == 1
    a = c.get(f"{A}/learning/achievements", headers=u).json()
    assert a["today"] == 3 and a["daily_goal"] == 10
    c.patch(f"{A}/me", json={"settings": {"daily_goal": 25}}, headers=u)
    assert c.get(f"{A}/learning/achievements", headers=u).json()["daily_goal"] == 25


def test_analytics_overview_counts_real_rows_only(app_env):
    c, api, admin, _ = app_env
    learner = api.user(admin)
    researcher = api.user(admin, "researcher")
    for ok in (True, False, True, True, False):
        c.post(f"{A}/learning/attempts", json={"sign_id": "ISL010", "mode": "quiz", "correct": ok}, headers=learner)
    assert c.get(f"{A}/analytics/overview", headers=learner).status_code == 403
    o = c.get(f"{A}/analytics/overview", params={"days": 7}, headers=researcher).json()
    assert len(o["days"]) == 7 and sum(o["series"]["learning_attempts"]) == 5
    assert o["series"]["active_users"][-1] == 1 and o["totals"]["attempt_accuracy"] == 0.6
    assert o["most_practised"][0]["sign_id"] == "ISL010" and o["hardest"][0]["accuracy"] == 0.6
    assert c.get(f"{A}/analytics/overview", params={"days": 0}, headers=researcher).status_code == 422
