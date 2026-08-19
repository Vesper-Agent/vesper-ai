# Vesper — Low-Level Design (LLD)

Detailed design of every module. See `HLD.md` for the architecture-level view.

Package layout (`src/vesper/`):

```
config.py         paths + .env loading
models.py         manifest schema (Pydantic)
exceptions.py     error hierarchy
storage.py        VesperDatabase (ABC)
sqlite_storage.py SQLiteVesperDatabase
registry.py       validate_manifest, AgentRegistry, get_registry
factory.py        get_provider, calculate_cost, MODEL_COSTS
model_costs.json  curated pricing table
providers/
  base.py         ToolCall, LLMResponse, BaseProvider
  openai.py       OpenAIProvider
  anthropic.py    AnthropicProvider
  google.py       GoogleProvider
tools.py          VesperTool, tool, ToolRegistry, load_entrypoint_tools
builtin_tools.py  read_file, web_search, BUILTIN_TOOLS
memory.py         MemoryStore, estimate_tokens
audit.py          RunRecord, AuditStore
runtime.py        RunResult, Agent
cli.py            Typer app
```

---

## 1. Manifest schema — `models.py`

```python
class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")   # unknown fields are rejected

class MemoryConfig(StrictBaseModel):
    scope: str
    retentionDays: int
    strategy: Optional[str] = None               # accepted; V1 always truncates

class BudgetConfig(StrictBaseModel):
    maxCostPerRun: Optional[float] = None
    alertAt: Optional[float] = None

class AgentSpec(StrictBaseModel):
    name: str
    model: str
    entryPoint: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    memory: Optional[MemoryConfig] = None
    budget: Optional[BudgetConfig] = None

class AgentManifest(AgentSpec):
    apiVersion: Literal["vesper/v1"]
    kind: Literal["Agent"]

VesperManifest = AgentManifest
manifest_adapter = TypeAdapter(VesperManifest)
```

- `extra="forbid"` makes parked fields (`guardrails`, `eval`, …) fail validation with a clear message.
- The schema knows only `kind: Agent` under `apiVersion: vesper/v1`. Fleets and other kinds are the v2 gate.

## 2. Errors — `exceptions.py`

```
VesperError (base)
├── InvalidAgentSpecError        # YAML fails validation
├── NoChangeDetectedError        # apply matches active version
├── ResourceNameNotFoundError
├── ResourceVersionNotFoundError
├── ModelNotSupportedError       # no provider for model prefix
├── BudgetExceededError          # cap exceeded OR budget-set-but-unpriced
├── ToolNotFoundError            # manifest tool not registered
└── (InvalidModelNameError, LLMProviderError — reserved)
```

## 3. Registry — `storage.py`, `sqlite_storage.py`, `registry.py`

### 3.1 `VesperDatabase` (ABC) — the backend contract
`setup_tables`, `save_agent_spec`, `get_resources`, `get_history`, `get_resource_config`,
`delete_resource`. Enables swapping SQLite for a future Postgres backend.

### 3.2 `SQLiteVesperDatabase` — schema
```sql
CREATE TABLE resources (
    name TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    active_version_id TEXT
);
CREATE TABLE manifests (
    id TEXT PRIMARY KEY,               -- uuid4 hex
    resource_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL,        -- manifest.model_dump_json()
    FOREIGN KEY (resource_name) REFERENCES resources(name) ON DELETE CASCADE,
    UNIQUE (resource_name, version)
);
```
`save_agent_spec(manifest) -> (id, version)`:
- new resource → insert `resources` + `manifests` v1.
- existing → compare `content_json` to the active version; identical → `NoChangeDetectedError`;
  else insert `version+1` and repoint `active_version_id`.

`get_resources` joins `resources` to the active manifest for `(name, kind, version)`.
`get_resource_config(name, version=None)` returns the active (or specific) version, re-validated via
`manifest_adapter.validate_json`.

### 3.3 `registry.py`
- `validate_manifest(file_path) -> VesperManifest` — module function (shared by CLI + SDK). Loads YAML,
  raises `FileNotFoundError`; early-rejects `kind: AgentFleet` with a friendly message; validates via
  `manifest_adapter`, formatting Pydantic errors into `InvalidAgentSpecError`.
- `AgentRegistry(db)` — thin orchestration: `validate_manifest` (delegates), `apply_manifest`,
  `get_all_resources`, `get_history`, `get_resource_config`, `delete_resource`.
- `get_registry() -> AgentRegistry` — reads `~/.vesper/config.json`; `backend: local` →
  `SQLiteVesperDatabase`; missing config or other backend → `VesperError`.

## 4. Providers — `providers/`

### 4.1 `base.py`
```python
class ToolCall(BaseModel):
    id: str; name: str; arguments: dict

class LLMResponse(BaseModel):
    content: str = ""
    prompt_tokens: int
    completion_tokens: int
    tool_calls: List[ToolCall] = []

class BaseProvider(ABC):
    def __init__(self, model_name): ...
    @abstractmethod
    def generate(self, messages, tools=None) -> LLMResponse: ...
```

### 4.2 Neutral message format (the loop's contract)
```
{"role": "user",      "content": str}
{"role": "assistant", "content": str}                       # text turn
{"role": "assistant", "tool_calls": [ToolCall.model_dump()]}# tool-call turn
{"role": "tool", "tool_call_id": id, "name": n, "content": str}  # tool result
```
Neutral tool schema (from `VesperTool.schema()`):
`{"name", "description", "parameters": {"type":"object","properties":{…},"required":[…]}}`

### 4.3 Per-provider translation
| | Tool schema | Tool-call turn | Tool result | Parsed from |
|---|---|---|---|---|
| **OpenAI** (Responses) | `{type:function, …}` | `function_call` input item | `function_call_output` | `output[].type=="function_call"` |
| **Anthropic** | `{name, description, input_schema}` | `tool_use` block | `tool_result` block (user) | `content[].type=="tool_use"` |
| **Google** | `function_declarations` | `function_call` part (model) | `function_response` part | `response.function_calls` |

Notes: OpenAI serializes `arguments` as a JSON string; Anthropic requires `max_tokens` (4096) and uses
`input_schema`; Google has no call-id (`ToolCall.id = name`) and maps roles `assistant→model`.

## 5. Provider factory & pricing — `factory.py`

```python
MODEL_COSTS = json.load(open("model_costs.json"))   # {model: {input, output}} per 1M tokens

def calculate_cost(model, prompt_tokens, completion_tokens) -> Optional[float]:
    if model not in MODEL_COSTS: return None          # graceful miss (not an error)
    return (prompt*in_price + completion*out_price) / 1_000_000

def get_provider(model_name) -> BaseProvider:
    gpt-/o1-/o3- → OpenAIProvider
    claude-*     → AnthropicProvider
    gemini-*     → GoogleProvider
    else         → ModelNotSupportedError
```
Support (routing) is decoupled from pricing (lookup). An unpriced model still runs; the *budget layer*
decides whether that's allowed.

## 6. Tools — `tools.py`, `builtin_tools.py`

```python
class VesperTool:
    fn, name (= fn.__name__), description (= arg or __doc__)
    execute(**kwargs)      # calls fn
    schema() -> dict       # JSON schema from inspect.signature; params w/o default → required

@tool(description=None)    # decorator → returns a VesperTool
class ToolRegistry:
    register(tool); filter_by_manifest(names) -> {name: VesperTool}   # ToolNotFoundError if missing

def load_entrypoint_tools(file_path) -> [VesperTool]   # imports a .py, collects VesperTool instances
```
`TYPE_MAP`: `str→string, int→integer, float→number, bool→boolean` (default `string`).
Built-ins: `read_file(path)`, `web_search(query)` (keyless DuckDuckGo Instant Answer via `urllib`).
`BUILTIN_TOOLS = [read_file, web_search]`.

## 7. Memory — `memory.py`

```sql
CREATE TABLE memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT, scope_key TEXT, role TEXT, content TEXT,
    tokens INTEGER, created_at REAL
);
```
```python
MEMORY_TOKEN_CAP = 8000
estimate_tokens(text) = max(1, len(text)//4)

MemoryStore.load(agent_name, scope_key, retention_days) -> [messages]
   # DELETE rows older than retention cutoff (per agent+scope)
   # SELECT ordered oldest→newest; drop oldest until sum(tokens) <= CAP
MemoryStore.save(agent_name, scope_key, messages)   # append with estimated tokens
MemoryStore.delete(agent_name)                      # clear all memory for an agent
```
Only conversational turns (user input + final assistant text) are stored — tool turns stay ephemeral.

## 8. Audit — `audit.py`

```python
class RunRecord(BaseModel):
    run_id, agent_name, session_id?, input, output?, cost?,
    prompt_tokens, completion_tokens, status, created_at
```
```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY, agent_name TEXT, session_id TEXT,
    input TEXT, output TEXT, cost REAL,
    prompt_tokens INTEGER, completion_tokens INTEGER,
    status TEXT, created_at REAL
);
```
`AuditStore.record(RunRecord)`, `list(agent_name) -> [RunRecord]` (newest first), `delete(agent_name)`.

## 9. Runtime — `runtime.py`

```python
class RunResult(BaseModel):
    content, cost?, prompt_tokens, completion_tokens, session_id?, alerted=False

class Agent:
    __init__(manifest, tools=None):
        provider = get_provider(manifest.model)
        registry = ToolRegistry(BUILTIN_TOOLS + (tools or []))
        memory_store = MemoryStore() if manifest.memory else None
        audit = AuditStore()

    from_manifest(file_path, tools=None)   # validate + _collect_tools
    load(name, tools=None)                 # get_registry().get_resource_config(name) + _collect_tools
    _collect_tools(manifest, tools)        # explicit tools + entryPoint tools
    runs() -> audit.list(manifest.name)
    _resolve_scope(session) -> (scope_key, session_id)
        # scope=="session" → (session or "sess_"+uuid, same)
        # else (project)   → ("project", None)
```

### 9.1 `run(input, session=None)` — control flow
```
1. active_tools = registry.filter_by_manifest(manifest.tools); schemas = [t.schema()] or None
2. max_cost, alert_at ← manifest.budget
3. if max_cost set and calculate_cost(model,0,0) is None:      # unpriced + budget
       raise BudgetExceededError("cannot enforce budget")
4. run_id = "run_"+uuid[:12]
5. scope_key, session_id ← _resolve_scope(session) if memory else (None, session)
6. history ← memory_store.load(...) if memory else []
7. messages = history + [user]
8. try:
     loop:
       resp = provider.generate(messages, schemas)
       prompt_tokens += resp.prompt_tokens; completion_tokens += resp.completion_tokens
       cost = calculate_cost(model, prompt_tokens, completion_tokens)
       if max_cost and cost > max_cost:
            raise BudgetExceededError(f"exceeded ${max_cost} (spent ${cost})")
       if not resp.tool_calls:
            memory_store.save(user, assistant)          # if memory
            audit.record(status="completed", output=resp.content, cost, tokens)
            return RunResult(content, cost, tokens, session_id,
                             alerted = alert_at and cost >= alert_at)
       append assistant tool-call turn
       for call: result = active_tools[call.name].execute(**call.arguments)
                 append {"role":"tool", tool_call_id, name, content=str(result)}
   except BudgetExceededError:
       audit.record(status="failed", output=None, cost=calculate_cost(model, tokens), tokens)
       raise
```
Cost accumulates across every hop; only LLM calls cost, tools are free. Budget breach is detected
post-hop (a hop's cost is unknown until it returns) and always reports actual spend.

## 10. Config — `config.py`

```python
get_vesper_home() -> expanduser(env VESPER_HOME or "~/.vesper")
load_env()        -> parse ./.env KEY=VALUE lines into os.environ (setdefault; real env wins)
```

## 11. CLI — `cli.py` (Typer)

Root callback runs `load_env()`. `get_registry()` wraps `registry.get_registry()`, mapping
`VesperError` → `typer.Exit`.

| Command | Core call |
|---|---|
| `init [--force] [--cloud]` | create `~/.vesper`, `config.json`, `registry.db` |
| `validate -f` | `registry.validate_manifest` |
| `apply -f` | `registry.apply_manifest` (handles `NoChangeDetectedError`) |
| `list` / `ls` | `registry.get_all_resources` |
| `history <name>` | `registry.get_history` |
| `show <name> [-v]` | `registry.get_resource_config` → JSON |
| `run <name> [-i/--input-file/-s/--max-cost]` | `Agent.load(name).run(...)`; prints content, alert, cost footer |
| `runs <name>` | `AuditStore().list(name)` → table |
| `delete <name> [-f] [-y]` | `registry.delete_resource` + `MemoryStore.delete` + `AuditStore.delete` |

`--max-cost` mutates `agent.manifest.budget.maxCostPerRun` before the run.

## 12. Dependency graph (import direction)

```
cli ─▶ runtime ─▶ registry ─▶ sqlite_storage ─▶ storage
 │        │           └────────▶ config              └▶ models
 │        ├─▶ factory ─▶ providers/* ─▶ base
 │        ├─▶ tools ◀── builtin_tools
 │        ├─▶ memory ─▶ config
 │        └─▶ audit  ─▶ config
 └─▶ memory, audit, models, config
```
No cycles. The SDK package `__init__` exposes `tool`, `Agent`, `RunResult`, `load`.

## 13. Extension points

- **New provider** — subclass `BaseProvider`, implement `generate` + translations, add a prefix branch
  in `get_provider`, add pricing rows.
- **New built-in tool** — add a `@tool` function to `builtin_tools.BUILTIN_TOOLS`.
- **New backend** — implement `VesperDatabase`; wire it in `get_registry` by `backend` type.
- **v2 engines** — introduce `apiVersion: vesper/v2`, re-add `AgentFleetManifest`/eval/guardrail
  schema, and extend the runtime; v1 manifests remain valid.
