<p align="center">
  <h1 align="center">🧬 AgentGit</h1>
  <p align="center"><strong>Git for AI Agent Behavior</strong></p>
  <p align="center">
    Version, diff, and rollback how your agent <em>behaves</em> — not just the code.
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentgit/"><img src="https://img.shields.io/pypi/v/agentgit?color=blue&label=pypi" alt="PyPI"></a>
  <a href="https://github.com/adesh-2006/AgentGit/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
  <a href="https://github.com/adesh-2006/AgentGit/actions"><img src="https://github.com/adesh-2006/AgentGit/workflows/CI/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/agentgit/"><img src="https://img.shields.io/pypi/pyversions/agentgit" alt="Python"></a>
</p>

---

> You changed a prompt. You upgraded the model. You tweaked a tool.
> 
> **Did your agent get better or worse?**
> 
> Right now, you have no idea. You manually test a few examples, hope for the best, and ship it.
> 
> **AgentGit fixes this.** It gives you `git diff` — but for agent *behavior*.

---

## ⚡ Quickstart

```bash
pip install agentgit
```

```python
from agentgit import track
from agentgit.snapshot import create_snapshot
from agentgit.diff import create_diff
from agentgit.report import print_diff_report

# 1. Wrap your agent (any callable — OpenAI, Anthropic, LangChain, or plain function)
agent_v1 = track(your_agent_function, name="my-agent")

# 2. Snapshot how it behaves right now
snap_v1 = create_snapshot(agent_v1, "v1.0", tasks=["task1", "task2", "task3"])

# 3. Change your prompt / model / tools
agent_v2 = track(updated_agent_function, name="my-agent")
snap_v2 = create_snapshot(agent_v2, "v2.0", tasks=["task1", "task2", "task3"])

# 4. See EXACTLY what changed behaviorally
result = create_diff(snap_v1, snap_v2)
print_diff_report(result)
```

**Output:**

```
╭──────── AgentGit Diff: v1.0 → v2.0 ────────╮
│                                               │
│  Metric              v1.0     v2.0    Change  │
│  ─────────────────────────────────────────── │
│  Task Completion     87%      91%     ↑ 4.6%  ✅ │
│  Avg Steps / Task    3.2      2.8     ↓ 12.5% ✅ │
│  Avg Latency         450ms    380ms   ↓ 15.6% ✅ │
│  Error Rate          13%      5%      ↓ 61.5% ✅ │
│  Avg Cost / Task     $0.04    $0.06   ↑ 50.0% ⚠️ │
│                                               │
│  Tool Usage:                                  │
│    web_search        12       18      ↑ 50%   │
│    database_query    8        5       ↓ 37%   │
│                                               │
╰───────────────────────────────────────────────╯
╭─────────────────────────────────────────────────╮
│ ⚠️  Mixed — 4 improved, 1 regressed (Avg Cost). │
╰─────────────────────────────────────────────────╯
```

**That output? Nobody else can give it to you today.**

---

## 🤔 Why AgentGit?

| Without AgentGit | With AgentGit |
|:---|:---|
| "I changed the prompt... did it get better?" 🤷 | `agentgit diff v1.0` → see exactly what changed |
| Manually test 5 examples and hope for the best | Automatically test 100 tasks and get statistical proof |
| No idea what caused a production regression | Full behavioral changelog across versions |
| CI/CD can't gate on agent quality | `agentgit ci-check` fails the build if behavior regresses |
| Agent upgraded to GPT-5 — fingers crossed 🤞 | Behavioral diff proves GPT-5 is 12% better on your tasks |

---

## 🔌 Works With Everything

AgentGit is **framework-agnostic**. It wraps any callable:

```python
# ✅ Raw OpenAI
from openai import OpenAI
client = OpenAI()

@track(name="openai-agent")
def my_openai_agent(task):
    return client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": task}]
    )

# ✅ Anthropic
@track(name="claude-agent")
def my_claude_agent(task):
    return anthropic.messages.create(model="claude-3-5-sonnet", ...)

# ✅ LangChain
agent = track(my_langchain_agent)

# ✅ CrewAI
crew = track(my_crew.kickoff)

# ✅ Any Python function
@track
def my_custom_agent(task):
    return do_stuff(task)
```

**Zero migration. Zero new framework to learn. Just wrap and go.**

---

## 🖥️ CLI

```bash
# Initialize in your project
agentgit init --name my-agent

# Create snapshots using built-in benchmarks or your own tasks
agentgit snapshot v1.0 --tasks agentgit/benchmarks/tool_calling.json

# See the terminal diff
agentgit diff v1.0 v2.0

# Export as GitHub PR comment markdown
agentgit diff v1.0 v2.0 --format markdown

# Export as a standalone dark-mode HTML dashboard
agentgit diff v1.0 v2.0 --format html -o diff_report.html

# List all snapshots  
agentgit list

# Show a snapshot's details
agentgit show v1.0

# Rollback to a known-good version
agentgit rollback v1.0

# CI/CD gate — fail the build if behavior regresses
agentgit ci-check v2.0 --rules "task_completion >= 0.85 AND error_rate < 0.10"
```

---

## 💬 Automated GitHub PR Comments

Post behavioral diffs directly on pull requests whenever prompt or model changes are proposed:

```yaml
# .github/workflows/agent-diff.yml
name: Agent Behavioral Diff

on:
  pull_request:
    paths:
      - 'prompts/**'
      - 'agents/**'

jobs:
  behavior-diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .

      - name: Generate Behavioral Diff
        run: |
          agentgit diff v1.0 v2.0 --format markdown > diff.md

      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const body = fs.readFileSync('diff.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

---

## 🚦 CI/CD Integration

Block deployments when agent behavior regresses:

```yaml
# .github/workflows/agent-ci.yml
- name: Check agent behavior
  run: |
    agentgit ci-check v2.0 \
      --rules "task_completion >= 0.85 AND error_rate < 0.10 AND avg_cost < 0.05"
```

```python
# Or programmatically:
from agentgit.ci import parse_rules, ci_check

rules = parse_rules("task_completion >= 0.85 AND error_rate < 0.10")
passed, details = ci_check(snapshot, rules)

if not passed:
    print("❌ Deployment blocked!")
    sys.exit(1)
```

---

## 📊 What AgentGit Tracks

For every agent invocation, AgentGit records:

| Metric | What It Tells You |
|:---|:---|
| **Task Completion Rate** | % of tasks the agent completed successfully |
| **Error Rate** | % of tasks that threw exceptions |
| **Avg Steps / Task** | How many tool calls the agent makes (efficiency) |
| **Avg Latency** | How long each task takes |
| **Avg Tokens / Task** | Token consumption per task |
| **Avg Cost / Task** | Dollar cost per task (auto-estimated) |
| **Tool Usage** | Which tools were called and how often |
| **Model Used** | Which LLM model was invoked |

---

## 🧩 How It Works

```
Your Code (unchanged)
       │
       ▼
   track() wrapper ──── records every call silently
       │
       ▼
   create_snapshot() ── runs N tasks, builds behavioral profile  
       │
       ▼
   create_diff() ────── compares two profiles statistically
       │
       ▼
   Beautiful report ─── shows what improved / regressed / neutral
```

AgentGit doesn't change how your agent works. It just observes and measures.

---

## 🗺️ Roadmap

- [x] Core tracker — wrap any callable
- [x] Behavioral snapshots
- [x] Behavioral diffs with polarity-aware scoring
- [x] CI/CD gate (`agentgit ci-check`)
- [x] OpenAI & Anthropic metric extraction
- [x] Beautiful Rich terminal output
- [ ] Web dashboard (interactive diff viewer)
- [ ] Async agent support
- [ ] LangChain/CrewAI deep integration
- [ ] Snapshot comparison leaderboard
- [ ] Prompt hash tracking
- [ ] A/B testing mode
- [ ] GitHub Action (official)

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Development setup
git clone https://github.com/adesh-2006/AgentGit.git
cd AgentGit
pip install -e ".[dev]"
pytest -v
```

---

## 📜 License

MIT — use it however you want.

---

<p align="center">
  <strong>If this saves you time, give it a ⭐</strong>
  <br>
  <sub>Built by <a href="https://github.com/adesh-2006">@adesh-2006</a></sub>
</p>
