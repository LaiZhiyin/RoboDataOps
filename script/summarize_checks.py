"""Publish measured pytest results, not hand-entered success counts."""

import json
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

root = Path(__file__).resolve().parents[1]
suite = ET.parse(root / "reports/junit.xml").getroot().find("testsuite")
cov = json.loads((root / "reports/coverage.json").read_text())
validation = json.loads((root / "reports/validation.json").read_text())
summary = {
    "release": "1.0.0",
    "generated_at": datetime.now(UTC).isoformat(),
    "tests": int(suite.attrib["tests"]),
    "failures": int(suite.attrib["failures"]),
    "errors": int(suite.attrib["errors"]),
    "skipped": int(suite.attrib["skipped"]),
    "coverage_percent": round(cov["totals"]["percent_covered"], 2),
    "oracle_scenarios": validation["planning"]["scenarios"],
    "public_episodes": validation["public_sample"]["episodes"],
    "public_frames": validation["public_sample"]["frames"],
    "browser": json.loads((root / "reports/browser-smoke.json").read_text()),
    "notice": "Actual local pytest and browser run. Remote CI evidence is linked separately in GitHub Actions. No human or policy effectiveness claim.",
}
if summary["failures"] or summary["errors"]:
    raise SystemExit("Refusing to publish a passing summary from failing tests")
(root / "reports/test-summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False))
