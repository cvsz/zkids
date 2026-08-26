import json
import threading
import time
import urllib.request
from pathlib import Path

from zkid.config import FactoryConfig
from zkid.db import Database, FactoryRepository
from zkid.models import EpisodeScript
from zkid.web.server import make_handler, serve  # noqa: F401
from zkid.web.server import ZkidWebServer
from http.server import ThreadingHTTPServer


def _seed(tmp_path: Path) -> FactoryConfig:
    cfg = FactoryConfig.load(root=tmp_path)
    db = Database(cfg.db_path)
    repo = FactoryRepository(db)
    repo.save_episode_script(
        EpisodeScript(
            episode_id="EPW1",
            title="Web Test",
            learning_goal="colors",
            scenes=[{"scene_id": "S001", "duration_target": 8.0, "action": "wave"}],
        )
    )
    db.close()
    return cfg


def _start(cfg, token):
    app = ZkidWebServer(cfg, token)
    index = (Path(__file__).parents[1] / "src" / "zkid" / "web" / "static" / "index.html").read_text()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app, index))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return app, port, httpd


def _get(port, path, headers=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode())


def _post(port, path, payload, headers=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def test_web_endpoints(tmp_path):
    cfg = _seed(tmp_path)
    _, port, httpd = _start(cfg, token="secret1")
    time.sleep(0.2)

    code, body = _get(port, "/api/health")
    assert code == 200 and body["ok"]

    code, body = _get(port, "/api/episodes")
    assert code == 200 and any(e["episode_id"] == "EPW1" for e in body["episodes"])

    code, body = _get(port, "/api/status?ep=EPW1")
    assert code == 200 and body["title"] == "Web Test"
    assert len(body["gates"]) == 5

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as r:
        assert r.status == 200
        assert b"zkid" in r.read()

    code, body = _post(port, "/api/produce", {"topic": "x"})
    assert code == 403

    code, body = _post(port, "/api/produce", {"topic": ""}, {"X-Auth-Token": "secret1"})
    assert code == 400

    code, body = _post(port, "/api/produce", {"topic": "Mimi waves hello", "ep": "../evil"}, {"X-Auth-Token": "secret1"})
    assert code == 400

    code, body = _post(port, "/api/produce", {"topic": "Mimi waves hello", "ep": "EPW9", "draft": True, "auto_approve": True}, {"X-Auth-Token": "secret1"})
    assert code == 202
    task_id = body["task"]["task_id"]
    for _ in range(180):
        code, body = _get(port, f"/api/tasks/{task_id}")
        if body["state"] != "running":
            break
        time.sleep(1)
    assert body["state"] == "done"
    assert body["returncode"] == 0
    httpd.shutdown()


def test_media_traversal_blocked(tmp_path):
    cfg = _seed(tmp_path)
    _, port, httpd = _start(cfg, token=None)
    time.sleep(0.2)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/media/..%2f..%2fetc%2fpasswd", timeout=10)
        raise AssertionError("traversal should fail")
    except urllib.error.HTTPError as e:
        assert e.code in (404, 400)
    finally:
        httpd.shutdown()
