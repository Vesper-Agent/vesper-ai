# Vesper

Infrastructure for managing AI agents in production. Vesper lets you declare an agent in a YAML manifest, version it like code, and run it — from the CLI or a Python SDK — with tool-calling, persistent memory, budget enforcement, and an audit trail.

Supports **OpenAI**, **Anthropic (Claude)**, and **Google (Gemini)** models out of the box.

---

## Install

```bash
pip install vesper-ai
```

The package installs as `vesper-ai`, but you import and run it as `vesper` (`import vesper`, `vesper ...`).

Set your provider API key in the environment, or drop a `.env` file in your project root (Vesper auto-loads it):

```
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

---

## Quickstart (CLI)

**1. Initialize** the local state directory (`~/.vesper`):

```bash
vesper init
```

**2. Write a manifest** — `agent.yml`:

```yaml
apiVersion: vesper/v1
kind: Agent

name: researcher
model: gpt-4o-mini
entryPoint: examples/agent.py     # loads your @vesper.tool functions

tools:
  - web_search                    # built-in
  - get_stock_price               # custom, from entryPoint

memory:
  scope: project                  # persistent thread for this agent
  retentionDays: 30

budget:
  maxCostPerRun: 0.05
  alertAt: 0.04
```

**3. Validate & deploy** (each apply is versioned; an unchanged apply is skipped):

```bash
vesper validate -f agent.yml
vesper apply -f agent.yml
```

**4. Run it:**

```bash
vesper run researcher --input "What is the price of AAPL?"
```

```
AAPL is trading at $187.42.
cost $0.000041 · 146 in / 32 out · session sess_a91f...
```

**5. Inspect and manage:**

```bash
vesper list                       # all deployed agents + versions
vesper history researcher         # version history
vesper show researcher            # active config as JSON
vesper runs researcher            # run history: cost, tokens, status, time
vesper delete researcher --yes    # remove agent + versions + memory + audit
```

### `run` options

```bash
vesper run researcher --input "..." --session proj-42   # reuse a session (stateful memory)
vesper run researcher --input-file ./question.txt       # read input from a file
vesper run researcher --input "..." --max-cost 0.20     # override the manifest budget for this run
```

---

## Quickstart (SDK)

Define tools with the `@vesper.tool` decorator:

```python
# examples/agent.py
import vesper

@vesper.tool(description="Get the current stock price for a ticker symbol")
def get_stock_price(ticker: str) -> str:
    return f"{ticker.upper()} is trading at $187.42"
```

Load a deployed agent and run it:

```python
import vesper

agent = vesper.load("researcher")          # active manifest from the registry
result = agent.run("What is the price of AAPL?")

print(result.content)
print(result.cost, result.prompt_tokens, result.completion_tokens)
```

Run straight from a YAML file, or register tools programmatically:

```python
from vesper import Agent, tool

@tool(description="Look up an order by id")
def get_order(order_id: str) -> dict:
    return {"id": order_id, "status": "shipped"}

agent = Agent.from_manifest("agent.yml", tools=[get_order])
print(agent.run("Where is order 1234?").content)
```

Stateful, multi-turn memory via sessions:

```python
first = agent.run("What is RAG?", session="proj-42")
agent.run("Compare it to fine-tuning", session="proj-42")   # sees the first turn
```

Inspect past runs:

```python
for r in agent.runs():
    print(r.run_id, r.status, r.cost, r.created_at)
```

---

## How it works

- **Manifests & versioning** — `apply` stores each manifest in SQLite (`~/.vesper/registry.db`); re-applying a changed manifest bumps its version, an identical one is a no-op.
- **Providers** — the model name routes to a provider (`gpt-*` → OpenAI, `claude-*` → Anthropic, `gemini-*` → Google). Any model these providers offer will run.
- **Tools** — built-in `web_search` and `read_file`, plus any `@vesper.tool` functions in your `entryPoint`. The manifest's `tools` list is the whitelist the model may call.
- **Memory** — `scope: session` keeps a thread per session id (minted as `sess_…` and returned on the result if you don't pass one); `scope: project` keeps one persistent thread per agent. History older than `retentionDays` is pruned; long histories are truncated oldest-first. Stored in `~/.vesper/memory.db`.
- **Budget (FinOps)** — costs are tracked per run from a curated pricing table. A run that would exceed `maxCostPerRun` stops with `BudgetExceededError`; crossing `alertAt` flags `RunResult.alerted`. If a model has no pricing entry, it still runs — unless a budget is set, in which case the run is refused (a cap can't be enforced without a price).
- **Audit** — every run (completed or budget-aborted) is logged to `~/.vesper/audit.db` and surfaced via `vesper runs` / `agent.runs()`.

Model pricing in `model_costs.json` is derived from [LiteLLM](https://github.com/BerriAI/LiteLLM)'s
`model_prices_and_context_window.json` (MIT licensed), filtered to the supported providers.

---

## Not in V1

The `apiVersion` field gates what a release supports. V1 (`vesper/v1`) is single-agent only. Planned for a future version: **agent fleets / task graphs** (`kind: AgentFleet`), **guardrails**, **evals / CI gates**, memory **summarization** strategies, and a **cloud (Postgres) backend**. Manifests using these are rejected with a clear message today.
