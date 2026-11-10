"""Vocabulary proposals: duplicates refused, linguist accepts into the next stable ID."""
A = "/api/v1"


def test_proposal_lifecycle_and_duplicates(app_env):
    c, api, admin, _ = app_env
    learner = api.user(admin)
    ling = api.user(admin, "linguist")
    assert c.post(f"{A}/vocabulary/proposals", json={"gloss": "Hello", "category": "greetings"}, headers=learner).status_code == 409
    r = c.post(f"{A}/vocabulary/proposals", json={"gloss": "Water", "category": "food_daily_needs", "english_meaning": "Water",
                                                 "hindi_meaning": "पानी", "kannada_meaning": "ನೀರು"}, headers=learner)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert c.post(f"{A}/vocabulary/proposals", json={"gloss": "water ", "category": "food_daily_needs"}, headers=learner).status_code == 409
    assert c.post(f"{A}/vocabulary/proposals/{pid}/decide", json={"decision": "accept"}, headers=learner).status_code == 403
    mine = c.get(f"{A}/vocabulary/proposals", headers=learner).json()
    assert [p["id"] for p in mine["items"]] == [pid] and mine["vocabulary_size"] == 200 and mine["target"] == 500
    d = c.post(f"{A}/vocabulary/proposals/{pid}/decide", json={"decision": "accept"}, headers=ling).json()
    assert d["status"] == "accepted" and d["created_sign_id"] == "ISL201"
    s = c.get(f"{A}/signs/ISL201").json()
    assert s["verification_status"] == "proposed"
    assert s["translations"]["hi"]["text"] == "पानी" and s["translations"]["hi"]["status"] == "draft"
    assert c.post(f"{A}/vocabulary/proposals/{pid}/decide", json={"decision": "reject", "note": "x"}, headers=ling).status_code == 409
    r2 = c.post(f"{A}/vocabulary/proposals", json={"gloss": "Teapot", "category": "objects"}, headers=learner).json()
    assert c.post(f"{A}/vocabulary/proposals/{r2['id']}/decide", json={"decision": "reject"}, headers=ling).status_code == 422
    assert c.post(f"{A}/vocabulary/proposals/{r2['id']}/decide", json={"decision": "reject", "note": "regional variant of an existing sign"},
                  headers=ling).json()["status"] == "rejected"
    # direct creation also refuses duplicate names
    dup = c.post(f"{A}/signs", json={"sign_id": "ISL300", "canonical_sign_name": "HELLO", "category": "greetings"}, headers=ling)
    assert dup.status_code == 409
