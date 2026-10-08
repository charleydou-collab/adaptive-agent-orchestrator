#!/usr/bin/env python3
"""Resolve abstract execution requirements with an explicit premium approval gate."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


COST_ORDER = {"low": 0, "medium": 1, "high": 2}
EXIT_CODES = {"selected": 0, "invalid_input": 2, "approval_required": 3,
              "no_compatible_model": 4}


def is_premium(model):
    return (model.get("cost_class") == "high" or
            model.get("approval_policy") == "explicit-user-approval")


def incompatibilities(model, requirements):
    reasons = []
    if model.get("availability") != "available":
        reasons.append("availability")
    if requirements["capability_tier"] not in model.get("capability_tiers", []):
        reasons.append("capability_tier")
    if model.get("context_window", 0) < requirements["minimum_context"]:
        reasons.append("context")
    if not set(requirements["modalities"]).issubset(model.get("modalities", [])):
        reasons.append("modalities")
    if not set(requirements["required_tools"]).issubset(model.get("tools", [])):
        reasons.append("tools")
    effort = model.get("reasoning_mapping", {}).get(requirements["minimum_reasoning_class"])
    if effort is None or effort not in model.get("supported_efforts", []):
        reasons.append("reasoning")
    return reasons


def rank(model):
    return (COST_ORDER.get(model.get("cost_class"), 99),
            model.get("context_window", 0), model.get("provider", ""),
            model.get("model_id", ""), model.get("version", ""))


def resolved(model, requirements, adapter, worker_mode, approval_reference=None, now=None):
    timestamp = now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "status": "selected",
        "premium_used": is_premium(model),
        "resolved_execution": {
            "provider": model["provider"],
            "model_id": model["model_id"],
            "effort": model["reasoning_mapping"][requirements["minimum_reasoning_class"]],
            "worker_mode": worker_mode,
            "adapter": adapter,
            "resolution_timestamp": timestamp,
        },
    }
    if approval_reference is not None:
        result["approval_reference"] = approval_reference
    return result


def resolve(registry, requirements, *, adapter, worker_mode="native-parallel",
            approval=None, now=None):
    models = registry.get("models")
    if not isinstance(models, list):
        raise ValueError("Registry must contain a models array")

    rejection_summary = {name: 0 for name in
                         ("availability", "capability_tier", "context", "modalities", "tools", "reasoning")}
    compatible = []
    for model in models:
        reasons = incompatibilities(model, requirements)
        for reason in reasons:
            rejection_summary[reason] += 1
        if not reasons:
            compatible.append(model)

    compatible.sort(key=rank)
    ordinary = [model for model in compatible if not is_premium(model)]
    if ordinary:
        return resolved(ordinary[0], requirements, adapter, worker_mode, now=now)

    premium = [model for model in compatible if is_premium(model)]
    if not premium:
        return {
            "status": "no_compatible_model",
            "compatible_count": 0,
            "rejection_summary": rejection_summary,
        }

    if approval:
        approved = next((model for model in premium
                         if model["model_id"] == approval.get("model_id")), None)
        reference = approval.get("reference")
        if approved is not None and isinstance(reference, str) and reference.strip():
            return resolved(approved, requirements, adapter, worker_mode,
                            approval_reference=reference, now=now)

    recommendation = premium[0]
    effort = recommendation["reasoning_mapping"][requirements["minimum_reasoning_class"]]
    explanation = (
        "Why it is recommended: no available low- or medium-cost model without a premium "
        "approval requirement satisfies all mandatory capability, context, modality, tool, "
        "and reasoning requirements."
    )
    prompt = (
        f"The task requires the higher-cost model {recommendation['model_id']} "
        f"with effort {effort}. {explanation} Do you approve using this exact model for this task?"
    )
    return {
        "status": "approval_required",
        "compatible_count": len(compatible),
        "recommended_model": {
            "provider": recommendation["provider"],
            "model_id": recommendation["model_id"],
            "version": recommendation["version"],
            "cost_class": recommendation["cost_class"],
            "effort": effort,
        },
        "reason": explanation,
        "user_prompt": prompt,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--worker-mode", default="native-parallel",
                        choices=("native-parallel", "native-sequential", "role-simulation", "direct"))
    parser.add_argument("--approved-model-id")
    parser.add_argument("--approval-ref")
    try:
        args = parser.parse_args(argv)
        if bool(args.approved_model_id) != bool(args.approval_ref):
            raise ValueError("Approved model and approval reference must be supplied together")
        approval = None
        if args.approved_model_id:
            approval = {"model_id": args.approved_model_id, "reference": args.approval_ref}
        result = resolve(
            json.loads(args.registry.read_text(encoding="utf-8")),
            json.loads(args.requirements.read_text(encoding="utf-8")),
            adapter=args.adapter,
            worker_mode=args.worker_mode,
            approval=approval,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"status": "invalid_input", "error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return EXIT_CODES[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
