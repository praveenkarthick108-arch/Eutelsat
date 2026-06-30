import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from database import get_db
import models

router = APIRouter()

_TOOL_ROOT = Path(__file__).parent.parent
_FRAMEWORK_ROOT = _TOOL_ROOT.parent / "eutelsat-sit-framework"

_MODULE_FOLDER = {
    "Customer Portal":           "customer-portal",
    "Contracts / CIM":           "contracts-cim",
    "CPQ / EPC":                 "cpq-epc",
    "Order Management":          "order-management",
    "Billing / Charging":        "billing-charging",
    "Inv. & Accounting":         "inv-accounting",
    "API / Integration":         "api-integration",
    "Provisioning / Activation": "api-integration",
    "ServiceNow / ITSM":         "api-integration",
}


def _check_cmd(cmd: str) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=10, shell=True)
        return r.returncode == 0
    except Exception:
        return False


def _run_cmd(cmd: str, cwd: Path, timeout: int = 120):
    try:
        r = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True,
            text=True, timeout=timeout, shell=True,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return -1, f"Timed out after {timeout}s — the SIT environment may be unreachable."
    except Exception as e:
        return -1, str(e)


# ── Prerequisite check ────────────────────────────────────────────────────────

@router.get("/framework/check")
def check_framework():
    fw = _FRAMEWORK_ROOT

    # 1. Framework folder
    fw_ok = fw.exists()

    # 2. sit.env — AUTH_TOKEN filled in
    env_file = fw / "config" / "sit.env"
    sit_ok, sit_detail = False, "config/sit.env not found"
    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
        m = re.search(r'^AUTH_TOKEN=(.+)$', content, re.M)
        if m and m.group(1).strip():
            sit_ok = True
            sit_detail = "AUTH_TOKEN is set"
        else:
            sit_detail = "AUTH_TOKEN is empty — fill in eutelsat-sit-framework/config/sit.env"

    # 3. Node.js
    node_ok = _check_cmd("node --version")

    # 4. Newman — local install takes priority over global
    newman_bin = (fw / "api-tests" / "node_modules" / ".bin" / "newman.cmd").exists() or \
                 (fw / "api-tests" / "node_modules" / ".bin" / "newman").exists()
    newman_global = _check_cmd("newman --version")
    newman_ok = newman_bin or newman_global
    newman_detail = "Ready" if newman_ok else "Not installed — run: cd api-tests && npm install"

    # 5. Playwright
    pw_ok = (fw / "ui-tests" / "node_modules" / "@playwright" / "test").exists()
    pw_detail = "Ready" if pw_ok else "Not installed — run: cd ui-tests && npm install && npx playwright install chromium"

    # 6. pytest
    pytest_ok = _check_cmd(f'"{sys.executable}" -m pytest --version')
    pytest_detail = "Ready" if pytest_ok else "Not installed — run: pip install -r e2e-tests/requirements.txt"

    return {
        "framework_root": str(fw),
        "checks": {
            "framework":  {"ok": fw_ok,      "label": "Framework folder",       "detail": str(fw) if fw_ok else "Not found next to eutelsat-testgen"},
            "sit_env":    {"ok": sit_ok,      "label": "SIT credentials",        "detail": sit_detail},
            "node":       {"ok": node_ok,     "label": "Node.js",                "detail": "Installed" if node_ok else "Install from nodejs.org"},
            "newman":     {"ok": newman_ok,   "label": "Newman (API runner)",    "detail": newman_detail},
            "playwright": {"ok": pw_ok,       "label": "Playwright (UI runner)", "detail": pw_detail},
            "pytest":     {"ok": pytest_ok,   "label": "pytest (E2E runner)",    "detail": pytest_detail},
        },
        "can_run": {
            "postman":    fw_ok and node_ok and newman_ok,
            "playwright": fw_ok and node_ok and pw_ok,
            "python":     fw_ok and pytest_ok,
        },
    }


# ── Run tests ─────────────────────────────────────────────────────────────────

@router.post("/framework/run/{session_id}")
def run_framework_tests(
    session_id: int,
    script_type: Literal["postman", "playwright", "python"] = Query(default="postman"),
    db: DBSession = Depends(get_db),
):
    """Run exported test scripts against SIT. Blocks until complete (max 2 min)."""
    if not _FRAMEWORK_ROOT.exists():
        raise HTTPException(status_code=404, detail="Framework folder not found")

    sess = db.query(models.GenerationSession).filter(models.GenerationSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    module_folder = _MODULE_FOLDER.get(sess.module, "api-integration")

    if script_type == "postman":
        api_dir = _FRAMEWORK_ROOT / "api-tests"
        col_dir = api_dir / "collections" / module_folder
        if not col_dir.exists() or not list(col_dir.glob("*.json")):
            raise HTTPException(
                status_code=400,
                detail=f"No Postman collections in api-tests/collections/{module_folder}/. Export the script first."
            )
        returncode, output = _run_cmd(
            f"node run-api-tests.js --module {module_folder}",
            cwd=api_dir, timeout=120,
        )

    elif script_type == "playwright":
        ui_dir = _FRAMEWORK_ROOT / "ui-tests"
        test_dir = ui_dir / "tests" / module_folder
        if not test_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"No Playwright tests in ui-tests/tests/{module_folder}/. Export the script first."
            )
        returncode, output = _run_cmd(
            f"npx playwright test tests/{module_folder} --reporter=list",
            cwd=ui_dir, timeout=120,
        )

    else:  # python
        e2e_dir = _FRAMEWORK_ROOT / "e2e-tests"
        returncode, output = _run_cmd(
            f'"{sys.executable}" -m pytest --tb=short -v',
            cwd=e2e_dir, timeout=120,
        )

    # Parse pass/fail counts from output
    passed, failed = 0, 0
    m = re.search(r'(\d+) passed', output)
    if m: passed = int(m.group(1))
    m = re.search(r'(\d+) failed', output)
    if m: failed = int(m.group(1))
    # Newman custom runner format: "X passed, Y failed"
    m = re.search(r'Total passed\s*:\s*(\d+)', output)
    if m: passed = int(m.group(1))
    m = re.search(r'Total failed\s*:\s*(\d+)', output)
    if m: failed = int(m.group(1))

    # Find report file
    report_path = None
    reports_dir = _FRAMEWORK_ROOT / "reports"
    if script_type == "postman":
        files = sorted(reports_dir.glob("api-*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            report_path = "reports/" + files[0].name
    elif script_type == "playwright":
        rp = reports_dir / "playwright-report" / "index.html"
        if rp.exists():
            report_path = "reports/playwright-report/index.html"
    else:
        rp = reports_dir / "e2e-report.html"
        if rp.exists():
            report_path = "reports/e2e-report.html"

    return {
        "script_type": script_type,
        "module": sess.module,
        "returncode": returncode,
        "passed": passed,
        "failed": failed,
        "output": output[-6000:] if len(output) > 6000 else output,
        "report_path": report_path,
        "success": returncode == 0,
    }
