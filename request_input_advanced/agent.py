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

from typing import Optional

# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from pydantic import Field
# pyrefly: ignore [missing-import]
from google.adk.workflow import node
# pyrefly: ignore [missing-import]
from google.genai import Client
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
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


class TimeOffRequest(BaseModel):
  days: int = Field(description="Number of days requested.")
  reason: str = Field(description="Reason for the time off.")


class TimeOffDecision(BaseModel):
  """The structured response we expect back from the human manager."""

  approved: bool = Field(description="Whether the time off is approved.")
  approved_days: Optional[int] = Field(
      default=None, description="Number of days approved."
  )


process_request = Agent(
    name="process_request",
    instruction=(
        "Extract the number of days and the reason from the user's natural"
        " language time off request."
    ),
    output_schema=TimeOffRequest,
    output_key="request",
)


def evaluate_request(request: TimeOffRequest):
  """
  If days <= 1, it's auto-approved. Otherwise, routes to manager review.
  """
  if request.days <= 1:
    return TimeOffDecision(approved=True)
  else:
    return RequestInput(
        interrupt_id="manager_approval",
        message="Please review this time off request.",
        payload=request,
        response_schema=TimeOffDecision,
    )


def process_decision(request: TimeOffRequest, node_input: TimeOffDecision):
  if node_input.approved:
    approved_days = (
        node_input.approved_days
        if node_input.approved_days is not None
        else request.days
    )
    message = (
        f"Time Off Approved! {approved_days} out of {request.days} days"
        " granted."
    )
  else:
    message = "Time Off Denied."

  yield Event(message=message)



'''

root_agent = Workflow(
    name="request_input_advanced",
    edges=[
        ("START", process_request, evaluate_request, process_decision),
    ],
)

'''



root_agent = Workflow(
    name="request_input_advanced",
    edges=[
        ("START", validate_api_key),
        (validate_api_key, {"success": process_request}),
        (process_request, evaluate_request),
        (evaluate_request, process_decision),
    ],
)