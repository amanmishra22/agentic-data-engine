"""
Autonomous Enterprise Compliance & Lead Intelligence Agent
Built with LangGraph to consume structured JSON compliance feeds,
detect vulnerability anomalies, and generate automated remediation plans.
"""

from typing import Any, Dict, List
import json
from agents.state import PipelineState

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph = None
    END = "__end__"


# ---------------------------------------------------------------------------
# Node 1: Ingestion & Schema Validation
# ---------------------------------------------------------------------------
def ingest_and_validate(state: PipelineState) -> Dict[str, Any]:
    """Validates raw incoming JSON feed records against compliance constraints."""
    raw = state.get("raw_feed", [])
    valid = []
    anomalies = []

    for item in raw:
        if not item.get("url"):
            continue
        
        # Check integrity
        score = item.get("complianceScore", 0)
        if score < 0 or score > 100:
            anomalies.append({"url": item.get("url"), "reason": "Score out of bounds"})
            continue

        valid.append(item)

    return {
        "validated_records": valid,
        "anomalies": anomalies,
    }


# ---------------------------------------------------------------------------
# Node 2: Risk Scoring & Target Prioritization
# ---------------------------------------------------------------------------
def prioritize_vulnerabilities(state: PipelineState) -> Dict[str, Any]:
    """Identifies critical compliance failures (missing HSTS, failing WCAG, no privacy policy)."""
    valid = state.get("validated_records", [])
    prioritized = []

    for record in valid:
        score = record.get("complianceScore", 100)
        a11y_score = record.get("accessibilityScore", 100)
        sec_score = record.get("securityScore", 100)

        risk_level = "LOW"
        remediation_urgency = "STANDARD"

        if score < 50 or sec_score < 40:
            risk_level = "CRITICAL"
            remediation_urgency = "IMMEDIATE"
        elif score < 75 or a11y_score < 60:
            risk_level = "HIGH"
            remediation_urgency = "SCHEDULED"

        if risk_level in ("CRITICAL", "HIGH"):
            prioritized.append({
                "url": record.get("url"),
                "risk_level": risk_level,
                "urgency": remediation_urgency,
                "complianceScore": score,
                "missingSecurity": [
                    k for k in ["hasHSTS", "hasCSP", "hasXFrameOptions"]
                    if not record.get(k, True)
                ],
                "accessibilityDeficits": {
                    "missingAlt": record.get("imagesMissingAlt", 0),
                    "totalImages": record.get("imagesTotal", 0),
                },
                "contacts": record.get("emails", []),
            })

    # Sort descending by risk (lowest score first)
    prioritized.sort(key=lambda x: x["complianceScore"])
    return {"prioritized_targets": prioritized}


# ---------------------------------------------------------------------------
# Node 3: Executive Summary & Remediation Dispatch
# ---------------------------------------------------------------------------
def generate_remediation_payloads(state: PipelineState) -> Dict[str, Any]:
    """Generates structured remediation action plans ready for CRM/Email dispatch."""
    targets = state.get("prioritized_targets", [])
    payloads = []

    for target in targets:
        actions = []
        if "hasHSTS" in target.get("missingSecurity", []):
            actions.append("Configure Strict-Transport-Security header (max-age=31536000; includeSubDomains).")
        if "hasCSP" in target.get("missingSecurity", []):
            actions.append("Define Content-Security-Policy to mitigate Cross-Site Scripting (XSS).")
        
        missing_alt = target.get("accessibilityDeficits", {}).get("missingAlt", 0)
        if missing_alt > 0:
            actions.append(f"Add descriptive alt attributes to {missing_alt} unlabelled visual assets.")

        payloads.append({
            "targetUrl": target["url"],
            "riskLevel": target["risk_level"],
            "urgency": target["urgency"],
            "contactRecipients": target["contacts"],
            "recommendedRemediation": actions,
        })

    summary = (
        f"Pipeline processed {len(state.get('validated_records', []))} records. "
        f"Identified {len(targets)} high-risk non-compliant entities requiring automated remediation."
    )

    return {
        "dispatch_payloads": payloads,
        "executive_summary": summary,
    }


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------
def build_compliance_agent():
    """Builds and compiles the deterministic LangGraph workflow."""
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed. Install via `pip install langgraph`.")

    graph = StateGraph(PipelineState)

    graph.add_node("validate", ingest_and_validate)
    graph.add_node("prioritize", prioritize_vulnerabilities)
    graph.add_node("dispatch", generate_remediation_payloads)

    graph.set_entry_point("validate")
    graph.add_edge("validate", "prioritize")
    graph.add_edge("prioritize", "dispatch")
    graph.add_edge("dispatch", END)

    return graph.compile()


if __name__ == "__main__":
    # Sample execution harness with dummy verified feed
    sample_feed = [
        {
            "url": "https://secure-enterprise.com",
            "complianceScore": 95,
            "accessibilityScore": 92,
            "securityScore": 100,
            "privacyScore": 90,
            "hasHSTS": True,
            "hasCSP": True,
            "hasXFrameOptions": True,
            "imagesTotal": 10,
            "imagesMissingAlt": 0,
            "emails": ["security@secure-enterprise.com"],
        },
        {
            "url": "https://vulnerable-portal.org",
            "complianceScore": 42,
            "accessibilityScore": 48,
            "securityScore": 25,
            "privacyScore": 40,
            "hasHSTS": False,
            "hasCSP": False,
            "hasXFrameOptions": False,
            "imagesTotal": 24,
            "imagesMissingAlt": 18,
            "emails": ["contact@vulnerable-portal.org"],
        },
    ]

    print("[*] Running Autonomous Pipeline Validation...")
    state: PipelineState = {
        "raw_feed": sample_feed,
        "validated_records": [],
        "anomalies": [],
        "prioritized_targets": [],
        "executive_summary": None,
        "dispatch_payloads": [],
    }

    # Step-by-step state transition
    s1 = ingest_and_validate(state)
    state.update(s1)
    s2 = prioritize_vulnerabilities(state)
    state.update(s2)
    s3 = generate_remediation_payloads(state)
    state.update(s3)

    print("\n--- EXECUTIVE SUMMARY ---")
    print(state["executive_summary"])
    print("\n--- REMEDIATION PAYLOAD SAMPLE ---")
    print(json.dumps(state["dispatch_payloads"], indent=2))
