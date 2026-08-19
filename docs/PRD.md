# Vesper — Product Requirements

## Problem

Building AI agents is easy nowadays, but running them in production needs a lot of manual scripts to manage persistent agent memory, quality and eval gates, security, FinOps, and inter-agent communication in agent fleets. There is no standalone infrastructure for managing AI agents in production. In other words, there is no **Kubernetes for AI agents**.

## Solution

Vesper — infrastructure to manage AI agents in production. A developer defines agents and their configuration in a YAML manifest and runs them through Vesper's CLI or Python SDK (`@vesper.tool` decorators to link execution functions). Vesper handles the agent lifecycle, persistent memory, eval gates, security-as-code, FinOps, and multi-agent communication.

Just like Kubernetes takes a declarative manifest and manages the lifecycle of a container, Vesper takes a declarative manifest and manages the lifecycle of an AI agent.

## The 7 Engines

Vesper is built as seven layers. V1 ships the foundation (Registry, Lifecycle, Memory, FinOps); the remaining three follow in later releases, gated behind `apiVersion`.

| Engine | What it does | Status |
|---|---|---|
| **Agent Registry Engine** | Declarative YAML manifests, schema validation, git-like versioning, SQLite state store (`apply` / `list` / `history` / `show` / `delete`). | ✅ V1 |
| **Agent Lifecycle Engine** | Runs agents: provider execution across OpenAI / Anthropic / Google, the tool-calling loop, built-in + `entryPoint` tools, run records. | ✅ V1 |
| **Agent Memory Engine** | Stateful memory with `session` / `project` scopes, `retentionDays` pruning, and overflow truncation. | ✅ V1 |
| **FinOps Engine** | Per-run cost tracking from a curated pricing table, `maxCostPerRun` hard caps, `alertAt` warnings, and an audit log of every run. | ✅ V1 |
| **Agent Communication Bus** | Multi-agent fleets, task graphs (`dependsOn`), and inter-agent message passing (`kind: AgentFleet`). | ⏳ Upcoming |
| **Quality & Eval Engine** | Eval datasets, pass thresholds, and CI gates (`ciGate`) to block regressions before deploy. | ⏳ Upcoming |
| **Security Engine** | Guardrails and policy-as-code enforced at runtime around agent inputs, outputs, and tool use. | ⏳ Upcoming |

## Who is this for

Production teams or solo developers who need to manage and orchestrate their AI agents.

## What we are not building

- No agentic framework integration such as LangGraph
- No cloud agent management service
- No web UI

## Success metric

A developer can define agents and their configuration in a YAML file, use the SDK and `@vesper.tool` decorator to link the agent's execution functions, and rely on Vesper to persist and re-inject memory across agent calls — while staying within an enforced cost budget and keeping a full audit trail.

## V1 scope (shipped)

- `apiVersion: vesper/v1`, `kind: Agent` (single-agent only; fleets gated to a future `vesper/v2`).
- Three providers (OpenAI, Anthropic, Google) routed by model name.
- Tool-calling with built-in tools (`web_search`, `read_file`) and custom `@vesper.tool` functions loaded from `entryPoint`.
- Session/project memory, budget enforcement, and run audit.
- CLI (`init`, `validate`, `apply`, `list`, `history`, `show`, `run`, `runs`, `delete`) and Python SDK (`vesper.load`, `Agent`, `RunResult`, `tool`).
