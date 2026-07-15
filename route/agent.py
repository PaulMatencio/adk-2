# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pyrefly: ignore [missing-import]
from google.genai import Client

# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from typing import Literal
# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk.workflow import node
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from google.adk.agents import Context
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
import os

def model_event(text: str, **kwargs) -> Event:
    """Helper to yield a model event with explicit model role."""
    return Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)]
        ),
        **kwargs
    )

@node(rerun_on_resume=True)
def validate_api_key(ctx: Context, node_input: str):

    # 1. Check if Gemini API Key is set in state or environment
    gemini_api_key = ctx.state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    
    
    if not gemini_api_key:
        # Generate unique interrupt ID to avoid duplicate ID lockup in Web UI
        interrupt_id = ctx.state.get("gemini_api_key_interrupt_id")
        if not interrupt_id:
            counter = ctx.state.get("gemini_api_key_counter", 0) + 1
            ctx.state["gemini_api_key_counter"] = counter
            interrupt_id = f"gemini_api_key_{counter}"
            ctx.state["gemini_api_key_interrupt_id"] = interrupt_id
            
        choice = ctx.resume_inputs.get(interrupt_id)
        if choice is None:
            yield RequestInput(
                interrupt_id=interrupt_id,
                message="Please enter your Gemini API Key (or type 'exit' to quit):",
            )
            return
            
        ctx.state["gemini_api_key_interrupt_id"] = None
        
        choice_str = str(choice).strip()
        if choice_str.lower() in ["exit", "quit", "q"]:
            yield model_event("Goodbye!", route="exit")
            return
            
        gemini_api_key = choice_str
        print("🔑 Validating Gemini API Key...")
        
        # Validate key by making a dummy call to the models API
        try:
            client = Client(api_key=gemini_api_key)
            client.models.generate_content(
                model="gemini-2.5-flash",
                contents="test"
            )
        except Exception as e:
            yield model_event(f"Error: Invalid Gemini API key or connection error: {e}")
            counter = ctx.state.get("gemini_api_key_counter", 0) + 1
            ctx.state["gemini_api_key_counter"] = counter
            next_id = f"gemini_api_key_{counter}"
            ctx.state["gemini_api_key_interrupt_id"] = next_id
            yield RequestInput(
                interrupt_id=next_id,
                message="Please enter a valid Gemini API Key (or type 'exit' to quit):",
            )
            return
            
        # Key is valid, store it in state and environment
        ctx.state["gemini_api_key"] = gemini_api_key
        os.environ["GEMINI_API_KEY"] = gemini_api_key
        #print("🔑 Gemini API Key is valid and loaded.")
        yield Event(message="Gemini API Key is valid and loaded.", route="success", output=node_input)
        ctx.route = "success"
    else:
        # Key is already set in state/env, just pass through success
        yield Event(message="Gemini API Key is already loaded.", route="success", output=node_input)
        ctx.route = "success"


class InputCategory(BaseModel):
  category: Literal["question", "statement", "other"]
  language: str


def process_input(node_input: str):
  return Event(state={"input": node_input})


classify_input = Agent(
    name="classify_input",
    instruction=(
        "Based on this input, decide which category it belongs to: "
        "{input}"
    ),
    output_schema=InputCategory,
    output_key="category",
)


def route_on_category(category: InputCategory):
  """Yields an Event with a specific route based on the classification."""
  yield Event(route=category.category)


answer_question = Agent(
    name="answer_question",
    instruction="""Answer the question: {input}""",
)


comment_on_statement = Agent(
    name="comment_on_statement",
    instruction="""Comment on the statement: {input}""",
)


def handle_other():
  yield Event(
      message="Sorry I can only anwer questions or comment on statements."
  )


root_agent = Workflow(
    name="route",
    edges=[
        ("START", validate_api_key),
        (validate_api_key, {"success": process_input}),
        (process_input, classify_input),
        (classify_input, route_on_category),
        (
            route_on_category,
            {
                "question": answer_question,
                "statement": comment_on_statement,
                "other": handle_other,
            },
        ),
    ],
)