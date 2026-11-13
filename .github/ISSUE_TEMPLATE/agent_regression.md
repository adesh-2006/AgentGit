---
name: AI Behavioral Regression Report
about: Report an unexpected behavioral degradation or regression across agent versions
title: '[REGRESSION] '
labels: 'regression'
assignees: ''

---

**Behavioral Metric Regressed**
- [ ] Task Completion Rate
- [ ] Error Rate
- [ ] Latency Spike
- [ ] Token / Cost Spike
- [ ] Tool Call Looping / Failure

**Snapshot Comparison**
- Baseline Version: `vX.Y`
- Regressed Version: `vA.B`

**AgentGit Diff Output**
```
<!-- Paste output of 'agentgit diff' or 'agentgit diagnose' here -->
```

**Task Input that Failed**
```
<!-- Paste the specific prompt or task input here -->
```

**Root Cause or Investigation Notes**
What was changed between versions? (Prompt wording, model version, system instruction, tool definition, etc.)
