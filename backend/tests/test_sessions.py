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


def test_admin_issued_password_reset(app_env):
    c, api, admin, _ = app_env
    h = api.user(admin)
    me = c.get(f"{A}/me", headers=h).json()
    learner2 = api.user(admin)
    assert c.post(f"{A}/admin/users/{me['id']}/password-reset", headers=learner2).status_code == 403
    r = c.post(f"{A}/admin/users/{me['id']}/password-reset", headers=admin)
    assert r.status_code == 201
    code = r.json()["code"]
    assert c.post(f"{A}/auth/reset-password", json={"code": "x" * 20, "new_password": "new-password-77"}).status_code == 400
    assert c.post(f"{A}/auth/reset-password", json={"code": code, "new_password": "new-password-77"}).status_code == 200
    # one-time, old sessions revoked, old password gone, new password works
    assert c.post(f"{A}/auth/reset-password", json={"code": code, "new_password": "other-pass-777"}).status_code == 400
    assert c.get(f"{A}/me", headers=h).status_code == 401
    assert c.post(f"{A}/auth/login", json={"email": me["email"], "password": "password-123!"}).status_code == 401
    assert api.login(me["email"], "new-password-77")


def test_totp_rfc6238_vectors():
    import hashlib

    from app import totp
    key = b"12345678901234567890"
    for t, want in [(59, "94287082"), (1111111109, "07081804"), (1234567890, "89005924"), (20000000000, "65353130")]:
        assert totp.hotp(key, t // 30, digits=8, digest=hashlib.sha1) == want


def test_two_factor_setup_login_and_disable(app_env):
    import time

    from app import totp
    c, api, admin, _ = app_env
    h = api.user(admin)
    me = c.get(f"{A}/me", headers=h).json()
    assert me["two_factor"] is False
    s = c.post(f"{A}/me/2fa/setup", headers=h).json()
    assert s["otpauth_uri"].startswith("otpauth://totp/ISL%20NOVA:")
    now = time.time()
    valid = {totp.totp(s["secret"], now + d) for d in (-60, -30, 0, 30, 60)}
    wrong = next(x for x in ("000000", "111111", "222222", "333333") if x not in valid)
    assert c.post(f"{A}/me/2fa/enable", json={"code": wrong}, headers=h).status_code == 400
    # use the previous step so the login below can use the current one (replay protection)
    r = c.post(f"{A}/me/2fa/enable", json={"code": totp.totp(s["secret"], now - 30)}, headers=h)
    assert r.status_code == 200, r.text
    assert c.get(f"{A}/me", headers=h).json()["two_factor"] is True

    creds = {"email": me["email"], "password": "password-123!"}
    r = c.post(f"{A}/auth/login", json=creds)
    assert r.status_code == 401 and r.json()["error"]["code"] == "otp_required"
    assert c.post(f"{A}/auth/login", json={**creds, "otp": "123"}).status_code == 401
    code = totp.totp(s["secret"], now)
    assert c.post(f"{A}/auth/login", json={**creds, "otp": code}).status_code == 200
    r = c.post(f"{A}/auth/login", json={**creds, "otp": code})  # same code again: replay refused
    assert r.status_code == 401 and r.json()["error"]["code"] == "invalid_otp"

    assert c.post(f"{A}/me/2fa/disable", json={"code": wrong}, headers=h).status_code == 400
    assert c.post(f"{A}/me/2fa/disable", json={"code": totp.totp(s["secret"])}, headers=h).status_code == 200
    assert c.post(f"{A}/auth/login", json=creds).status_code == 200


def test_retention_job_dry_run_then_apply(app_env):
    c, api, admin, _ = app_env
    h = api.user(admin)
    me = c.get(f"{A}/me", headers=h).json()
    # an issued-and-redeemed reset code is eligible for deletion
    code = c.post(f"{A}/admin/users/{me['id']}/password-reset", headers=admin).json()["code"]
    assert c.post(f"{A}/auth/reset-password", json={"code": code, "new_password": "another-pass-1"}).status_code == 200
    learner = api.user(admin)
    assert c.post(f"{A}/admin/retention", json={}, headers=learner).status_code == 403
    dry = c.post(f"{A}/admin/retention", json={}, headers=admin).json()
    assert dry["applied"] is False and dry["would_delete"]["password_resets_expired_or_used"] >= 1
    assert "recordings_past_consent_retention" in dry["needs_review"]
    done = c.post(f"{A}/admin/retention", json={"apply": True}, headers=admin).json()
    assert done["deleted"]["password_resets_expired_or_used"] >= 1
    again = c.post(f"{A}/admin/retention", json={}, headers=admin).json()
    assert again["would_delete"]["password_resets_expired_or_used"] == 0
