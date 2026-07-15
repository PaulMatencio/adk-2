# ADK Parallel Fan-Out/Fan-In Travel Planner Agent

This project demonstrates a parallel, looping workflow agent built with the **Google Antigravity SDK (ADK)**. It gathers travel prerequisites, validates them, and fans out to query the OpenWeather API and Google Search (via Gemini Grounding) in parallel before joining the results to summarize a travel overview.

---

## 🏗️ Workflow Architecture

The agent gathers all credentials and target locations sequentially inside `ask_inputs` to ensure that parallel tasks execute without interruptions. It then triggers parallel branches that merge at a `JoinNode` barrier.

```mermaid
graph TD
    START([START]) --> ValidateWeather[validate_api_key]
    ValidateWeather -- "success" --> AskInputs[ask_inputs]
    
    subgraph Parallel Branches (Fan-Out)
        AskInputs -- "success" --> AskForecast[ask_location_forecast]
        AskInputs -- "success" --> AskHotel[ask_hotel]
        AskInputs -- "success" --> AskRestaurant[ask_restaurant]
    end
    
    AskForecast --> JoinNode[join_node JoinNode]
    AskHotel --> JoinNode
    AskRestaurant --> JoinNode
    
    JoinNode --> Aggregate[aggregate]
    
    Aggregate --> AskInputs
```

### Nodes Definition
1. **`validate_api_key`**: Validates the OpenWeather API key.
2. **`ask_inputs`**: A consolidated node that:
   - Validates the Weather API key (if missing).
   - Prompts for and validates the Gemini API key (if missing).
   - Prompts for the destination city (cleared on every loop iteration).
3. **`ask_location_forecast`**: Fetches the destination city's current weather using the OpenWeather API.
4. **`ask_hotel`**: Uses the Gemini API with **Google Search Grounding** to search for the top 3 affordable hotels in the city.
5. **`ask_restaurant`**: Uses the Gemini API with **Google Search Grounding** to search for the top 3 good restaurants in the city.
6. **`join_node`**: Joins the outputs of the three parallel nodes into a single merged dictionary.
7. **`aggregate`**: Formats the final readout displaying the weather, hotels, and restaurants, and clears the location state to allow another prompt.

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
.venv/bin/adk run fan_out_fan_in
```

### 🌐 Running the Web UI
To interact with the agent through the visual developer interface:
```bash
.venv/bin/adk web fan_out_fan_in --port 8080
```
Then open your web browser and navigate to:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 💡 Core Principles & Best Practices

### 1. Parallel Branching and Join Barriers
To launch parallel processes, specify a tuple of target nodes in the edge dictionary routing keys:
```python
(ask_inputs, {
    "success": (ask_location_forecast, ask_hotel, ask_restaurant),
})
```
All parallel paths must target a `JoinNode` instance. The `JoinNode` blocks execution until all branches complete, merging their outputs into a single payload keyed by node names:
```python
join_node = JoinNode(name="join_for_results")
# Edges targeting join_node
(ask_location_forecast, join_node),
(ask_hotel, join_node),
(ask_restaurant, join_node),
```

### 2. Preventing Replay Divergence and Deadlocks
ADK uses a chronological `ReplaySequenceBarrier` to ensure deterministic execution orders during session replays (resumptions).
* **Parallel Interrupt Deadlock**: If nodes inside parallel branches yield a `RequestInput` (suspend), they interrupt execution. Since branches are concurrent, the sequence in which they complete or interrupt can vary, creating duplicate sequence keys in the database and causing deadlock timeouts on sequence barriers during replay.
* **The Solution**: Consolidate all user inputs and credential prompts (`RequestInput`) into a **sequential pre-step node** (`ask_inputs`). By the time the graph fans out, all inputs are already in state. Parallel tasks can run straight to completion without suspending, avoiding replay deadlocks.

### 3. Context-Isolated State Keys (Infinite Loop Stability)
When a workflow runs in a loop, it replays previous steps from `START` on every resume to rebuild the execution context.
* **The Problem**: If a looping node (like `ask_inputs`) uses static key names in `ctx.state` (such as `location_counter`), the replayed steps (e.g., `ask_inputs@1`) will read the latest mutated value from the end of the loop, prompting for incorrect input IDs and causing replay path divergence.
* **The Solution**: Suffixed keys are generated dynamically using `ctx.node_path` (e.g., `location_{ctx.node_path}`). This isolates the counter, interrupt IDs, and inputs of each iteration (e.g., `ask_inputs@1` vs `ask_inputs@2`), ensuring stable replays and robust looping.

### 4. API Key Persistence and Environment Variable Syncing
To prevent prompting the user for credentials (OpenWeather and Gemini keys) on every run:
* **Storage**: Valid keys are saved in `os.environ`, the local `.env` file, and `.venv/bin/activate`.
* **Reuse**: In `ask_inputs`, these files are checked first, and cached keys are reused as long as they are valid.
* **Automatic Invalidation**: If downstream api calls (like weather retrieval or Gemini search) encounter `401 Unauthorized` or authentication failures, the keys are automatically deleted from `ctx.state`, `os.environ`, `.env`, and `.venv/bin/activate`, triggering a fresh prompt on the next run.

### 5. Google Search Grounding with Gemini
To obtain real-time internet data (like active hotel listings or dining options), configure your GenAI SDK client tool options with the `GoogleSearch` tool:
```python
client = Client(api_key=gemini_api_key)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Search for hotels in {location}",
    config=types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
)
```
