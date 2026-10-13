from pathlib import Path
from tempfile import TemporaryDirectory

from roadguard.storage import IncidentStore


def test_incident_store_persists_and_reads_events() -> None:
    with TemporaryDirectory(prefix="roadguard-storage-test-") as directory:
        store = IncidentStore(Path(directory))
        incident = store.create(
            source="camera-0",
            label="accident",
            confidence=0.87,
            snapshot_path="snapshots/incident.jpg",
        )

        assert incident["id"] > 0
        assert incident["source"] == "camera-0"
        assert incident["confidence"] == 0.87
        assert store.get(incident["id"]) == incident
        assert store.list_recent() == [incident]
        assert store.get(incident["id"] + 1) is None


def test_incident_store_closes_database_connections() -> None:
    with TemporaryDirectory(prefix="roadguard-storage-cleanup-test-") as directory:
        store = IncidentStore(Path(directory))
        store.create("camera-0", "accident", 0.87, None)
        store.list_recent()

    assert not Path(directory).exists()
