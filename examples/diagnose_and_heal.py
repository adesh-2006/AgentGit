"""Automated Regression Diagnosis & Healing with AgentGit.

Demonstrates:
1. Creating a baseline agent (v1.0)
2. Experiencing a prompt regression (v2.0)
3. Using create_diff & task regression analysis to diagnose root causes
4. Deploying a healed version (v2.1) where all regressions are resolved
"""

from __future__ import annotations

from agentgit import diff, snapshot, track
from agentgit.report import print_diff_report


def main() -> None:
    tasks = [
        "Check account balance for user #104",
        "Transfer $50 to savings account",
        "Schedule recurring payment on the 1st of every month",
    ]

    # Baseline Agent v1.0
    @track(name="banking-agent")
    def agent_v1(task: str) -> str:
        return f"Completed: {task}"

    print("1️⃣ Taking snapshot of baseline v1.0...")
    v1 = snapshot(agent_v1, version="v1.0", tasks=tasks)

    # Buggy Agent v2.0 (Prompt alteration caused unhandled transfer timeout)
    @track(name="banking-agent")
    def agent_v2(task: str) -> str:
        if "transfer" in task.lower():
            raise TimeoutError("Transaction network timed out after 30s")
        return f"Completed: {task}"

    print("2️⃣ Taking snapshot of regressed v2.0...")
    v2 = snapshot(agent_v2, version="v2.0", tasks=tasks)

    print("3️⃣ Diffing v1.0 → v2.0 to catch regression:")
    diff_v2 = diff(v1, v2)
    print_diff_report(diff_v2)

    # Check regressed tasks
    for rt in diff_v2.regressed_tasks:
        print(f"🔴 Regression in Task #{rt.task_index + 1}: {rt.task_input}")
        print(f"   Root Cause: {rt.error}")
        print(f"   💡 Suggested Fix: {rt.suggested_fix}\n")

    # Healed Agent v2.1 (Implemented retry mechanism as suggested)
    @track(name="banking-agent")
    def agent_v2_1(task: str) -> str:
        if "transfer" in task.lower():
            # Retry succeeded
            return f"Completed with retry: {task}"
        return f"Completed: {task}"

    print("4️⃣ Taking snapshot of healed v2.1...")
    v2_1 = snapshot(agent_v2_1, version="v2.1", tasks=tasks)

    print("5️⃣ Verifying healed version against v2.0:")
    diff_healed = diff(v2, v2_1)
    print_diff_report(diff_healed)


if __name__ == "__main__":
    main()
