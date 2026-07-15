# ADK Parallel Workers (Map-Reduce) Agent

This project demonstrates the concurrent batch processing capabilities of the **Google Antigravity SDK (ADK)** using **Parallel Workers**. It showcases how to leverage the `parallel_worker` configuration to split lists, execute tasks concurrently (mapping), and collect results back into a single structured list (reducing) without manual loop orchestration.

---

## 🏗️ Workflow Architecture

The parent workflow (`root_agent`) takes a topic, generates a list of related sub-topics, processes those sub-topics concurrently in a parallel layer, and gathers the results for a final summary.

```mermaid
graph TD
    START([START]) --> ValidateKey[validate_api_key]
    ValidateKey -- "success" --> ProcessInput[process_input]
    ValidateKey -- "exit" --> END([Goodbye / Exit])
    
    ProcessInput --> FindRelated[find_related_topics Agent]
    
    subgraph Parallel Worker Layer (Mapping)
        FindRelated -->|Yields list| MakeUpper[make_upper_case Parallel Worker]
        MakeUpper -->|Runs in parallel per item| ExplainTopic[explain_topic Parallel Agent]
    end
    
    ExplainTopic -->|Gathers list of results| Aggregate[aggregate]
```

### Nodes & Models Definition

- **`TopicExplanation` (Pydantic Model)**:
  - Defines the schema for each processed sub-topic with fields: `topic` and `explanation`.
- **`validate_api_key`**:
  - Prompts for and validates the Gemini API key.
- **`process_input`**:
  - Saves the user's input topic in `ctx.state["topic"]`.
- **`find_related_topics` (Agent)**:
  - Prompts Gemini to generate a list of 3 related topics based on the input `{topic}` and outputs a `list[str]`.
- **`make_upper_case`**:
  - A function node decorated with `@node(parallel_worker=True)`. It converts each sub-topic to uppercase.
- **`explain_topic` (Agent)**:
  - An Agent configured with `parallel_worker=True` and `output_schema=TopicExplanation`. It runs concurrently for each uppercase sub-topic, explaining its relationship to the original topic.
- **`aggregate`**:
  - A standard function node that collects the gathered list of `TopicExplanation` items, joins them into a single markdown string, and outputs it.

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
.venv/bin/adk run parallel_worker
```

### 🌐 Running the Web UI
To interact with the agent through the visual developer interface:
```bash
.venv/bin/adk web parallel_worker --port 8080
```
Then open your web browser and navigate to:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 💡 Core Principles & Best Practices

### 1. What is a Parallel Worker (`parallel_worker=True`)?
In ADK, when a node is marked with `parallel_worker=True` (either via the `@node` decorator parameter or as an agent parameter):
- The framework expects the incoming data (`node_input`) to be a list. If it receives a single item, it automatically wraps it in a list.
- The framework loops through the list items and schedules a concurrent execution task (`ctx.run_node`) for each item in parallel.
- All parallel instances execute in their own isolated sub-branches, preventing them from writing overlapping outputs to the same session variables.

### 2. Automatic Reducing (Gathering)
You do not need to write custom collector code to merge parallel outputs.
- If a parallel worker node is followed by a **standard (non-worker) node**, the ADK framework automatically introduces a synchronization barrier.
- It awaits the completion of all concurrent tasks, bundles their individual outputs into a list (preserving the original index order), and passes the consolidated list directly as the `node_input` to the successor node:
```python
# The preceding node (explain_topic) is a parallel_worker.
# This node (aggregate) is a standard node, so it receives the gathered list.
def aggregate(node_input: list[TopicExplanation]):
    ...
```

### 3. Fail-Fast Concurrency Control
Under the hood, `_ParallelWorker` runs tasks using standard python `asyncio` routines.
- Concurrency can optionally be throttled using the `max_concurrency` attribute (default is unlimited).
- If any concurrent task raises an exception, the framework immediately cancels all other active tasks in the worker layer to prevent wasteful API usage, clean up resources, and propagate the error.

### 4. How to Configure Parallel Workers
Parallel workers can be declared in two ways:
1. **For Function Nodes**: Decorate the function with `@node(parallel_worker=True)`:
```python
@node(parallel_worker=True)
def make_upper_case(node_input: str):
    yield node_input.upper()
```
2. **For Agents**: Specify the `parallel_worker=True` keyword argument during Agent initialization:
```python
explain_topic = Agent(
    name="explain_topic",
    instruction="...",
    parallel_worker=True,
    output_schema=TopicExplanation,
)
```
