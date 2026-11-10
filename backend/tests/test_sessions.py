"""Sign out everywhere: bumping the token version revokes every earlier token."""
A = "/api/v1"


def test_logout_all_revokes_every_session(app_env):
    c, api, admin, _ = app_env
    first = api.user(admin)
    email = c.get(f"{A}/me", headers=first).json()["email"]
    second = api.login(email, "password-123!")
    assert c.get(f"{A}/me", headers=first).status_code == 200
    assert c.get(f"{A}/me", headers=second).status_code == 200

    assert c.post(f"{A}/auth/logout-all", headers=first).status_code == 200
    for h in (first, second):
        r = c.get(f"{A}/me", headers=h)
        assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_token"

    fresh = api.login(email, "password-123!")
    assert c.get(f"{A}/me", headers=fresh).status_code == 200
    # other accounts are untouched
    assert c.get(f"{A}/me", headers=admin).status_code == 200


def test_logout_all_needs_auth(app_env):
    c, *_ = app_env
    assert c.post(f"{A}/auth/logout-all").status_code == 401
