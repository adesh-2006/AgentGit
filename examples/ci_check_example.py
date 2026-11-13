"""Example: CI/CD pipeline integration.

Shows how to use AgentGit's ci-check to gate deployments
based on behavioral thresholds.
"""

from agentgit import track
from agentgit.snapshot import create_snapshot
from agentgit.ci import parse_rules, ci_check
from agentgit.report import print_ci_report


# A production agent
def support_agent(task: str) -> str:
    """Customer support agent."""
    if "refund" in task.lower():
        return "I've processed your refund request. You'll receive it in 3-5 business days."
    elif "status" in task.lower():
        return "Your order #1234 is currently in transit. Expected delivery: Tomorrow."
    elif "bug" in task.lower():
        raise RuntimeError("Unhandled error in bug reports")
    return f"I'd be happy to help with: {task}"


# Define test tasks
tasks = [
    "What's my order status?",
    "I want a refund for order #5678",
    "How do I reset my password?",
    "Report a bug in the checkout",
    "Cancel my subscription",
    "What are your business hours?",
]

# Track and snapshot
agent = track(support_agent, name="support-bot")
snap = create_snapshot(agent, "v2.1", tasks)

# Define CI rules
rules_str = "task_completion >= 0.80 AND error_rate < 0.20"
rules = parse_rules(rules_str)

# Run CI check
passed, details = ci_check(snap, rules)
print_ci_report(details, passed, snap.version)

if passed:
    print("✅ Ready to deploy!")
else:
    print("❌ Deployment blocked — fix regressions first.")
    exit(1)
