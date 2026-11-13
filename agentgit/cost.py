"""Production Token Budget & Scaling Simulator (agentgit cost-predict).

Simulates production API costs and model trade-offs based on empirical
token distributions captured in a snapshot.

Usage::

    from agentgit.cost import predict_production_cost
    from agentgit.storage import AgentGitStore

    store = AgentGitStore(".")
    forecast = predict_production_cost(store, "v1.0", dau=10000, requests_per_user=5)
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from agentgit.storage import AgentGitStore
from agentgit.tracker import _MODEL_COST_PER_1K


class ModelCostEstimate(BaseModel):
    """Estimated cost on a specific model."""

    model_name: str
    monthly_cost_usd: float
    cost_per_1k_requests: float
    savings_vs_current: float
    savings_pct: float


class CostForecast(BaseModel):
    """Complete production cost scaling forecast."""

    version: str
    model: str
    daily_active_users: int
    requests_per_user: int
    monthly_requests: int
    avg_input_tokens: int
    avg_output_tokens: int
    current_monthly_cost: float
    alternative_models: List[ModelCostEstimate] = Field(default_factory=list)
    recommendation: str = ""


def predict_production_cost(
    store: AgentGitStore,
    version: str,
    dau: int = 1000,
    requests_per_user: int = 5,
    days_per_month: int = 30,
) -> CostForecast:
    """Forecast production API expenses based on snapshot *version*."""
    snap = store.load(version)

    monthly_requests = dau * requests_per_user * days_per_month

    # Average tokens from task results
    if snap.task_results:
        avg_tokens = snap.metrics.avg_tokens_per_task
        # Default split: ~70% input, ~30% output
        avg_inp = int(avg_tokens * 0.70)
        avg_out = int(avg_tokens * 0.30)
    else:
        avg_inp = 800
        avg_out = 250

    current_model = "gpt-4o"
    if snap.metrics.models_used:
        current_model = max(snap.metrics.models_used, key=lambda k: snap.metrics.models_used[k])

    # Compute cost for current model
    def _calc_monthly(model_key: str) -> float:
        for k, (inp_rate, out_rate) in _MODEL_COST_PER_1K.items():
            if k in model_key.lower():
                cost_per_req = (avg_inp / 1000 * inp_rate) + (avg_out / 1000 * out_rate)
                return cost_per_req * monthly_requests
        return (avg_inp + avg_out) / 1000 * 0.005 * monthly_requests

    current_monthly = _calc_monthly(current_model)

    alternatives: List[ModelCostEstimate] = []
    compare_keys = [
        "gpt-4o",
        "gpt-4o-mini",
        "claude-3-5-sonnet",
        "claude-3-5-haiku",
        "gemini-2.5-flash",
    ]

    for ck in compare_keys:
        cost = _calc_monthly(ck)
        savings = current_monthly - cost
        savings_pct = (savings / current_monthly * 100) if current_monthly > 0 else 0.0
        cost_per_1k = (cost / monthly_requests * 1000) if monthly_requests > 0 else 0.0

        alternatives.append(ModelCostEstimate(
            model_name=ck,
            monthly_cost_usd=round(cost, 2),
            cost_per_1k_requests=round(cost_per_1k, 3),
            savings_vs_current=round(savings, 2),
            savings_pct=round(savings_pct, 1),
        ))

    # Sort cheapest first
    alternatives.sort(key=lambda x: x.monthly_cost_usd)
    cheapest = alternatives[0]

    rec = (
        f"💡 Budget Optimization: Switching to '{cheapest.model_name}' would save "
        f"${cheapest.savings_vs_current:,.2f}/month ({cheapest.savings_pct:.0f}% reduction) "
        f"at your scale of {monthly_requests:,} requests/month."
    )

    return CostForecast(
        version=version,
        model=current_model,
        daily_active_users=dau,
        requests_per_user=requests_per_user,
        monthly_requests=monthly_requests,
        avg_input_tokens=avg_inp,
        avg_output_tokens=avg_out,
        current_monthly_cost=round(current_monthly, 2),
        alternative_models=alternatives,
        recommendation=rec,
    )
