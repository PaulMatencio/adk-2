# ADK Nested Workflow & Parallel Fan-Out/Fan-In Agent

This project demonstrates a multi-stage workflow agent built with the **Google Antigravity SDK (ADK)**. It showcases how to nest a sub-workflow as a single node in a parent workflow, execute parallel fan-out branches (a sub-workflow and an agent running concurrently), and merge their results via a `JoinNode`.

---

## 🏗️ Workflow Architecture

The parent workflow (`root_agent`) validates credentials and inputs sequentially before fanning out into parallel branches that merge at a `JoinNode` barrier.

```mermaid
graph TD
    START([START]) --> ValidateKey[validate_api_key]
    ValidateKey -- "success" --> ProcessInput[process_input]
    ValidateKey -- "exit" --> END([Goodbye / Exit])
    
    subgraph Parallel Branches (Fan-Out)
        ProcessInput --> find_famous_person[find_famous_person Sub-Workflow]
        ProcessInput --> find_historical_event[find_historical_event Agent]
    end
    
    subgraph find_famous_person sub-workflow
        SubStart([START]) --> find_name[find_name Agent]
        find_name --> generate_bio[generate_bio Agent]
    end
    
    find_famous_person --> join_for_aggregation[join_for_aggregation JoinNode]
    find_historical_event --> join_for_aggregation
    
    join_for_aggregation --> aggregate_results[aggregate_results]
```

### Nodes Definition

1. **`validate_api_key`**:
   - Interactively prompts for and validates the Gemini API key using the `google-genai` SDK.
   - Automatically handles validation errors and generates dynamic interrupt IDs to support UI execution.
2. **`process_input`**:
   - Prompts the user for a valid 4-digit year (e.g., `1955`).
   - Uses regex validation to ensure the input year is format-compliant before storing it in `ctx.state["year"]`.
3. **`find_famous_person` (Nested Workflow)**:
   - A sub-workflow comprising two agents:
     - **`find_name` Agent**: Resolves the name of one famous person born in the specified `{year}`.
     - **`generate_bio` Agent**: Writes a short, 3-sentence biography of the identified person.
4. **`find_historical_event` (Agent)**:
   - Prompts Gemini to describe one highly significant historical event that occurred in the specified `{year}` in 2 sentences.
5. **`join_for_aggregation` (JoinNode)**:
   - Synchronizes the concurrent execution branches (`find_famous_person` sub-workflow and `find_historical_event` agent) and aggregates their outputs.
6. **`aggregate_results`**:
   - Combines the structured output dictionary from the `JoinNode`, formats a markdown summary containing the person's biography and historical event, and resets temporary state.

---

## 🚀 Getting Started

### 📋 Prerequisites
Ensure your virtual environment is active and all dependencies are installed:
```bash
source .venv/bin/activate
```

### 💻 Running the CLI Agent
To run the workflow interactively directly inside the terminal:
```bash
.venv/bin/adk run nested_workflow
```

### 🌐 Running the Web UI
To interact with the agent through the visual developer interface:
```bash
.venv/bin/adk web nested_workflow --port 8080
```
Then open your web browser and navigate to:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 💡 Core Principles & Best Practices

### 1. Nested Sub-Workflows as Nodes
In ADK, workflows are fully composable. A `Workflow` instance can be registered as an entry in the parent workflow's edges just like a regular node or agent:
```python
find_famous_person = Workflow(
    name="find_famous_person",
    edges=[("START", find_name, generate_bio)],
)
```
When executed as part of the parent graph:
- It initiates its execution at its internal `"START"`.
- It processes its inner nodes sequentially.
- The output of the final node in the sub-workflow (`generate_bio`) is returned to the parent workflow as the sub-workflow's output, keyed under the name of the sub-workflow (`"find_famous_person"`).

### 2. Parallel Fan-Out/Fan-In with Workflows
To trigger concurrent execution branches, define a tuple of target workflows/nodes in your edge routing definition:
```python
(process_input, (find_famous_person, find_historical_event))
```
Use a `JoinNode` to collect the outputs of all parallel branches. The resulting payload passed to the downstream aggregation node is a dictionary indexed by the branch names:
```python
def aggregate_results(ctx: Context, node_input: dict[str, str], year: str):
    # node_input contains:
    # {
    #   "find_famous_person": "Biography output...",
    #   "find_historical_event": "Historical event output..."
    # }
```

### 3. Rerun-on-Resume (`@node(rerun_on_resume=True)`)
Nodes that prompt the user for input (`RequestInput`) suspend the workflow execution. Decorating these functions with `@node(rerun_on_resume=True)` is critical. It guarantees that when the workflow resumes, the node is re-evaluated with the newly submitted `resume_inputs`, ensuring that values are successfully validated and written to `ctx.state`.

### 4. Dynamic Interrupt IDs
To prevent the ADK Web UI from locking up during repeated prompts, always track a counter in `ctx.state` and generate unique interrupt IDs (e.g. `year_{counter}`). Reusing static interrupt IDs causes the web client to treat new inputs as historical replays and halts input submittal.
