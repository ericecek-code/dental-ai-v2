import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ml.reporter import generate_patient_report


def test_generate_patient_report(tmp_path):
    out = str(tmp_path / "report.pdf")
    findings = [
        {"label_sk": "Karies", "severity": "urgent", "confidence": 0.93},
        {"label_sk": "Zápal ďasien", "severity": "watch", "confidence": 0.61},
    ]
    result = generate_patient_report(out, "panorama.jpg", findings)
    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 500
