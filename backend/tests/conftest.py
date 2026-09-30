import os

os.environ["LOGIRAD_DATABASE_URL"] = "sqlite://"
os.environ["LOGIRAD_ADMIN_PASSWORD"] = "test-admin-pw"
os.environ["LOGIRAD_JWT_SECRET"] = "test-secret-0123456789abcdef0123456789"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app import db as db_module


@pytest.fixture()
def client(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = os.environ.get("LOGIRAD_TEST_DATABASE_URL")
    if url:  # e.g. run the suite against PostgreSQL
        engine = create_engine(url)
        from app.db import Base
        from sqlalchemy import text
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    import app.main as main
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", Session)

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    main.app.dependency_overrides[db_module.get_db] = override
    with TestClient(main.app) as c:
        yield c
    main.app.dependency_overrides.clear()


@pytest.fixture()
def admin(client):
    r = client.post("/api/auth/login", data={"username": "admin@logirad.local", "password": "test-admin-pw"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


GOOD_RFQ = {
    "contact_name": "Ali", "contact_email": "ali@example.com", "contact_phone": "+971500000000",
    "company_name": "Ali Trading", "origin_country": "cn", "origin_city": "Shanghai",
    "destination_country": "AE", "destination_city": "Dubai", "mode": "ocean_fcl",
    "commodity": "Furniture", "weight_kg": 18000, "containers": "1x40HC", "incoterm": "FOB",
    "ready_date": "2026-11-01",
}
