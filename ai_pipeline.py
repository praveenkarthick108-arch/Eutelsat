import os
import json
import re
import warnings
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
_http_client = httpx.Client(verify=False)

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
    http_client=_http_client,
)

MODEL = "openai/gpt-oss-20b"


def _call(prompt: str, max_tokens: int = 4096) -> str:
    completion = client.chat.completions.create(
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

def scout_agent(feature_title: str, module: str, test_type: str) -> list[str]:
    """Identify 7 distinct test scenario areas for thorough coverage."""
    prompt = f"""You are a senior QA architect for the Eutelsat satellite telecommunications BSS/OSS project (Release 1).
Systems involved: GEO Community Cloud portal, GCRM Salesforce (contracts), Zuora (CPQ/billing), GEO Salesforce (orders), O-BRM (billing), SAP (invoicing).

Analyze this feature and identify exactly 7 distinct test scenario areas for thorough {test_type} coverage.

Module: {module}
Feature: {feature_title}
Test Type: {test_type}

Each area must be specific and actionable — covering happy paths, edge cases, negative scenarios, and integration points.
Return ONLY a JSON array of exactly 7 strings, no markdown, no explanation:
["scenario area 1", "scenario area 2", ..., "scenario area 7"]"""

    try:
        response = _call(prompt)
        areas = _extract_json(response)
        if isinstance(areas, list) and len(areas) > 0:
            return [str(a) for a in areas[:8]]
    except Exception as e:
        print(f"[Scout Agent] Error: {e}")

    return [
        f"Core {feature_title} happy path",
        "Input validation and boundary conditions",
        "Error handling and negative scenarios",
        "Integration with downstream BSS/OSS systems",
        "Data integrity and persistence verification",
        "Concurrent operations and race conditions",
        "Performance and SLA compliance",
    ]


# ── Agent 2: Generator ────────────────────────────────────────────────────────

def generator_agent(
    area: str,
    feature_title: str,
    module: str,
    test_type: str,
    count: int = 5,
) -> list[dict]:
    """Generate test cases for a specific scenario area."""
    prompt = f"""You are a senior QA engineer for the Eutelsat Release 1 BSS/OSS project.
Systems: GEO Community Cloud portal, GCRM Salesforce (contracts), Zuora (CPQ/billing), GEO Salesforce (orders), O-BRM (billing), SAP (invoicing).

Generate exactly {count} {test_type} test cases for this specific scenario area:

Feature: {feature_title}
Module: {module}
Scenario Area: {area}

Return ONLY a JSON array — no markdown:
[
  {{
    "description": "Verify that ...",
    "steps": "1. Step one\\n2. Step two\\n3. Step three\\n4. Step four",
    "expected_result": "System should ..."
  }}
]

Rules:
- Each description MUST start with "Verify that"
- Steps should be numbered, specific and actionable (4-6 steps)
- Expected result must be specific and verifiable
- Reference actual systems (Zuora, GCRM, GEO portal, etc.) where relevant"""

    try:
        response = _call(prompt)
        cases = _extract_json(response)
        if isinstance(cases, list):
            return cases
    except Exception as e:
        print(f"[Generator Agent] Area '{area[:50]}' error: {e}")

    return [
        {
            "description": f"Verify that {area.lower()}",
            "steps": "1. Navigate to the feature\n2. Execute the action\n3. Observe the result\n4. Verify state",
            "expected_result": "System behaves as expected per requirements",
        }
    ]


# ── Agent 3: Reviewer ─────────────────────────────────────────────────────────

def _assign_priorities_batch(batch: list[dict], test_type: str) -> list[dict]:
    cases_json = json.dumps(batch, indent=2)
    n = len(batch)
    prompt = f"""You are a senior QA lead for the Eutelsat Release 1 project.

Assign a priority (High / Medium / Low) to each of these {n} {test_type} test cases.
Do NOT remove or reorder any — return all {n} items.
Priority distribution: ~30% High (critical path, revenue impact), ~50% Medium (important but not blocking), ~20% Low (edge cases).

Return ONLY a JSON array of exactly {n} objects — no markdown:
[
  {{
    "description": "...",
    "steps": "...",
    "expected_result": "...",
    "priority": "High"
  }}
]

Test cases:
{cases_json}"""

    try:
        response = _call(prompt)
        reviewed = _extract_json(response)
        if isinstance(reviewed, list) and len(reviewed) == n:
            return reviewed
        if isinstance(reviewed, list) and len(reviewed) > 0:
            for i, orig in enumerate(batch):
                if i < len(reviewed):
                    orig["priority"] = reviewed[i].get("priority", "Medium")
            return batch
    except Exception as e:
        print(f"[Reviewer Batch] Error: {e}")

    priorities = ["High", "High", "Medium", "Medium", "Medium", "Low"]
    for i, case in enumerate(batch):
        case.setdefault("priority", priorities[i % len(priorities)])
    return batch


def reviewer_agent(all_cases: list[dict], test_type: str) -> list[dict]:
    """Assign priorities to ALL cases; batch if count > 25."""
    BATCH_SIZE = 25
    total = len(all_cases)
    if total == 0:
        return all_cases
    if total <= BATCH_SIZE:
        print(f"      Reviewing {total} cases...")
        return _assign_priorities_batch(all_cases, test_type)
    print(f"      Large set ({total} cases) - batching...")
    result = []
    for start in range(0, total, BATCH_SIZE):
        batch = all_cases[start : start + BATCH_SIZE]
        print(f"        Batch {start // BATCH_SIZE + 1}: cases {start+1}-{start+len(batch)}")
        result.extend(_assign_priorities_batch(batch, test_type))
    return result


# ── Agent 4: Evaluator ────────────────────────────────────────────────────────

def _evaluate_batch(batch: list[dict], module: str, test_type: str) -> list[dict]:
    n = len(batch)
    cases_json = json.dumps(
        [{"description": c.get("description", ""), "steps": c.get("steps", "")[:200]} for c in batch],
        indent=2
    )
    prompt = f"""You are a QA quality assessor for the Eutelsat Release 1 BSS/OSS project.
Module: {module} | Test Type: {test_type}

Evaluate each test case and assign:
1. confidence_score (0.0-1.0):
   0.9-1.0 = clear, standard, highly testable
   0.7-0.8 = reasonable, minor clarification needed
   0.5-0.6 = plausible but uncertain about specifics
   <0.5    = speculative, needs requirements clarification

2. hallucination_risk ("Low" / "Medium" / "High"):
   Low    = generic pattern verifiable in any telecom BSS/OSS
   Medium = references specific features needing confirmation
   High   = very specific claims hard to verify without system access

Return ONLY a JSON array of exactly {n} objects — no markdown:
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
        print(f"[Evaluator Batch] Error: {e}")

    for case in batch:
        case.setdefault("confidence_score", 0.82)
        case.setdefault("hallucination_risk", "Low")
    return batch


def evaluator_agent(all_cases: list[dict], module: str, test_type: str) -> list[dict]:
    """Assign confidence scores and hallucination risk to all cases."""
    BATCH_SIZE = 20
    total = len(all_cases)
    if total == 0:
        return all_cases
    if total <= BATCH_SIZE:
        print(f"      Evaluating {total} cases for quality metrics...")
        return _evaluate_batch(all_cases, module, test_type)
    print(f"      Evaluating {total} cases in batches...")
    result = []
    for start in range(0, total, BATCH_SIZE):
        batch = all_cases[start : start + BATCH_SIZE]
        result.extend(_evaluate_batch(batch, module, test_type))
    return result


# ── Follow-up Agent ───────────────────────────────────────────────────────────

def followup_agent(
    query: str,
    feature_title: str,
    module: str,
    test_type: str,
    existing_cases: list[dict],
) -> dict:
    """Answer a follow-up question or generate additional test cases."""
    summary = [
        {"tc_id": c.get("tc_id", f"TC-{i+1:03d}"), "description": c.get("description", "")}
        for i, c in enumerate(existing_cases[:15])
    ]
    prompt = f"""You are a QA assistant for the Eutelsat Release 1 BSS/OSS project.

Feature: {feature_title} | Module: {module} | Type: {test_type}

Existing {len(existing_cases)} test cases (summary):
{json.dumps(summary, indent=2)}

User follow-up: "{query}"

Decide: does the user want MORE test cases, or are they asking a question/requesting clarification?

If they want MORE test cases, generate 3-5 new ones without duplicating existing ones.
If they are asking a question, answer concisely and helpfully.

Return JSON exactly:
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
      "hallucination_risk": "Low"
    }}
  ]
}}

OR

{{
  "type": "answer",
  "message": "Your detailed answer here...",
  "new_cases": []
}}"""

    try:
        response = _call(prompt, max_tokens=3000)
        result = _extract_json(response)
        if isinstance(result, dict) and "type" in result:
            return result
    except Exception as e:
        print(f"[Followup Agent] Error: {e}")

    return {
        "type": "answer",
        "message": "I had trouble processing that request. Please try rephrasing your question.",
        "new_cases": [],
    }


# ── Main Pipeline ─────────────────────────────────────────────────────────────

CASES_PER_AREA = 5   # 7 areas x 5 = ~35 test cases
MAX_CASES = 60       # safety cap


def run_pipeline(
    feature_title: str,
    description: str,
    module: str,
    test_type: str,
) -> list[dict]:
    """4-agent pipeline: Scout -> Generator -> Reviewer -> Evaluator."""

    print(f"\n{'='*60}")
    print(f"Eutelsat GenAI Pipeline  |  {module}  |  {test_type}")
    print(f"Feature: {feature_title}")
    print(f"{'='*60}")

    # Agent 1: Scout
    print("\n[1/4] Scout Agent - identifying 7 test areas...")
    areas = scout_agent(feature_title, module, test_type)
    print(f"      {len(areas)} areas identified")
    for i, a in enumerate(areas, 1):
        print(f"        {i}. {a[:70]}")

    # Agent 2: Generator
    print(f"\n[2/4] Generator Agent - {CASES_PER_AREA} cases per area...")
    all_raw: list[dict] = []
    for i, area in enumerate(areas, 1):
        print(f"      Area {i}/{len(areas)}: {area[:60]}...")
        cases = generator_agent(area, feature_title, module, test_type, CASES_PER_AREA)
        all_raw.extend(cases)
        print(f"             -> {len(cases)} cases")

    if len(all_raw) > MAX_CASES:
        print(f"      [Cap] {len(all_raw)} -> {MAX_CASES}")
        all_raw = all_raw[:MAX_CASES]
    print(f"      {len(all_raw)} total cases collected")

    # Agent 3: Reviewer
    print(f"\n[3/4] Reviewer Agent - assigning priorities...")
    final = reviewer_agent(all_raw, test_type)

    # Agent 4: Evaluator
    print(f"\n[4/4] Evaluator Agent - scoring quality metrics...")
    final = evaluator_agent(final, module, test_type)

    print(f"\n{'='*60}")
    print(f"Pipeline complete: {len(final)} test cases ready")
    print(f"{'='*60}\n")

    return final
