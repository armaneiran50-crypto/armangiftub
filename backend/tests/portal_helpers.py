def provider_login(client, admin, provider_id, email):
    r = client.post(f"/api/providers/{provider_id}/users", headers=admin, json={"email": email, "password": "portal-pass-1"})
    assert r.status_code == 201, r.text
    tok = client.post("/api/auth/login", data={"username": email, "password": "portal-pass-1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}
