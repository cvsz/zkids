import json

from zkid.db import Database, FactoryRepository
from zkid.pipeline.gates import GateBlocked, GateKeeper
from zkid.pipeline.factory import EpisodeFactory
from zkid.schema_export import export_schemas


def test_schema_export(tmp_path):
    files = export_schemas(tmp_path / "schemas")
    names = [f.name for f in files]
    assert "series-bible.schema.json" in names
    assert "scene-manifest.schema.json" in names
    assert json.loads(files[0].read_text())["type"] == "object"


def test_gate_keeper_flow():
    db = Database(":memory:")
    repo = FactoryRepository(db)
    keeper = GateKeeper(repo)
    try:
        keeper.require(5, "EP001")
        raise AssertionError("gate 5 should block")
    except GateBlocked:
        pass
    keeper.approve(5, "EP001", note="ok")
    assert keeper.require(5, "EP001") is True


def test_gate_draft_auto_approve():
    db = Database(":memory:")
    repo = FactoryRepository(db)
    keeper = GateKeeper(repo, auto_approve_in_draft=[1, 2])
    assert keeper.require(1, "EP001", draft_mode=True) is True
    assert repo.gate_status(1, "EP001")["status"] == "approved"
