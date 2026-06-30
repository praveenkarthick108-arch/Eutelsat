import os
import sys
import json
import re
import warnings
import httpx
from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
from openai import OpenAI
from dotenv import load_dotenv

# ── Module auto-detection ──────────────────────────────────────────────────────

_MODULE_KEYWORDS = {
    "Customer Portal": ["portal", "customer 360", "community cloud", "dp-sub", "user access", "inventory", "hierarchy", "data allowance", "capped data"],
    "Contracts / CIM": ["contract", "cim", "gcrm", "account setup", "agreement", "dp specific option", "contract model", "contract rule"],
    "CPQ / EPC": ["cpq", "epc", "pricing", "catalogue", "catalog", "zuora", "product structure", "network slice", "product catalogue", "product pricing"],
    "Order Management": ["order management", "order journey", "celfocus", "activation journey", "renewal", "termination", "undisclosed mode", "order journey"],
    "Provisioning / Activation": ["provisioning", "provision", "axiros", "device", "terminal", "commissioning", "deactivation", "suspension", "activation"],
    "Billing / Charging": ["billing", "billing model", "re-rating", "re rating", "obrm", "o-brm", "brm", "true-up", "credits", "rating engine", "bill override"],
    "Inv. & Accounting": ["invoice", "invoicing", "sap", "s4hana", "accounting", "tax calculation", "s/4hana", "invoice generation"],
    "API / Integration": ["api", "integration", "mulesoft", "sync", "federation", "middleware", "cdr", "callback", "webhook", "catalogue sync", "account federation"],
    "ServiceNow / ITSM": ["servicenow", "service now", "itsm", "incident", "change request", "sla", "problem management", "release readiness"],
}

_ALL_MODULES = list(_MODULE_KEYWORDS.keys())

TEST_TYPES_MULTI = ["Functional", "API/Integration", "Regression", "UAT", "End-to-End (E2E)"]
TC_TYPE_PREFIX = {
    "Functional": "FUNC", "API/Integration": "INTG", "Regression": "REGR",
    "UAT": "UAT", "End-to-End (E2E)": "E2E",
}


def detect_module(feature_title: str, description: str = "") -> str:
    """Auto-detect the BSS/OSS module using keyword matching, falling back to AI."""
    text = f"{feature_title} {description}".lower()
    best_module, best_score = "Customer Portal", 0
    for module, keywords in _MODULE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score, best_module = score, module
    if best_score >= 1:
        return best_module
    # AI fallback
    try:
        prompt = (
            f"You are a BSS/OSS architect for the Eutelsat CxP programme.\n"
            f"Classify this feature into ONE of these modules:\n{json.dumps(_ALL_MODULES)}\n\n"
            f"Feature: {feature_title}\nDescription: {description[:300]}\n\n"
            f"Return ONLY the module name exactly as listed, nothing else."
        )
        result = _call(prompt, max_tokens=60).strip().strip('"\'')
        if result in _MODULE_KEYWORDS:
            return result
    except Exception:
        pass
    return best_module

def _p(s: str) -> None:
    """Print safely on Windows cp1252 consoles — LLM output may contain arbitrary Unicode."""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", "replace").decode("ascii"))

load_dotenv()

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

def _make_client() -> OpenAI:
    """Create a fresh OpenAI client per call — httpx.Client is not thread-safe under concurrent use."""
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
        http_client=httpx.Client(verify=False),
    )

# Module-level client kept only for backward-compat imports (routes/generate.py, main.py)
client = _make_client()

MODEL = "openai/gpt-oss-20b"

SYSTEM_STACK = (
    "GEO Community Cloud Portal, GCRM Salesforce (contracts), Zuora (CPQ/billing/re-rating), "
    "GEO Salesforce + Celfocus OM (order management), Axiros (LEO device provisioning), "
    "Oracle BRM / O-BRM (billing engine), SAP S4HANA (invoicing/accounting), "
    "MuleSoft LEO (integration middleware), ServiceNow (ITSM/incident management)"
)

E2E_CHAIN = (
    "GEO Community Cloud Portal → GCRM Salesforce (contract) → Zuora CPQ (pricing) "
    "→ GEO Salesforce / Celfocus OM (order execution) → Axiros (device provisioning) "
    "→ Oracle BRM (rating/billing) → SAP S4HANA (invoicing) → ServiceNow (ITSM)"
)

# ── Feature 3: Out-of-scope detection ─────────────────────────────────────────

_OUT_OF_SCOPE = [
    (["unit test", "unit testing", "component test"],
     "Component/unit testing is out of scope for Lot B. Lot B covers E2E, Integration, Regression, Performance (API), and UAT only."),
    (["data migration test", "migration testing", "etl test"],
     "Data migration testing is out of scope for Lot B."),
    (["security test", "pen test", "penetration test", "security scan", "vulnerability"],
     "Security/penetration testing is out of scope for Lot B."),
    (["geo stack regression", "geo regression", "geo stack test"],
     "GEO stack regression is out of scope — Lot B covers the LEO hybrid stack only."),
    (["legacy stack", "legacy system test", "legacy regression"],
     "Legacy stack testing is out of scope for Lot B."),
]


def check_out_of_scope(feature_title: str, test_type: str, description: str = "") -> str:
    """Return a warning string if the request is out of Lot B scope, else empty string."""
    text = f"{feature_title} {test_type} {description}".lower()
    for patterns, warning in _OUT_OF_SCOPE:
        if any(p in text for p in patterns):
            return warning
    return ""


def _call(prompt: str, max_tokens: int = 4096) -> str:
    c = _make_client()
    completion = c.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        top_p=1,
        max_tokens=max_tokens,
        stream=False,
    )
    return completion.choices[0].message.content


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*", "", text).strip("` \n")
    try:
        return json.loads(text)
    except Exception:
        pass
    for pattern in (r"(\[[\s\S]*\])", r"(\{[\s\S]*\})"):
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                continue
    raise ValueError(f"No valid JSON found in response: {text[:300]}")


# ── Agent 1: Scout ────────────────────────────────────────────────────────────

def scout_agent(
    feature_title: str,
    module: str,
    test_type: str,
    rag_context: str = "",
    release: str = "R1",
    chain_mode: bool = False,
    num_areas: int = 7,
) -> list[str]:
    """Identify distinct test scenario areas."""
    from scope_data import RELEASES
    rel = RELEASES.get(release, RELEASES["R1"])
    release_block = (
        f"\nRelease context: {rel['name']} — {rel['focus']}\n"
        f"Test focus: {', '.join(rel['test_focus'])}\n"
    )
    context_block = f"\nProject documentation context:\n{rag_context}\n" if rag_context else ""

    if chain_mode:
        prompt = f"""You are a senior QA architect for the Eutelsat CxP programme.
Full E2E chain: {E2E_CHAIN}
{release_block}{context_block}
Identify exactly {num_areas} cross-system E2E scenario areas for the feature below.
Each area MUST span at least 3 systems in the chain and represent a business-critical journey.

Feature: {feature_title}
Test Type: {test_type}

Return ONLY a JSON array of {num_areas} strings — no markdown:
["scenario area 1", ..., "scenario area {num_areas}"]"""
    else:
        prompt = f"""You are a senior QA architect for the Eutelsat CxP BSS/OSS programme.
Full hybrid stack: {SYSTEM_STACK}
{release_block}{context_block}
Identify exactly {num_areas} distinct test scenario areas for thorough {test_type} coverage.

Module: {module}
Feature: {feature_title}
Test Type: {test_type}

Each area must cover happy paths, edge cases, negatives, and integration points.
Reference actual systems (Celfocus, Axiros, Zuora, Oracle BRM, SAP S4HANA, MuleSoft) where relevant.
Return ONLY a JSON array of {num_areas} strings — no markdown:
["scenario area 1", ..., "scenario area {num_areas}"]"""

    try:
        response = _call(prompt, max_tokens=700)
        areas = _extract_json(response)
        if isinstance(areas, list) and len(areas) > 0:
            return [str(a) for a in areas[:num_areas + 1]]
    except Exception as e:
        _p(f"[Scout Agent] Error: {e}")

    fallback = [
        f"Core {feature_title} happy path",
        "Input validation and boundary conditions",
        "Error handling and negative scenarios",
        "Integration with downstream BSS/OSS systems",
        "Data integrity and persistence verification",
        "Concurrent operations and race conditions",
        "Performance and SLA compliance",
    ]
    return fallback[:num_areas]


# ── Agent 2: Generator ────────────────────────────────────────────────────────

def generator_agent(
    area: str,
    feature_title: str,
    module: str,
    test_type: str,
    count: int = 5,
    rag_context: str = "",
    release: str = "R1",
    chain_mode: bool = False,
) -> list[dict]:
    """Generate test cases — UAT gets business format, chain mode gets cross-system steps."""
    from scope_data import RELEASES, KPI_TARGETS
    rel = RELEASES.get(release, RELEASES["R1"])
    context_block = f"\nProject documentation:\n{rag_context}\n" if rag_context else ""

    is_uat = test_type.upper() in ("UAT", "UAT GOVERNANCE", "BUSINESS TESTING")

    if is_uat:
        # Feature 2: UAT business format
        prompt = f"""You are a UAT coordinator for the Eutelsat CxP programme ({rel['name']}).
Full hybrid stack: {SYSTEM_STACK}
{context_block}
Generate exactly {count} UAT test cases in BUSINESS format for:

Feature: {feature_title}
Module: {module}
Business Scenario Area: {area}

UAT test cases must be written for business users (not technical testers).
Use plain business language, reference business outcomes not technical calls.

Return ONLY a JSON array — no markdown:
[
  {{
    "description": "Business scenario: as a [role], verify that [business outcome]",
    "steps": "1. As [business role], [action in business terms]\\n2. Confirm [business state]\\n3. Validate [business outcome]\\n4. Sign off [acceptance criteria]",
    "expected_result": "Acceptance criteria: [specific measurable business outcome]",
    "automation_candidate": false,
    "automation_notes": "Business-led UAT — requires human judgment, manual execution only"
  }}
]

Rules:
- Written for non-technical business users
- Steps reference the business process, not API calls
- Expected result is an acceptance criteria statement
- automation_candidate is always false for UAT"""

    elif chain_mode:
        # Feature 5: E2E chain mode
        prompt = f"""You are a senior QA engineer for the Eutelsat CxP programme ({rel['name']}).
Full E2E chain: {E2E_CHAIN}
KPI targets: API response <2s, billing accuracy >=90%, ordering automation >=90%.
{context_block}
Generate exactly {count} E2E chain test cases that trace the FULL system chain for:

Feature: {feature_title}
E2E Scenario Area: {area}

Each test case MUST:
- Have steps that explicitly move data/state through at least 4 systems in the chain
- Reference specific system names (Portal, Salesforce, Zuora, Celfocus, Axiros, O-BRM, SAP)
- Include verification at each system handoff point

Return ONLY a JSON array — no markdown:
[
  {{
    "description": "Verify that [end-to-end business flow] across [systems]",
    "steps": "1. In GEO Community Cloud Portal, [action]\\n2. Verify GCRM Salesforce [state]\\n3. Confirm Zuora [action]\\n4. Check Celfocus OM [state]\\n5. Verify Axiros provisioning [outcome]\\n6. Confirm O-BRM billing [result]\\n7. Validate SAP invoice [state]",
    "expected_result": "System should [end state] with data consistent across Portal, Zuora, Celfocus, O-BRM and SAP",
    "automation_candidate": true,
    "automation_notes": "API chain test — REST-Assured for each integration point, Jenkins CI/CD pipeline"
  }}
]"""

    else:
        kpi_block = (
            f"KPIs: ordering automation {KPI_TARGETS['ordering_automation']}, "
            f"billing accuracy {KPI_TARGETS['billing_accuracy']}, "
            f"API response {KPI_TARGETS['api_response_time']}."
        )
        prompt = f"""You are a senior QA engineer for the Eutelsat CxP BSS/OSS programme ({rel['name']}).
Full hybrid stack: {SYSTEM_STACK}
{kpi_block}
{context_block}
Generate exactly {count} {test_type} test cases for:

Feature: {feature_title}
Module: {module}
Scenario Area: {area}

Return ONLY a JSON array — no markdown:
[
  {{
    "description": "Verify that ...",
    "steps": "1. Step one\\n2. Step two\\n3. Step three\\n4. Step four",
    "expected_result": "System should ...",
    "automation_candidate": true,
    "automation_notes": "Brief rationale: e.g. API-driven REST-Assured / Selenium UI flow / manual judgment required"
  }}
]

Rules:
- description MUST start with "Verify that"
- Steps: 4–6 numbered, specific, reference actual systems where relevant
- automation_candidate: true if predictable inputs/outputs, stable UI/API flows; false if exploratory or subjective
- automation_notes: one sentence — which framework (Selenium/REST-Assured/Appium) or why manual"""

    try:
        resp = _call(prompt, max_tokens=2048)
        cases = _extract_json(resp)
        if isinstance(cases, list):
            return cases
    except Exception as e:
        _p(f"[Generator Agent] Area error: {e}")

    return [{
        "description": f"Verify that {area.lower()}",
        "steps": "1. Navigate to the feature\n2. Execute the action\n3. Observe the result\n4. Verify state",
        "expected_result": "System behaves as expected per requirements",
        "automation_candidate": False,
        "automation_notes": "Fallback case — review manually",
    }]


# ── Agent 3: Reviewer ─────────────────────────────────────────────────────────

def _assign_priorities_batch(batch: list[dict], test_type: str) -> list[dict]:
    n = len(batch)
    cases_json = json.dumps(batch, indent=2)
    prompt = f"""You are a senior QA lead for the Eutelsat CxP programme.

Assign a priority (High / Medium / Low) to each of these {n} {test_type} test cases.
Do NOT remove or reorder any — return all {n} items.
Priority: ~30% High (critical path, revenue impact), ~50% Medium, ~20% Low (edge cases).

Return ONLY a JSON array of exactly {n} objects — no markdown:
[{{"description":"...","steps":"...","expected_result":"...","priority":"High","automation_candidate":true,"automation_notes":"..."}}]

Test cases:
{cases_json}"""

    try:
        response = _call(prompt, max_tokens=2048)
        reviewed = _extract_json(response)
        if isinstance(reviewed, list) and len(reviewed) == n:
            return reviewed
        if isinstance(reviewed, list) and len(reviewed) > 0:
            for i, orig in enumerate(batch):
                if i < len(reviewed):
                    orig["priority"] = reviewed[i].get("priority", "Medium")
            return batch
    except Exception as e:
        _p(f"[Reviewer Batch] Error: {e}")

    priorities = ["High", "High", "Medium", "Medium", "Medium", "Low"]
    for i, case in enumerate(batch):
        case.setdefault("priority", priorities[i % len(priorities)])
    return batch


def reviewer_agent(all_cases: list[dict], test_type: str) -> list[dict]:
    BATCH_SIZE = 25
    total = len(all_cases)
    if total == 0:
        return all_cases
    if total <= BATCH_SIZE:
        _p(f"      Reviewing {total} cases...")
        return _assign_priorities_batch(all_cases, test_type)
    _p(f"      Large set ({total}) - batching...")
    result = []
    for start in range(0, total, BATCH_SIZE):
        batch = all_cases[start: start + BATCH_SIZE]
        _p(f"        Batch {start // BATCH_SIZE + 1}: {start+1}-{start+len(batch)}")
        result.extend(_assign_priorities_batch(batch, test_type))
    return result


# ── Agent 4: Evaluator ────────────────────────────────────────────────────────

def _evaluate_batch(batch: list[dict], module: str, test_type: str) -> list[dict]:
    n = len(batch)
    cases_json = json.dumps(
        [{"description": c.get("description", ""), "steps": c.get("steps", "")[:200]} for c in batch],
        indent=2
    )
    prompt = f"""You are a QA quality assessor for the Eutelsat CxP programme.
Module: {module} | Test Type: {test_type}

Evaluate each test case:
1. confidence_score (0.0–1.0): 0.9+ clear & testable, 0.7–0.8 reasonable, 0.5–0.6 uncertain, <0.5 speculative
2. hallucination_risk: Low (generic telecom pattern) / Medium (feature-specific, needs confirmation) / High (very specific, unverifiable without system access)

Return ONLY a JSON array of {n} objects — no markdown:
[{{"confidence_score": 0.85, "hallucination_risk": "Low"}}]

Test cases:
{cases_json}"""

    try:
        response = _call(prompt, max_tokens=2048)
        evals = _extract_json(response)
        if isinstance(evals, list):
            for i, case in enumerate(batch):
                ev = evals[i] if i < len(evals) else {}
                case["confidence_score"] = round(float(ev.get("confidence_score", 0.82)), 2)
                case["hallucination_risk"] = ev.get("hallucination_risk", "Low")
            return batch
    except Exception as e:
        _p(f"[Evaluator Batch] Error: {e}")

    for case in batch:
        case.setdefault("confidence_score", 0.82)
        case.setdefault("hallucination_risk", "Low")
    return batch


def evaluator_agent(all_cases: list[dict], module: str, test_type: str) -> list[dict]:
    BATCH_SIZE = 20
    total = len(all_cases)
    if total == 0:
        return all_cases
    if total <= BATCH_SIZE:
        _p(f"      Evaluating {total} cases...")
        return _evaluate_batch(all_cases, module, test_type)
    result = []
    for start in range(0, total, BATCH_SIZE):
        result.extend(_evaluate_batch(all_cases[start: start + BATCH_SIZE], module, test_type))
    return result


# ── Follow-up Agent ───────────────────────────────────────────────────────────

def followup_agent(
    query: str,
    feature_title: str,
    module: str,
    test_type: str,
    existing_cases: list[dict],
) -> dict:
    summary = [
        {"tc_id": c.get("tc_id", f"TC-{i+1:03d}"), "description": c.get("description", "")}
        for i, c in enumerate(existing_cases[:15])
    ]
    prompt = f"""You are a QA assistant for the Eutelsat CxP programme.
Feature: {feature_title} | Module: {module} | Type: {test_type}
Existing {len(existing_cases)} test cases (summary):
{json.dumps(summary, indent=2)}

User follow-up: "{query}"

If the user wants MORE test cases, generate 3–5 new ones without duplicating existing ones.
If asking a question, answer concisely.

Return JSON:
{{
  "type": "new_cases",
  "message": "Here are additional test cases focusing on ...",
  "new_cases": [
    {{
      "description": "Verify that ...",
      "steps": "1. ...\\n2. ...\\n3. ...",
      "expected_result": "System should ...",
      "priority": "High",
      "confidence_score": 0.87,
      "hallucination_risk": "Low",
      "automation_candidate": true,
      "automation_notes": "REST-Assured API test"
    }}
  ]
}}
OR
{{
  "type": "answer",
  "message": "Your answer here...",
  "new_cases": []
}}"""

    try:
        response = _call(prompt, max_tokens=3000)
        result = _extract_json(response)
        if isinstance(result, dict) and "type" in result:
            return result
    except Exception as e:
        _p(f"[Followup Agent] Error: {e}")

    return {"type": "answer", "message": "I had trouble processing that. Please try rephrasing.", "new_cases": []}


# ── Agent 5: Automation Script Generator ─────────────────────────────────────

_MODULE_BASE_PATHS = {
    "Customer Portal":           "/api/portal/v1",
    "Contracts / CIM":           "/api/crm/v1",
    "CPQ / EPC":                 "/api/cpq/v1",
    "Order Management":          "/api/orders/v1",
    "Billing / Charging":        "/api/billing/v1",
    "Inv. & Accounting":         "/api/invoicing/v1",
    "API / Integration":         "/api/integration/v1",
    "Provisioning / Activation": "/api/provisioning/v1",
    "ServiceNow / ITSM":         "/api/itsm/v1",
}


def _clean_code(text: str, lang: str) -> str:
    """Strip markdown code fences from LLM output."""
    text = text.strip()
    text = re.sub(rf"^```(?:{lang}|json|javascript|js|python|py)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def _http_method(tc: dict) -> str:
    """Infer HTTP method from test case description/steps."""
    text = f"{tc.get('description','')} {tc.get('steps','')}".lower()
    if any(k in text for k in ["terminat", "delet", "cancel", "deactivat", "remov"]):
        return "DELETE"
    if any(k in text for k in ["creat", "add", "new order", "submit", "set up", "setup", "configure", "provisio", "place"]):
        return "POST"
    if any(k in text for k in ["updat", "amend", "modif", "chang", "edit", "patch", "mid-cycle"]):
        return "PATCH"
    if any(k in text for k in ["full update", "replac", "overwrite"]):
        return "PUT"
    return "GET"


def _gen_postman(feature_title: str, module: str, system: str, tc_json: str) -> str:
    """Build Postman Collection v2.1 JSON programmatically — always valid, never truncated."""
    tc_list = json.loads(tc_json)
    base_path = _MODULE_BASE_PATHS.get(module, "/api/v1")

    # Ask the AI only for short pm.test() assertion strings (one line per TC)
    tc_specs = json.dumps([{"id": tc.get("tc_id", ""), "expected": tc.get("expected_result", "")[:120]} for tc in tc_list], indent=2)
    assert_prompt = (
        "For each test case below, write ONE short pm.test() assertion string (max 120 chars) that checks the expected_result.\n"
        "Format: return ONLY a JSON array of strings, one per test case, in the same order.\n"
        "Each string is a complete pm.test() call, e.g.:\n"
        "  \"pm.test('Order status is Active', function(){pm.expect(pm.response.json().status).to.equal('Active');}});\"\n\n"
        "Test cases:\n"
        + tc_specs
        + f"\n\nReturn ONLY a JSON array of {len(tc_list)} strings — no markdown."
    )

    assertions = []
    try:
        raw = _call(assert_prompt, max_tokens=1200)
        raw = _clean_code(raw, "json")
        parsed = _extract_json(raw)
        if isinstance(parsed, list) and len(parsed) == len(tc_list):
            assertions = [str(a) for a in parsed]
    except Exception:
        pass
    # Fallback assertions
    while len(assertions) < len(tc_list):
        assertions.append("pm.test('Status 200 OK', function(){pm.response.to.have.status(200);});")

    # Build path segments from base_path
    path_parts = [p for p in base_path.strip("/").split("/") if p] + ["{{DP_ID}}"]

    items = []
    for i, tc in enumerate(tc_list):
        method = _http_method(tc)
        body = None
        if method in ("POST", "PUT", "PATCH"):
            body = {"mode": "raw", "raw": "{\"placeholder\": true}", "options": {"raw": {"language": "json"}}}

        item: dict = {
            "name": f"[{tc.get('tc_id','TC')}] {tc.get('description','')[:60]}",
            "event": [{"listen": "test", "script": {
                "exec": [
                    "pm.test('Status OK', function(){pm.response.to.have.status(200);});",
                    assertions[i],
                ],
                "type": "text/javascript",
            }}],
            "request": {
                "method": method,
                "header": [
                    {"key": "Authorization", "value": "Bearer {{AUTH_TOKEN}}"},
                    {"key": "Content-Type",  "value": "application/json"},
                ],
                "url": {
                    "raw": "{{BASE_URL}}" + base_path + "/{{DP_ID}}",
                    "host": ["{{BASE_URL}}"],
                    "path": path_parts,
                },
            },
        }
        if body:
            item["request"]["body"] = body
        items.append(item)

    collection = {
        "info": {
            "name": f"{feature_title} — {module} API Tests",
            "_postman_id": f"eutl-{module[:6].lower().replace(' ', '-').replace('/', '-')}",
            "description": (
                f"Automated API tests for: {feature_title}\n"
                f"Module: {module} | System: {system}\n"
                f"Generated by Eutelsat GenAI Test Case Generator\n\n"
                f"Setup: Set BASE_URL to your SIT environment URL.\n"
                f"Run: newman run <collection.json> --env-var BASE_URL=https://sit.eutelsat.com --env-var AUTH_TOKEN=<token>"
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "BASE_URL",     "value": "https://sit.eutelsat.com", "type": "string"},
            {"key": "AUTH_TOKEN",   "value": "",                          "type": "string"},
            {"key": "DP_ID",        "value": "DP-TEST-001",               "type": "string"},
            {"key": "CONTRACT_ID",  "value": "CNT-TEST-001",              "type": "string"},
            {"key": "ORDER_ID",     "value": "ORD-TEST-001",              "type": "string"},
        ],
        "item": items,
    }
    return json.dumps(collection, indent=2)


def _gen_playwright(feature_title: str, module: str, system: str, tc_json: str) -> str:
    prompt = f"""You are a senior test automation engineer for the Eutelsat CxP BSS/OSS programme.
Generate a complete Playwright test script in JavaScript for UI/browser automation.

Feature: {feature_title}
Module: {module}
System: {system}
Full stack context: {SYSTEM_STACK}

Test cases to implement:
{tc_json}

REQUIREMENTS:
1. Output ONLY valid JavaScript — no markdown fences, no explanation
2. Use @playwright/test: const {{ test, expect }} = require('@playwright/test')
3. Read config from env: BASE_URL (default https://sit.eutelsat.com), TEST_USERNAME, TEST_PASSWORD
4. Wrap all tests in test.describe('{feature_title}', () => {{ ... }})
5. test.beforeAll: navigate to login page, fill credentials, click submit, waitForLoadState('networkidle')
6. One test() per test case — name: '[TC_ID] description (first 65 chars)'
7. Each test: await page.goto(URL), waitForLoadState, step-by-step actions, expect() assertions
8. Use locator('[data-testid="..."]') or getByRole() selectors — prefer semantic
9. Assertions must verify the expected_result of each test case
10. test.afterAll: clean up test data via API if needed (commented stub)
11. Export a playwright.config.js stub as a comment block at the top of the file
12. Add // STEP N: comment for each distinct action (mirrors the test case steps)
"""
    raw = _call(prompt, max_tokens=5120)
    return _clean_code(raw, "javascript")


def _gen_python(feature_title: str, module: str, system: str, tc_json: str) -> str:
    base_path = _MODULE_BASE_PATHS.get(module, "/api/v1")
    prompt = f"""You are a senior test automation engineer for the Eutelsat CxP BSS/OSS programme.
Generate a complete Python pytest test script using the requests library for API testing.

Feature: {feature_title}
Module: {module}
System: {system}
API Base Path: {{BASE_URL}}{base_path}
Full stack context: {SYSTEM_STACK}

Test cases to implement:
{tc_json}

REQUIREMENTS:
1. Output ONLY valid Python — no markdown fences, no explanation
2. Imports: pytest, requests, os, json
3. Module-level constants from environment: BASE_URL, AUTH_TOKEN, DP_ACCOUNT_ID, CONTRACT_ID
4. Session-scoped fixture auth_session() returning requests.Session with Bearer auth headers
5. One test function per test case — name: test_[tc_id_lower]_[3_word_description]
6. Docstring first line: "TC-XXX: full description."
7. Pattern per test:
   a. endpoint = f'{{BASE_URL}}{base_path}/resource/...'
   b. response = auth_session.METHOD(endpoint, json={{...}})
   c. assert response.status_code == NNN, f"Expected NNN, got {{response.status_code}}: {{response.text[:200]}}"
   d. data = response.json() — then assert specific fields from expected_result
8. Include parametrize decorator for data-driven tests where the steps suggest multiple inputs
9. Add a conftest.py comment block at the very top showing what to put in conftest.py
10. Add @pytest.mark.smoke on High priority test cases, @pytest.mark.regression on Regression type
"""
    raw = _call(prompt, max_tokens=5120)
    return _clean_code(raw, "python")


def automation_agent(
    feature_title: str,
    module: str,
    system: str,
    test_cases: list[dict],
    script_type: str,
) -> str:
    """Generate Postman / Playwright / Python automation scripts from test cases."""
    # Prefer automation candidates; fall back to all if none tagged
    auto = [tc for tc in test_cases if tc.get("automation_candidate")]
    pool = auto if auto else test_cases
    # Postman JSON is verbose — cap lower to avoid truncation
    cap = 8 if script_type == "postman" else 12
    pool = pool[:cap]

    tc_list = [
        {
            "tc_id":          tc.get("tc_id", f"TC-{i+1:03d}"),
            "description":    tc.get("description", ""),
            "steps":          tc.get("steps", ""),
            "expected_result":tc.get("expected_result", ""),
            "priority":       tc.get("priority", "Medium"),
            "type":           tc.get("type", "Functional"),
            "automation_notes": tc.get("automation_notes", ""),
        }
        for i, tc in enumerate(pool)
    ]
    tc_json = json.dumps(tc_list, indent=2)

    _p(f"\n[Automation Agent] Generating {script_type} script for '{feature_title}' ({len(tc_list)} cases)...")
    if script_type == "postman":
        return _gen_postman(feature_title, module, system, tc_json)
    elif script_type == "playwright":
        return _gen_playwright(feature_title, module, system, tc_json)
    elif script_type == "python":
        return _gen_python(feature_title, module, system, tc_json)
    else:
        raise ValueError(f"Unknown script_type: {script_type}")


# ── Main Pipeline ─────────────────────────────────────────────────────────────

CASES_PER_AREA = 5
MAX_CASES = 60
MULTI_MODE_AREAS = 5
MULTI_MODE_CASES_PER_AREA = 4


def run_pipeline(
    feature_title: str,
    description: str,
    module: str,
    test_type: str,
    rag_context: str = "",
    release: str = "R1",
    chain_mode: bool = False,
    multi_mode: bool = False,
) -> list[dict]:
    """4-agent pipeline: Scout → Generator → Reviewer → Evaluator.

    multi_mode=True uses fewer areas/cases per type — used when generating all 5 types in parallel.
    """
    num_areas = MULTI_MODE_AREAS if multi_mode else 7
    cases_per = MULTI_MODE_CASES_PER_AREA if multi_mode else CASES_PER_AREA
    max_cases = num_areas * cases_per * 2

    mode_label = "E2E CHAIN" if chain_mode else test_type
    _p(f"\n{'='*60}")
    _p(f"Eutelsat GenAI Pipeline  |  {module}  |  {mode_label}  |  {release}")
    _p(f"Feature: {feature_title}")
    _p(f"Chain mode: {chain_mode} | Multi: {multi_mode} | RAG: {'YES' if rag_context else 'no'}")
    _p(f"{'='*60}")

    _p(f"\n[1/4] Scout Agent - identifying {num_areas} scenario areas...")
    areas = scout_agent(feature_title, module, test_type, rag_context, release, chain_mode, num_areas)
    _p(f"      {len(areas)} areas identified")
    for i, a in enumerate(areas, 1):
        _p(f"        {i}. {a[:70]}")

    _p(f"\n[2/4] Generator Agent - {cases_per} cases per area (parallel)...")
    all_raw: list[dict] = []
    with _TPE(max_workers=min(len(areas), 4)) as gen_ex:
        gen_futures = {
            gen_ex.submit(
                generator_agent, area, feature_title, module, test_type,
                cases_per, rag_context, release, chain_mode
            ): (i, area)
            for i, area in enumerate(areas, 1)
        }
        area_results: dict[int, list] = {}
        for fut in _ac(gen_futures):
            i, area = gen_futures[fut]
            try:
                cases = fut.result()
                area_results[i] = cases
                _p(f"      Area {i}/{len(areas)} done: {len(cases)} cases")
            except Exception as e:
                _p(f"      Area {i}/{len(areas)} failed: {e}")
                area_results[i] = []
    for i in sorted(area_results):
        all_raw.extend(area_results[i])

    if len(all_raw) > max_cases:
        _p(f"      [Cap] {len(all_raw)} -> {max_cases}")
        all_raw = all_raw[:max_cases]
    _p(f"      {len(all_raw)} total cases collected")

    _p("\n[3/4] Reviewer Agent - assigning priorities...")
    final = reviewer_agent(all_raw, test_type)

    _p("\n[4/4] Evaluator Agent - scoring quality metrics...")
    final = evaluator_agent(final, module, test_type)

    auto_count = sum(1 for c in final if c.get("automation_candidate"))
    _p(f"\n{'='*60}")
    _p(f"Pipeline complete: {len(final)} test cases - {auto_count} automation candidates")
    _p(f"{'='*60}\n")

    return final
