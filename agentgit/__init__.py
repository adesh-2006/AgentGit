"""AgentGit — Git for AI Agent Behavior.

Version, diff, and rollback how your agent behaves, not just the code.
Works with any AI framework: OpenAI, Anthropic, LangChain, CrewAI, or raw functions.

Usage::

    from agentgit import track, snapshot, diff

    # Wrap any agent
    agent = track(your_agent_function)

    # Run tasks and snapshot behavior
    snap = snapshot(agent, "v1.0", tasks=["task1", "task2"])

    # Change your prompt/model, snapshot again
    snap2 = snapshot(agent, "v2.0", tasks=["task1", "task2"])

    # See what changed behaviorally
    result = diff("v1.0", "v2.0")
"""

__version__ = "0.1.0"

from agentgit.bisect import bisect_metric
from agentgit.blame import blame_metric
from agentgit.ci import ci_check
from agentgit.diff import create_diff as diff
from agentgit.matrix import build_comparison_matrix
from agentgit.replay import get_task_trace
from agentgit.report import diff_to_html, diff_to_markdown
from agentgit.snapshot import create_snapshot as snapshot
from agentgit.storage import AgentGitStore
from agentgit.tracker import track
from agentgit.ui import start_ui

__all__ = [
    "__version__",
    "track",
    "snapshot",
    "diff",
    "ci_check",
    "diff_to_markdown",
    "diff_to_html",
    "blame_metric",
    "bisect_metric",
    "build_comparison_matrix",
    "get_task_trace",
    "start_ui",
    "AgentGitStore",
]
