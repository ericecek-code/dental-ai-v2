import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.routes import results as results_route


def test_get_result_feedback_is_list_not_dict(tmp_path, monkeypatch):
    """Frontend (api.ts) deklaráje feedback ako pole a volá na nom .forEach().

    Backend vracal dict {index: status} -> JSON objekt -> TypeError v prehliadači,
    výsledok analýzy sa zahodil a obraz snímky zmizol z obrazovky.
    """
    job_id = "0123456789ab"
    payload = {"job_id": job_id, "filename": "x.jpg", "count": 1, "findings": []}
    p = tmp_path / f"{job_id}.json"
    p.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(results_route, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(results_route, "get_feedback", lambda _j: {2: "confirmed"})

    data = results_route.get_result(job_id)

    assert isinstance(data["feedback"], list), "feedback musí byť pole, nie objekt/dict"
    assert data["feedback"] == [{"index": 2, "status": "confirmed"}]
    # index musí zostať číslo, nie string (JSON objekt by ho zmenil na kľúč)
    assert isinstance(data["feedback"][0]["index"], int)


def test_get_result_feedback_empty_is_list(tmp_path, monkeypatch):
    job_id = "0123456789ab"
    (tmp_path / f"{job_id}.json").write_text(json.dumps({"job_id": job_id}), encoding="utf-8")
    monkeypatch.setattr(results_route, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(results_route, "get_feedback", lambda _j: {})

    data = results_route.get_result(job_id)

    assert data["feedback"] == []
