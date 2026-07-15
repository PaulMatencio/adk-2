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
from google.adk.workflow import node
from typing import Literal
import os
# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from pydantic import Field
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from google.genai import Client



def model_event(text: str, **kwargs) -> Event:
    """Helper to yield a model event with explicit model role."""
    return Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=text)]
        ),
        **kwargs
    )

def validate_api_key(ctx: Context):

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
        print("🔑 Gemini API Key is valid and loaded.")

class Feedback(BaseModel):
  grade: Literal["tech-related", "unrelated"] = Field(
      description=(
          "Decide if the headline is related to technology or software"
          " engineering."
      ),
  )
  feedback: str = Field(
      description=(
          "If the headline is unrelated to technology, provide feedback on how"
          " to make it more tech-focused."
      ),
  )


@node(rerun_on_resume=True)
def process_input(ctx: Context, node_input: str):
    # 1. Check if Gemini API Key is set in state or environment
    gemini_api_key = ctx.state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        for event in validate_api_key(ctx):
            yield event
        gemini_api_key = ctx.state.get("gemini_api_key")
        if not gemini_api_key:
            return
    else:
        # Make sure environment variable is synced with cached state key
        os.environ["GEMINI_API_KEY"] = gemini_api_key

  
    yield Event(state={"topic": node_input})
    ctx.route = "success"


generate_headline = Agent(
    name="generate_headline",
    instruction="""
    Write a headline about the topic "{topic}".
    If feedback is provided, take it into account.
    The feedback: {feedback?}
    """,
)


evaluate_headline = Agent(
    name="evaluate_headline",
    instruction="""
    Grade whether the headline is related to technology or software engineering.
    """,
    output_schema=Feedback,
    output_key="feedback",
)


def route_headline(node_input: Feedback):
  return Event(route=node_input.grade)


root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", process_input),
        (process_input, {
            "success": generate_headline,
        }),
        (generate_headline, evaluate_headline),
        (evaluate_headline, route_headline),
        (route_headline, {"unrelated": generate_headline}),
    ],
)