# ADK Core Demo Agent Workflows

This workspace contains various demonstration workflows built with the **Google Antigravity SDK (ADK)**. These projects showcase design patterns for implementing caching, dynamic loops, human-in-the-loop validation, parallel execution, task retrying, routing, and sequential processing.

---

## 🚀 How to Run the Agents

All workflows are executed from the root of the `adk-2/` directory.

### 1. Activate the Virtual Environment
Before running any commands, activate the preconfigured Python virtual environment:
```bash
source .venv/bin/activate
```

### 2. Run in CLI Mode
To execute any agent interactively inside your terminal shell:
```bash
adk run <agent_name>
```
*Example (Human-in-the-Loop review)*:
```bash
adk run request_input
```

### 3. Run in Web UI Mode
To inspect execution logs, visualize the node graph, and interact with the agent through a local developer web page:
```bash
adk web <agent_name> --port 8080
```
*Example (Task Retry graph)*:
```bash
adk web retry --port 8080
```
After starting the server, open your web browser and navigate to:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 🏗️ Available Workflows

| Agent Name (`<agent_name>`) | Description | Core Feature Highlight |
| :--- | :--- | :--- |
| **`auth_api_key`** | Weather forecast loop with API key validation. | Credential caching and 401 recovery loops. |
| **`dynamic-nodes`** | Generates node instances dynamically based on runtime parameters. | Dynamically-constructed execution graphs. |
| **`fan_out_fan_in`** | Parallel processing with barrier synchronization. | Multi-branch execution merged via a `JoinNode`. |
| **`loop`** | Continuous processing loop for generating news headlines. | Graph-level cycle logic. |
| **`loop_self`** | Cyclic guess validation loop until a match is found. | Iterative feedback loops. |
| **`message`** | Text, multimodal image, multi-message sequence, and streaming layouts. | Rich output events and markdown streaming (`partial=True`). |
| **`multi_triggers`** | Fans out START trigger to multiple parallel functions. | Single event fanning out to parallel functions. |
| **`nested_workflow`** | Runs a sub-workflow as a single node in a parent workflow. | Reusable sub-workflow nesting. |
| **`node_output`** | Demonstrates simple returns, Event wrappers, and Pydantic outputs. | Node output formats and Pydantic auto-coercion. |
| **`parallel_worker`** | Maps a node across elements of a list in parallel. | Map-reduce list processing using `parallel_worker=True`. |
| **`request_input`** | Dual-branch HITL manager email review & validation. | Interactive forms, classifier routing, and manual review loops. |
| **`request_input_advanced`** | Time-off approval system with conditional manager interrupt. | Conditional Human-in-the-Loop decision pausing. |
| **`retry`** | Flaky task simulation with automatic exponential backoff. | `RetryConfig` task retry wrapper. |
| **`route`** | Multi-path destination routing based on LLM classification. | Category literal routing mapping. |
| **`sequence`** | Sequential step flow with dynamic value resolution. | Pre-agent branch value resolution. |
| **`state`** | Demonstrates direct, implicit, and parameter injection state patterns. | Key-to-parameter injection and shared dict state management. |

---

## 🛠️ Implementation Details & Design Patterns

### 1. State Object Persistence
The ADK `State` wrapper object does not implement standard dictionary `.pop()` methods. Key clearing must be done directly via assignment:
```python
# Correct way to clear state keys in ADK
ctx.state["weather_api_key"] = None
```

### 2. Event Role Alternation (Web UI Integration)
All events yielded by nodes representing agent/model responses must have their role explicitly set to `"model"`:
```python
yield Event(
    content=types.Content(
        role="model",
        parts=[types.Part.from_text(text="Model response text")]
    )
)
```
If an event is created using only the `message="..."` convenience argument, the underlying SDK serialization defaults the role to `"user"`. Consecutive user-role messages confuse the alternating turn-taking logic of the browser Web UI and cause it to lock up. Using explicit `"model"` roles solves this issue.

### 3. Dynamic Interrupt IDs (Web UI Loop Prevention)
When building loops that repeatedly prompt the user inside a workflow (for example, re-requesting an API key upon validation failure or prompting for locations in a continuous lookup loop), **never reuse static interrupt IDs** (like `"weather_api_key"` or `"location_input"`).
- **The Issue**: The ADK Web UI tracks replies mapped to prompt IDs in session history. If the backend yields a new `RequestInput` using a previously resolved ID, the frontend UI client interprets it as a historical replay rather than a new prompt.
- **The Solution**: Generate a unique, state-based dynamic ID for each prompt turn by tracking a counter in `ctx.state` and clearing the active prompt ID upon receiving user input:
  ```python
  interrupt_id = ctx.state.get("location_interrupt_id")
  if not interrupt_id:
      counter = ctx.state.get("location_counter", 0) + 1
      ctx.state["location_counter"] = counter
      interrupt_id = f"location_input_{counter}"
      ctx.state["location_interrupt_id"] = interrupt_id
  
  choice = ctx.resume_inputs.get(interrupt_id)
  if choice is None:
      yield RequestInput(interrupt_id=interrupt_id, message="...")
      return
  
  ctx.state["location_interrupt_id"] = None  # Clear for next iteration
  ```

### 4. Replay State Isolation
When a workflow loops over the same node multiple times (e.g. asking for inputs in a cyclic loop), ADK replays execution from `START` upon resumption.
- **The Problem**: If a node reads loop-global state keys (like `location_counter` or `location_interrupt_id` without context), replayed runs (e.g. execution index 1 of the node) will see the mutated values from the end of later iterations. This causes the replayed node to attempt validation of incorrect input IDs, leading to "Replay divergence detected" errors or UI freezes.
- **The Solution**: Always isolate loop-scoped state keys and counters by appending `ctx.node_path` (which includes the node execution index) to the key name:
  ```python
  # Isolate counters, interrupts, and location state per loop iteration
  counter_key = f"location_counter_{ctx.node_path}"
  interrupt_id_key = f"location_interrupt_id_{ctx.node_path}"
  location_state_key = f"location_{ctx.node_path}"
  ```
  This ensures that when the runner replays the session, each execution index only reads and writes state keys scoped to its specific iteration, keeping the execution path perfectly stable.

GIT_SSH_COMMAND="ssh -i ~/.ssh/id_ed25519_personal -o IdentitiesOnly=yes" git push -u origin main --force
