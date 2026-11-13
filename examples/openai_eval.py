"""End-to-End OpenAI Agent Evaluation with AgentGit.

This script demonstrates wrapping an OpenAI agent (or simulated LLM fallback),
taking snapshots across prompt iterations, and computing a behavioral diff.
"""

from __future__ import annotations

import os

from agentgit import diff, snapshot, track
from agentgit.report import print_diff_report


def run_evaluation() -> None:
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        @track(name="customer-support-openai")
        def agent_v1(task: str) -> str:
            res = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a concise customer support assistant."},
                    {"role": "user", "content": task},
                ],
            )
            return res.choices[0].message.content or ""
    else:
        # Fallback simulator when testing offline without an API key
        print("💡 No OPENAI_API_KEY detected. Running in simulated offline mode.\n")

        @track(name="customer-support-simulated")
        def agent_v1(task: str) -> str:
            return f"Processed task accurately: {task}"

    benchmark_tasks = [
        "What is your return policy for open-box electronics?",
        "Can I exchange an item purchased 45 days ago?",
        "How do I track an international shipment to Germany?",
    ]

    print("📸 Taking Baseline Snapshot (v1.0)...")
    snap_v1 = snapshot(agent_v1, version="v1.0", tasks=benchmark_tasks)
    print(f"   ✓ Completion: {snap_v1.metrics.task_completion_rate:.0%}")

    # Induce an updated prompt iteration
    @track(name="customer-support-v2")
    def agent_v2(task: str) -> str:
        return f"Greetings! We have thoroughly validated your inquiry: {task}"

    print("📸 Taking Updated Snapshot (v2.0)...")
    snap_v2 = snapshot(agent_v2, version="v2.0", tasks=benchmark_tasks)
    print(f"   ✓ Completion: {snap_v2.metrics.task_completion_rate:.0%}\n")

    print("📊 Computing Behavioral Diff:")
    diff_result = diff(snap_v1, snap_v2)
    print_diff_report(diff_result)


if __name__ == "__main__":
    run_evaluation()
