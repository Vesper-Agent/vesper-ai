# Vesper — High-Level Design (HLD)

## 1. Overview

Vesper is an infrastructure tool for running AI agents in production — "Kubernetes for AI agents."
A developer declares an agent in a YAML manifest; Vesper validates it, versions it, and executes it
with tool-calling, persistent memory, cost governance, and an audit trail. It is used through a CLI
and a Python SDK that share the same core engine.

This document describes the system at the architecture level. For class- and function-level detail,
see `LLD.md`.

## 2. Design goals & principles

- **Declarative** — an agent is a manifest (`apiVersion`, `kind`, `model`, `tools`, `memory`,
  `budget`), applied and versioned like infrastructure.
- **Library-first** — all behavior lives in the Python package; the CLI and SDK are thin callers of
  the same `Agent` engine. Neither owns logic.
- **Provider-agnostic core** — the run loop is written against a normalized provider interface;
  OpenAI, Anthropic, and Google are interchangeable adapters.
- **Version-gated evolution** — `apiVersion` decides what a release supports. V1 is single-agent;
  future capabilities arrive under `vesper/v2` without breaking v1 manifests.
- **Governed by default** — cost tracking, budget caps, and audit logging are part of every run, not
  add-ons.

## 3. System context

```
        Developer
           │
   writes  │  agent.yml  (declarative manifest)
           ▼
   ┌───────────────┐        ┌───────────────┐
   │   Vesper CLI  │        │  Vesper SDK   │
   │  (vesper ...) │        │ (import vesper)│
   └───────┬───────┘        └───────┬───────┘
           │   both call the same core        │
           └───────────────┬──────────────────┘
                           ▼
                 ┌──────────────────┐        ┌──────────────────┐
                 │   Vesper Core    │──────▶ │  LLM Providers   │
                 │ (registry + Agent)│       │ OpenAI/Anthropic/│
                 └────────┬─────────┘        │     Google       │
                          │                  └──────────────────┘
                          ▼
                 Local state (~/.vesper): SQLite
```

## 4. Two planes

Vesper separates cleanly into a **control plane** (managing agent definitions) and an **execution
plane** (running agents).

```
CONTROL PLANE                         EXECUTION PLANE
─────────────                         ───────────────
manifest (YAML)                       Agent.run(input)
   │ validate_manifest                   │ load memory
   ▼                                      ▼
AgentRegistry ── SQLiteVesperDatabase   provider.generate(messages, tools)
   │ apply/list/history/show/delete       │ tool-calling loop
   ▼                                      ▼
registry.db                            calculate_cost / budget gate
                                          │ save memory + audit
                                          ▼
                                       memory.db, audit.db
```

## 5. Component overview

| Component | Module | Responsibility |
|---|---|---|
| **Manifest schema** | `models.py` | Pydantic models + strict validation; the `apiVersion`/`kind` gate. |
| **Registry** | `registry.py`, `storage.py`, `sqlite_storage.py` | Validate, persist, and version manifests. |
| **Runtime (Agent)** | `runtime.py` | The execution engine: run loop, tool-calling, memory + budget + audit orchestration. |
| **Providers** | `providers/*` | Normalize each LLM SDK to a common `generate()` / `LLMResponse`. |
| **Provider factory** | `factory.py`, `model_costs.json` | Route model → provider; compute cost from the pricing table. |
| **Tools** | `tools.py`, `builtin_tools.py` | Tool abstraction, registry, schema generation, entryPoint loading, built-ins. |
| **Memory** | `memory.py` | Conversation persistence with scopes, retention, truncation. |
| **Audit** | `audit.py` | Run history log. |
| **Config** | `config.py` | Home directory + `.env` loading. |
| **CLI** | `cli.py` | Typer command surface over the core. |

## 6. The 7 Engines (product architecture)

Vesper's architecture is framed as seven engines. V1 implements four.

| Engine | Realized by | Status |
|---|---|---|
| Agent Registry Engine | `registry.py`, `sqlite_storage.py`, `models.py` | ✅ V1 |
| Agent Lifecycle Engine | `runtime.py`, `providers/*`, `factory.py`, `tools.py` | ✅ V1 |
| Agent Memory Engine | `memory.py` | ✅ V1 |
| FinOps Engine | `factory.py` (cost), budget logic in `runtime.py`, `audit.py` | ✅ V1 |
| Agent Communication Bus | (fleets/task graphs) | ⏳ v2 |
| Quality & Eval Engine | (eval datasets / CI gates) | ⏳ v2 |
| Security Engine | (guardrails / policy-as-code) | ⏳ v2 |

## 7. Key data flows

### 7.1 Apply (deploy a manifest)
```
vesper apply -f agent.yml
  → validate_manifest(file)                 # YAML → Pydantic (strict)
  → AgentRegistry.apply_manifest
     → SQLiteVesperDatabase.save_agent_spec
        → diff JSON vs active version
        → same? NoChangeDetectedError : insert new version + repoint active
```

### 7.2 Run (execute an agent)
```
vesper run <name> --input "..."     (or  vesper.load(name).run("..."))
  → Agent.load(name)                        # active manifest from registry
  → Agent.run(input, session)
     1. filter tools by manifest.tools → schemas
     2. budget preflight (unpriced + budget → refuse)
     3. load memory (scope key, retention, truncation)
     4. loop:
          provider.generate(messages, schemas)
          accumulate tokens → calculate_cost
          cost > maxCostPerRun → BudgetExceededError (record failed)
          tool calls? execute via registry, append results, repeat
          else → save memory, record audit(completed), return RunResult
```

## 8. Storage architecture

Local-first. All state under `~/.vesper` (override via `VESPER_HOME`). Three separate SQLite files,
one concern each:

| File | Owner | Tables | Concern |
|---|---|---|---|
| `registry.db` | `SQLiteVesperDatabase` | `resources`, `manifests` | Deploy state & versions |
| `memory.db` | `MemoryStore` | `memory` | Conversation history |
| `audit.db` | `AuditStore` | `runs` | Run log / FinOps history |

Separation keeps "what is deployed", "what the agent remembers", and "what happened" independent —
each can be queried, pruned, or deleted on its own. `vesper delete` cascades across all three.

## 9. Provider abstraction

The runtime never speaks a vendor SDK directly. Every provider implements:

```
generate(messages, tools=None) -> LLMResponse(content, prompt_tokens, completion_tokens, tool_calls)
```

Each adapter translates Vesper's neutral message/tool format into the vendor's native shape and parses
the response back into `LLMResponse` + `ToolCall`s. Adding a provider is additive: implement the
interface and add a routing prefix in `factory.get_provider`.

## 10. Technology choices

- **Python 3.9+**, packaged with setuptools (`src/` layout).
- **Typer + Rich** — CLI framework and terminal rendering.
- **Pydantic v2** — manifest validation, discriminated typing, result models.
- **SQLite (stdlib `sqlite3`)** — zero-dependency local state.
- **PyYAML** — manifest parsing.
- **openai / anthropic / google-genai** — provider SDKs.
- Pricing as a bundled JSON data file; `.env` parsed with stdlib (no `python-dotenv`).

## 11. Non-functional characteristics

- **Extensibility** — new providers, tools, and (v2) engines slot in without touching the run loop.
- **Observability** — every run is costed and logged; `alertAt` surfaces on the result.
- **Safety** — budgets are hard caps; unpriced models are refused when a budget is set.
- **Portability** — no server, no external DB; runs anywhere Python does.
- **Forward compatibility** — `apiVersion` gate lets v2 add fleets/evals/guardrails without breaking v1.

## 12. Known limitations (V1)

- Single agent per manifest (fleets are v2).
- One tool call per turn assumed; parallel tool calls in a single turn are not handled.
- Memory overflow uses truncation only (`summarise_on_overflow` accepted but not yet active).
- Local backend only (Postgres/cloud is a stubbed future backend).
