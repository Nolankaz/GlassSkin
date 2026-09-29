"""HTTP route checks with in-memory external dependencies."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main
from services.treatment_research import RESEARCH_VERSION, TreatmentResearchError
from services.treatment_simulation import DEFAULT_DURATION_DAYS, SIMULATION_PARAMETER_VERSION, run_profile_simulation
from simulation.models import SKIN_METRIC_NAMES
from simulation.parameters import available_treatment_ids


def profile_row(**overrides):
    row = {"id": 1, "name": "Synthetic test profile", "age": 30, "gender": "Not specified", **{metric: 5 for metric in SKIN_METRIC_NAMES}}
    row["inflammatory_acne"] = 8
    row.update(overrides)
    return row


class FakeQuery:
    def __init__(self, db, table_name):
        self.db = db
        self.table_name = table_name
        self.filters = []
        self.operation = "select"
        self.payload = None

    def select(self, *_args): return self
    def order(self, *_args, **_kwargs): return self
    def limit(self, *_args): return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def execute(self):
        rows = self.db.rows[self.table_name]
        matches = [row for row in rows if all(row.get(column) == value for column, value in self.filters)]
        if self.operation == "select": return SimpleNamespace(data=matches)

        self.db.writes.append((self.table_name, self.operation, self.payload))
        if self.operation == "insert":
            rows.append(self.payload)
            return SimpleNamespace(data=[self.payload])
        if self.operation == "update":
            for row in matches: row.update(self.payload)
            return SimpleNamespace(data=matches)
        self.db.rows[self.table_name] = [row for row in rows if not all(row.get(column) == value for column, value in self.filters)]
        return SimpleNamespace(data=[])


class FakeSupabase:
    def __init__(self):
        self.rows: dict[str, list[dict]] = {"skin_profiles": [profile_row()], "treatment_research_results": []}
        self.writes: list[tuple[str, str, object]] = []

    def table(self, name): return FakeQuery(self, name)


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(main, "supabase", fake)
    return fake


@pytest.fixture(autouse=True)
def generator_must_not_run(monkeypatch):
    async def fail_generation(*_args, **_kwargs):
        pytest.fail("Treatment generation should not run in this test")

    monkeypatch.setattr(main, "generate_treatment_options", fail_generation)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_simulation_catalogue(client):
    response = client.get("/simulation/treatments")
    assert response.status_code == 200
    assert tuple(item["treatment_id"] for item in response.json()) == available_treatment_ids(SIMULATION_PARAMETER_VERSION)


def test_simulation_response_matches_service(client, fake_db):
    response = client.get("/profiles/1/simulations/tretinoin")
    expected = run_profile_simulation(fake_db.rows["skin_profiles"][0], "tretinoin", DEFAULT_DURATION_DAYS)
    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


def test_simulation_unknown_profile(client):
    response = client.get("/profiles/999/simulations/tretinoin")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_simulation_unknown_treatment(client):
    response = client.get("/profiles/1/simulations/not_a_treatment")
    assert response.status_code == 404
    assert all(treatment_id in response.json()["detail"] for treatment_id in available_treatment_ids(SIMULATION_PARAMETER_VERSION))


@pytest.mark.parametrize("duration_days", [27, 169])
def test_simulation_duration_bounds(client, fake_db, duration_days):
    response = client.get(f"/profiles/1/simulations/tretinoin?duration_days={duration_days}")
    assert response.status_code == 422
    assert fake_db.writes == []


def test_profile_not_found(client):
    response = client.get("/profiles/999")
    assert response.status_code == 404


def test_profile_patch_age_matches_creation_bounds(client, fake_db):
    valid = client.patch("/profiles/1", json={"age": 5})
    assert valid.status_code == 200
    assert fake_db.rows["skin_profiles"][0]["age"] == 5

    invalid = client.patch("/profiles/1", json={"age": 121})
    assert invalid.status_code == 422


def test_cached_research_post_is_read_only(client, fake_db):
    cached_result = {"options": [{
        "treatment_name": "Synthetic test option",
        "treatment_type": "topical",
        "why_it_may_fit": "Test rationale",
        "prescription_required": False,
        "key_benefits": ["Test benefit"],
        "key_risks": ["Test risk"],
        "evidence_sources": [{"title": "Test source", "url": "https://evidence.invalid/test", "source_name": "Test source"}],
        "confidence": "low",
    }]}
    fake_db.rows["treatment_research_results"].append({"profile_id": 1, "research_version": RESEARCH_VERSION, "result": cached_result})
    response = client.post("/profiles/1/treatment-options")
    assert response.status_code == 200
    assert response.json()["result"] == cached_result
    assert fake_db.writes == []


def test_research_generation_get_is_gone(client):
    response = client.get("/profiles/1/treatment-options")
    assert response.status_code == 405
    assert "POST" in response.headers["allow"]


def test_research_unknown_profile(client):
    response = client.post("/profiles/999/treatment-options")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


def test_research_generation_failure_returns_502(client, fake_db, monkeypatch):
    async def fail_generation(_profile):
        raise TreatmentResearchError("Synthetic test failure")

    monkeypatch.setattr(main, "generate_treatment_options", fail_generation)
    response = client.post("/profiles/1/treatment-options")
    assert response.status_code == 502
    assert fake_db.writes == []


def test_saved_research_miss_is_read_only(client, fake_db):
    response = client.get("/profiles/1/treatment-options/saved")
    assert response.status_code == 200
    assert response.json()["result"] is None
    assert fake_db.writes == []
