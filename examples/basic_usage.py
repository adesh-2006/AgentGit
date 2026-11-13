"""Example: Using AgentGit with a simple agent function.

This demonstrates the core workflow:
1. Track an agent
2. Create a baseline snapshot
3. Change the agent
4. Snapshot again
5. Diff to see behavioral changes
"""

from agentgit import track
from agentgit.snapshot import create_snapshot
from agentgit.diff import create_diff
from agentgit.report import print_snapshot_report, print_diff_report


# Step 1: Define your agent (any callable)
def my_agent_v1(task: str) -> str:
    """V1 of our agent — simple and direct."""
    if "summarize" in task.lower():
        return f"Summary: {task[:50]}..."
    elif "analyze" in task.lower():
        return f"Analysis: The data shows positive trends in {task}"
    else:
        return f"I processed: {task}"


def my_agent_v2(task: str) -> str:
    """V2 — more thorough but slower."""
    import time
    time.sleep(0.01)  # Simulating more processing
    
    if "summarize" in task.lower():
        return f"Detailed Summary: After careful review, {task[:80]}... Key points: 1) Growth 2) Stability"
    elif "analyze" in task.lower():
        return f"Deep Analysis: Comprehensive review of {task} reveals multiple trends..."
    elif "error" in task.lower():
        raise ValueError("Cannot process error-related tasks")
    else:
        return f"Thoroughly processed: {task} with additional context and verification"


# Step 2: Define tasks to test
tasks = [
    "Summarize the Q3 earnings report",
    "Analyze customer churn data",
    "Write a response to the client email",
    "Summarize the product roadmap",
    "Analyze competitor pricing strategy",
]

# Step 3: Track and snapshot V1
print("=" * 60)
print("STEP 1: Snapshot Agent V1")
print("=" * 60)
tracked_v1 = track(my_agent_v1, name="my-agent")
snap_v1 = create_snapshot(tracked_v1, "v1.0", tasks)
print_snapshot_report(snap_v1)

# Step 4: Track and snapshot V2
print("=" * 60)
print("STEP 2: Snapshot Agent V2")
print("=" * 60)
tracked_v2 = track(my_agent_v2, name="my-agent")
snap_v2 = create_snapshot(tracked_v2, "v2.0", tasks)
print_snapshot_report(snap_v2)

# Step 5: Diff them!
print("=" * 60)
print("STEP 3: Behavioral Diff")
print("=" * 60)
diff_result = create_diff(snap_v1, snap_v2)
print_diff_report(diff_result)
