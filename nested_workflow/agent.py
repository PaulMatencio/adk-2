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

# NOT WORKING YET

from random import choice
from asyncio import transports
import re
import os
# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.workflow import JoinNode
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from google.genai import Client
# pyrefly: ignore [missing-import]
from google.adk.workflow import node, Edge

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

@node(rerun_on_resume=True)
def process_input(ctx: Context, node_input: str):
  """Validates the input is a valid 4-digit year."""
  year = ctx.state.get("year")
  if not year:
    match = re.search(r"\b\d{4}\b", node_input) if node_input else None
    if match:
      year = match.group(0)
      ctx.state["year"] = year
      yield Event(state={"year": year})
    else:
      interrupt_id = ctx.state.get("year_interrupt_id")
      if not interrupt_id:
        counter = ctx.state.get("year_counter", 0) + 1
        ctx.state["year_counter"] = counter
        interrupt_id = f"year_{counter}"
        ctx.state["year_interrupt_id"] = interrupt_id

      choice = ctx.resume_inputs.get(interrupt_id)
      if choice is None:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message="Please enter a valid 4-digit year (e.g., 1955):",
        )
        return

      ctx.state["year_interrupt_id"] = None
      choice_str = str(choice).strip()

      match_resumed = re.search(r"\b\d{4}\b", choice_str)
      if match_resumed:
        year = match_resumed.group(0)
        ctx.state["year"] = year
        yield Event(state={"year": year})
      else:
        yield Event(message="Invalid year format. Please provide a 4-digit year.")
        counter = ctx.state.get("year_counter", 0) + 1
        ctx.state["year_counter"] = counter
        next_id = f"year_{counter}"
        ctx.state["year_interrupt_id"] = next_id
        yield RequestInput(
            interrupt_id=next_id,
            message="Please enter a valid 4-digit year (e.g., 1955):",
        )
        return


find_name = Agent(
    name="find_name",
    instruction="""
    Find the name of one famous person who was born in this year: {year}.
    Return ONLY their name, nothing else.
    """,
)


generate_bio = Agent(
    name="generate_bio",
    instruction="""
    Write a short, engaging 3-sentence biography for the specified person.
    """,
)


# Sub-workflow that acts as a single node in the parent workflow
find_famous_person = Workflow(
    name="find_famous_person",
    edges=[("START", find_name, generate_bio)],
)


find_historical_event = Agent(
    name="find_historical_event",
    instruction="""
    Describe one highly significant historical event that occurred in this year: {year}.
    Keep the description to 2 sentences.
    """,
)

join_for_aggregation = JoinNode(name="join_for_aggregation")


def aggregate_results(ctx: Context, node_input: dict[str, str], year: str):
  """Combines outputs from parallel branches found in context state."""

  combined_message = (
      f"# Year: {year}\n\n"
      "## Famous Person Bio:\n\n"
      f"{node_input['find_famous_person']}\n\n"
      "## Historical Event:\n\n"
      f"{node_input['find_historical_event']}"
    
  )
  ctx.state['year'] = None
  ctx.state['find_famous_person'] = None
  ctx.state['find_historical_event'] = None
  yield Event(message=combined_message)

 
root_agent = Workflow(
    name="root_agent",
    edges=[
        (
            "START",
            validate_api_key,
            {"success": process_input},
            (find_famous_person, find_historical_event),
            join_for_aggregation,
            aggregate_results,
        )
    ],
)