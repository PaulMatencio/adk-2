# ADK Message Types & Streaming Demonstration Agent

This project demonstrates the diverse message rendering and streaming capabilities of the **Google Antigravity SDK (ADK)**. It showcases how to send text messages, bundle multimodal data (text and inline images), yield multiple sequential updates from a single node, and stream text in real time to the Web UI.

---

## 🏗️ Workflow Architecture

The workflow transitions from `send_string` to a parallel execution layer containing `send_multimodal` and `multiple_messages`. Because there is no `JoinNode` barrier, both concurrent branches transition to and trigger the final `stream_sentence` node independently.

```mermaid
graph TD
    START([START]) --> send_string[send_string]
    
    subgraph Parallel Branches (No Join Barrier)
        send_string --> send_multimodal[send_multimodal]
        send_string --> multiple_messages[multiple_messages]
    end
    
    send_multimodal --> stream_sentence[stream_sentence]
    multiple_messages --> stream_sentence
```

### Nodes Definition

1. **`send_string`**:
   - Sends a basic, markdown-formatted text response using `yield Event(message="...")`.
2. **`send_multimodal`**:
   - Bundles different media formats in a single message.
   - Decodes a base64-encoded red square PNG and attaches it alongside a description using `types.Part`.
3. **`multiple_messages`**:
   - Demonstrates a generator node yielding multiple distinct complete messages with artificial sleep delays to simulate a long-running backend task.
4. **`stream_sentence`**:
   - Demonstrates real-time message streaming. It yields a sentence (including a markdown table) in small text chunks with `partial=True`.

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
.venv/bin/adk run message
```

### 🌐 Running the Web UI
To interact with the agent through the visual developer interface:
```bash
.venv/bin/adk web message --port 8080
```
Then open your web browser and navigate to:
👉 **[http://localhost:8080](http://localhost:8080)**

---

## 💡 Core Principles & Best Practices

### 1. Simple Text Messages
In ADK, returning or yielding an event with a string automatically formats it as markdown in the Web UI:
```python
yield Event(message="# Heading\nThis is a *markdown* message.")
```

### 2. Mixed Multimodal Messages
To send inline images or attachments, populate the `message` parameter of the `Event` with a list of `types.Part` objects:
```python
yield Event(
    message=[
        types.Part.from_text(text="Here is the image:"),
        types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
    ]
)
```

### 3. Multiple Status Updates
If a node performs a long operation, it can continuously report progress by yielding multiple full events:
```python
yield Event(message="Starting task...")
# ... perform work ...
yield Event(message="Step 1 complete...")
# ... perform work ...
yield Event(message="All done!")
```
Each standard `yield Event(...)` creates a new chat bubble in the Web UI.

### 4. Real-time Chunked Streaming (`partial=True`)
To stream text word-by-word or character-by-character into a single continuous bubble, use the `partial=True` flag:
```python
for chunk in text_chunks:
    yield Event(message=chunk, partial=True)
```
- **Why it matters**: Without `partial=True`, every individual chunk would render as a separate, distinct message bubble, cluttering the chat history.
- **The UI Behavior**: The Web UI aggregates consecutive partial events into a single flowing bubble until the node finishes executing or yields a non-partial event.

### 5. Parallel Execution without Barriers
When a node transitions to a tuple of target nodes `(node_b, node_c)` and those nodes transition to a single successor `node_d` *without* a `JoinNode` barrier:
```python
edges=[
    (node_a, (node_b, node_c), node_d)
]
```
- The successor `node_d` is registered as a target for both `node_b` and `node_c`.
- Since there is no join barrier, `node_d` will be scheduled and executed **twice** (once when `node_b` completes, and once when `node_c` completes).
- If you only want `node_d` to execute once with the combined inputs, you must use a `JoinNode`.
