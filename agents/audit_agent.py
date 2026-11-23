"""
Autonomous Multi-Domain Compliance, Financial & Regulatory Triage Engine
Built with LangGraph to ingest Draft 2020-12 JSON feeds across five domains:
  1. B2B Web Accessibility, Security & Privacy Compliance
  2. Multi-Page Financial PDF Table & Balance Reconciliation
  3. Multi-State Contractor KYB, Bond & Insurance Underwriting
  4. Public Procurement Tender & Deadline Urgency Triage
  5. Real Estate Regulatory Registration & Completion Diligence
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
# Domain Detection Helper
# ---------------------------------------------------------------------------
def detect_record_domain(item: Dict[str, Any]) -> str:
    """Deterministically route an incoming JSON record to one of the 5 schema domains."""
    if "reconciliationStatus" in item and "documentUrl" in item:
        return "financial_reconciliation"
    if "licenseNumber" in item and "underwritingDecision" in item:
        return "contractor_license"
    if "tenderId" in item and "sourcePortal" in item:
        return "procurement_tender"
    if "registrationNumber" in item and "riskTier" in item:
        return "real_estate_rera"
    if "url" in item and "complianceScore" in item:
        return "b2b_compliance"
    return "unknown"


# ---------------------------------------------------------------------------
# Node 1: Multi-Domain Schema Validation & Anomaly Quarantine
# ---------------------------------------------------------------------------
def ingest_and_validate(state: PipelineState) -> Dict[str, Any]:
    """Validates raw incoming JSON stream records against domain-specific invariants."""
    raw = state.get("raw_feed", [])
    valid: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    for item in raw:
        domain = detect_record_domain(item)
        if domain == "unknown":
            anomalies.append({"record": item, "reason": "Unrecognized schema contract"})
            continue

        if domain == "b2b_compliance":
            score = item.get("complianceScore", -1)
            if not item.get("url") or not (0 <= score <= 100):
                anomalies.append({"id": item.get("url"), "domain": domain, "reason": "Invalid complianceScore bounds"})
                continue

        elif domain == "financial_reconciliation":
            conf = item.get("confidenceScore", -1)
            if not item.get("documentUrl") or not (0 <= conf <= 100):
                anomalies.append({"id": item.get("documentUrl"), "domain": domain, "reason": "Invalid confidenceScore"})
                continue

        elif domain == "contractor_license":
            t_score = item.get("trustScore", -1)
            if not item.get("licenseNumber") or not (0 <= t_score <= 100):
                anomalies.append({"id": item.get("licenseNumber"), "domain": domain, "reason": "Invalid trustScore"})
                continue

        elif domain == "procurement_tender":
            if not item.get("tenderId") or not item.get("title"):
                anomalies.append({"id": item.get("tenderId"), "domain": domain, "reason": "Missing tender identifier"})
                continue

        elif domain == "real_estate_rera":
            c_score = item.get("complianceScore", -1)
            if not item.get("registrationNumber") or not (0 <= c_score <= 100):
                anomalies.append({"id": item.get("registrationNumber"), "domain": domain, "reason": "Invalid RERA score"})
                continue

        enriched = dict(item)
        enriched["_domain"] = domain
        valid.append(enriched)
        counts[domain] = counts.get(domain, 0) + 1

    return {
        "validated_records": valid,
        "anomalies": anomalies,
        "domain_counts": counts,
    }


# ---------------------------------------------------------------------------
# Node 2: Cross-Domain Risk, Discrepancy & Opportunity Scoring
# ---------------------------------------------------------------------------
def prioritize_vulnerabilities(state: PipelineState) -> Dict[str, Any]:
    """Flags high-priority compliance gaps, ledger discrepancies, underwriting blocks, and closing tenders."""
    valid = state.get("validated_records", [])
    prioritized: List[Dict[str, Any]] = []

    for record in valid:
        domain = record["_domain"]

        if domain == "b2b_compliance":
            score = record.get("complianceScore", 100)
            sec_score = record.get("securityScore", 100)
            a11y_score = record.get("accessibilityScore", 100)
            if score < 75 or sec_score < 40 or a11y_score < 60:
                prioritized.append({
                    "domain": domain,
                    "entityId": record["url"],
                    "severity": "CRITICAL" if (score < 50 or sec_score < 40) else "HIGH",
                    "urgency": "IMMEDIATE" if score < 50 else "SCHEDULED",
                    "priorityRank": score,
                    "details": {
                        "missingSecurity": [
                            k for k in ("hasHSTS", "hasCSP", "hasXFrameOptions")
                            if not record.get(k, True)
                        ],
                        "imagesMissingAlt": record.get("imagesMissingAlt", 0),
                        "contacts": record.get("emails", []),
                    },
                })

        elif domain == "financial_reconciliation":
            status = record.get("reconciliationStatus", "")
            delta = abs(float(record.get("discrepancyDelta") or 0.0))
            if status in ("DISCREPANCY_DETECTED", "DISCREPANCY_FOUND") or delta > 0.01:
                prioritized.append({
                    "domain": domain,
                    "entityId": f"{record['documentUrl']}#page={record.get('pageNumber', 1)}",
                    "severity": "CRITICAL",
                    "urgency": "IMMEDIATE",
                    "priorityRank": 5,
                    "details": {
                        "declaredTotal": record.get("declaredTotal"),
                        "calculatedTotal": record.get("calculatedTotal"),
                        "discrepancyDelta": record.get("discrepancyDelta"),
                        "currency": record.get("currency", "USD"),
                    },
                })

        elif domain == "contractor_license":
            decision = record.get("underwritingDecision", "REVIEW")
            if decision in ("REJECT", "REVIEW"):
                prioritized.append({
                    "domain": domain,
                    "entityId": f"{record.get('state')}-{record['licenseNumber']}",
                    "severity": "CRITICAL" if decision == "REJECT" else "HIGH",
                    "urgency": "IMMEDIATE" if decision == "REJECT" else "SCHEDULED",
                    "priorityRank": record.get("trustScore", 50),
                    "details": {
                        "businessName": record.get("businessName"),
                        "decision": decision,
                        "complianceFlags": record.get("complianceFlags", []),
                    },
                })

        elif domain == "procurement_tender":
            urgency = record.get("urgencyLevel", "OPEN")
            if urgency in ("CLOSING_24H", "CLOSING_7D") or record.get("isHighValue"):
                prioritized.append({
                    "domain": domain,
                    "entityId": record["tenderId"],
                    "severity": "HIGH",
                    "urgency": "IMMEDIATE" if urgency == "CLOSING_24H" else "SCHEDULED",
                    "priorityRank": int(float(record.get("daysRemaining") or 7) * 5),
                    "details": {
                        "title": record.get("title"),
                        "sectorDomain": record.get("sectorDomain"),
                        "daysRemaining": record.get("daysRemaining"),
                        "documentUrl": record.get("documentUrl"),
                    },
                })

        elif domain == "real_estate_rera":
            tier = record.get("riskTier", "LOW_RISK")
            if tier in ("HIGH_RISK", "MODERATE_RISK") or record.get("hasExtension"):
                prioritized.append({
                    "domain": domain,
                    "entityId": f"{record.get('state')}:{record['registrationNumber']}",
                    "severity": "CRITICAL" if tier == "HIGH_RISK" else "HIGH",
                    "urgency": "IMMEDIATE" if tier == "HIGH_RISK" else "SCHEDULED",
                    "priorityRank": record.get("complianceScore", 50),
                    "details": {
                        "projectName": record.get("projectName"),
                        "promoterName": record.get("promoterName"),
                        "riskFlags": record.get("riskFlags", []),
                    },
                })

    prioritized.sort(key=lambda x: x["priorityRank"])
    return {"prioritized_targets": prioritized}


# ---------------------------------------------------------------------------
# Node 3: Deterministic Action & Remediation Payload Generator
# ---------------------------------------------------------------------------
def generate_remediation_payloads(state: PipelineState) -> Dict[str, Any]:
    """Generates structured downstream ERP, CRM, Bid-Desk, and Compliance payloads."""
    targets = state.get("prioritized_targets", [])
    payloads: List[Dict[str, Any]] = []

    for target in targets:
        domain = target["domain"]
        det = target["details"]
        actions: List[str] = []
        channel = "ENTERPRISE_AUDIT_BUS"

        if domain == "b2b_compliance":
            channel = "SECOPS_AND_WCAG_QUEUE"
            if "hasHSTS" in det.get("missingSecurity", []):
                actions.append("Configure Strict-Transport-Security header (max-age=31536000; includeSubDomains).")
            if "hasCSP" in det.get("missingSecurity", []):
                actions.append("Define Content-Security-Policy to mitigate Cross-Site Scripting (XSS).")
            if det.get("imagesMissingAlt", 0) > 0:
                actions.append(f"Add descriptive alt attributes to {det['imagesMissingAlt']} unlabelled visual assets.")

        elif domain == "financial_reconciliation":
            channel = "AP_LEDGER_HOLD_QUEUE"
            actions.append(
                f"Hold invoice payout: declared total ({det['declaredTotal']} {det['currency']}) "
                f"differs from line-item sum ({det['calculatedTotal']} {det['currency']}) by {det['discrepancyDelta']}."
            )

        elif domain == "contractor_license":
            channel = "VENDOR_KYB_UNDERWRITING"
            actions.append(
                f"Vendor '{det.get('businessName')}' triaged as {det.get('decision')}; "
                f"review flags: {', '.join(det.get('complianceFlags', []))}."
            )

        elif domain == "procurement_tender":
            channel = "B2G_BID_DESK_DISPATCH"
            actions.append(
                f"Route [{det.get('sectorDomain')}] bid '{det.get('title')}' "
                f"({det.get('daysRemaining')} days remaining) for BOQ estimation: {det.get('documentUrl')}"
            )

        elif domain == "real_estate_rera":
            channel = "LEGAL_COLLATERAL_DILIGENCE"
            actions.append(
                f"Escalate project '{det.get('projectName')}' ({det.get('promoterName')}) "
                f"to legal review due to: {', '.join(det.get('riskFlags', []))}."
            )

        payloads.append({
            "domain": domain,
            "entityId": target["entityId"],
            "dispatchChannel": channel,
            "riskLevel": target["severity"],
            "urgency": target["urgency"],
            "recommendedActions": actions,
        })

    summary = (
        f"Validated {len(state.get('validated_records', []))} multi-domain records across "
        f"{len(state.get('domain_counts', {}))} schema verticals "
        f"(quarantined {len(state.get('anomalies', []))} anomalies). "
        f"Dispatched {len(payloads)} prioritized action payloads."
    )

    return {
        "dispatch_payloads": payloads,
        "executive_summary": summary,
    }


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------
def build_compliance_agent():
    """Builds and compiles the deterministic multi-domain LangGraph workflow."""
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
    sample_feed: List[Dict[str, Any]] = [
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
        {
            "documentUrl": "https://docs.enterprise.example/invoices/inv-2026-884.pdf",
            "pageNumber": 1,
            "tableIndex": 0,
            "reconciliationStatus": "DISCREPANCY_DETECTED",
            "declaredTotal": 14850.00,
            "calculatedTotal": 14350.00,
            "discrepancyDelta": 500.00,
            "currency": "USD",
            "confidenceScore": 98,
        },
        {
            "state": "OR",
            "licenseNumber": "198412",
            "businessName": "APEX STRUCTURAL CONTRACTING LLC",
            "licenseStatus": "EXPIRED",
            "isActive": False,
            "trustScore": 25,
            "underwritingDecision": "REJECT",
            "complianceFlags": ["STATUS_EXPIRED", "LICENSE_EXPIRED"],
        },
        {
            "tenderId": "PROC/2026/SOLAR/74819",
            "sourcePortal": "Central Public Procurement Feed",
            "recordType": "ACTIVE_TENDER",
            "title": "Grid-Connected Rooftop Solar PV Plant (500 kW)",
            "sectorDomain": "Solar & Energy",
            "daysRemaining": 3.4,
            "urgencyLevel": "CLOSING_7D",
            "isHighValue": True,
            "documentUrl": "https://procurement.example.gov/docs/74819.pdf",
            "portalUrl": "https://procurement.example.gov/tenders",
        },
        {
            "registrationNumber": "P52100099123",
            "state": "MH",
            "authority": "State Real Estate Regulatory Authority",
            "projectName": "HORIZON TOWERS PHASE III",
            "promoterName": "HORIZON BUILDCON LLP",
            "hasExtension": True,
            "complianceScore": 65,
            "riskTier": "MODERATE_RISK",
            "riskFlags": ["OFFICIAL_RERA_REGISTERED", "EXTENSION_GRANTED_DELAY_HISTORY"],
        },
    ]

    print("[*] Executing Multi-Domain LangGraph Triage Pipeline...")
    state: PipelineState = {
        "raw_feed": sample_feed,
        "validated_records": [],
        "anomalies": [],
        "prioritized_targets": [],
        "domain_counts": {},
        "executive_summary": None,
        "dispatch_payloads": [],
    }

    for step_fn in (ingest_and_validate, prioritize_vulnerabilities, generate_remediation_payloads):
        state.update(step_fn(state))

    print("\n--- EXECUTIVE SUMMARY ---")
    print(state["executive_summary"])
    print("\n--- ACTION DISPATCH PAYLOADS ---")
    print(json.dumps(state["dispatch_payloads"], indent=2))
