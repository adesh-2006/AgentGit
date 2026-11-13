# 📖 AgentGit Complete Usage Guide & Tutorial

This guide walks you through using **AgentGit** in everyday development: from wrapping your first agent in Python to automated CI/CD gating in GitHub Actions.

---

## 🎯 The Real-World Problem

Imagine you built an AI customer support or code generation agent. Tomorrow, you want to **edit your system prompt**, adjust tools, or **upgrade models** (e.g. from GPT-4o to Claude 3.5 Sonnet or a local Llama model).

- **Without AgentGit:** You edit the prompt, eyeball 2 or 3 test outputs, hope nothing broke, and deploy. When it loops or hallucinates at 3 AM, you have no idea why.
- **With AgentGit:** You get statistical proof in 30 seconds of whether the change improved or regressed your agent across every critical metric.

---

## 🚀 1. Using AgentGit in Python (3 Lines)

You don't need to rewrite your agent logic or learn a new framework. Just decorate your existing function with `@track`:

```python
from agentgit import track, snapshot, diff
from agentgit.report import print_diff_report

# Step 1: Wrap your existing agent function (OpenAI, Claude, LangChain, CrewAI, etc.)
@track(name="customer-support")
def my_agent(user_question: str):
    # Your standard LLM or tool-calling code here
    response = call_llm(user_question)
    return response

# Step 2: Define the benchmark tasks you care about
benchmark_tasks = [
    "What is your return policy?",
    "Can I cancel my order #9921?",
    "How long does shipping take to India?",
    "I want to speak with a human support representative.",
]

# Step 3: Take a snapshot of your agent BEFORE changing anything
v1 = snapshot(my_agent, version="v1.0", tasks=benchmark_tasks)
```

Now, make your changes — tweak your system prompt, change few-shot examples, or switch models:

```python
# Step 4: Take a snapshot of your NEW agent
v2 = snapshot(my_updated_agent, version="v2.0", tasks=benchmark_tasks)

# Step 5: See EXACTLY what changed behaviorally
diff_result = diff(v1, v2)
print_diff_report(diff_result)
```

---

## 🖥️ 2. Using the CLI in Your Terminal

AgentGit includes a full suite of Git-style terminal commands:

```bash
# 1. Initialize inside any project folder:
agentgit init --name my-agent

# 2. Check if a prompt has contradictions or injection risks:
agentgit lint prompts/system_prompt.txt

# 3. Create snapshots using your tasks or the built-in benchmarks:
agentgit snapshot v1.0 --tasks agentgit/benchmarks/tool_calling.json
agentgit snapshot v2.0 --tasks agentgit/benchmarks/tool_calling.json

# 4. View the terminal diff:
agentgit diff v1.0 v2.0

# 5. Export as PR comment markdown:
agentgit diff v1.0 v2.0 --format markdown

# 6. Export as a standalone dark-mode HTML dashboard:
agentgit diff v1.0 v2.0 --format html -o diff_report.html

# 7. Pinpoint which version introduced a regression:
agentgit bisect v1.0 v2.0 --metric error_rate

# 8. Attribution history for any metric or tool:
agentgit blame error_rate
agentgit blame tool:web_search

# 9. Step-by-step playback of any task execution:
agentgit replay v2.0 1

# 10. Forecast your monthly API bill at scale:
agentgit cost-predict v1.0 --dau 5000 --requests 4

# 11. Launch the interactive browser dashboard:
agentgit ui --port 8585
```

---

## 🤖 3. Automated CI/CD in GitHub Actions

You can use the official composite action to automatically test your agent and post behavioral diffs directly on every Pull Request:

```yaml
# .github/workflows/agent-ci.yml
name: Agent Behavioral CI Gate

on: [pull_request]

jobs:
  test-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e .

      # Fails the PR if completion drops below 85% or errors exceed 10%
      - name: Run Behavioral CI Check
        uses: adesh-2006/AgentGit@main
        with:
          version: v2.0
          rules: "task_completion >= 0.85 AND error_rate < 0.10"
          diff-base: v1.0
```

---

## ⚡ Quick Reference: Command Cheatsheet

| Task | Command |
|:---|:---|
| **Track calls, latency, tokens & cost** | `@track` Python decorator |
| **Record baseline behavior** | `agentgit snapshot <version> --tasks <file>` |
| **Compare two versions** | `agentgit diff <v1> <v2>` |
| **Automated root-cause regression hunting** | `agentgit bisect <good_v> <bad_v> --metric <m>` |
| **Behavioral attribution audit** | `agentgit blame <metric>` |
| **Step-by-step task trajectory replay** | `agentgit replay <version> <task_#>` |
| **Multi-variant model A/B comparison** | `agentgit matrix <v1> <v2> <v3>` |
| **Static prompt & contract linting** | `agentgit lint <prompt_file>` |
| **Production token bill forecast** | `agentgit cost-predict <version> --dau <n>` |
| **Semantic drift & contradiction check** | `agentgit drift <v1> <v2>` |
| **Export data to CSV/JSONL** | `agentgit export <version> --format csv` |
| **Interactive local web UI** | `agentgit ui --port 8585` |
| **Rollback active version** | `agentgit rollback <version>` |
