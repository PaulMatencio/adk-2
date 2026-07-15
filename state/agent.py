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
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from pydantic import Field

class output_data(BaseModel):
  original: str = Field(description="original input")
  uppercased: str = Field(description="uppercased input")
  appended: str = Field(description="appended input")
  final: str= Field(description="final result")
  reverse: str| None = Field(default=None, description="reversal of final field")

def process_initial_input(ctx, node_input: str):
  """Takes initial input and sets it in state via direct dict modification."""
  ctx.state["original_text"] = node_input
  return node_input



def update_state_via_event(node_input: str):
  """Returns an Event that implicitly updates the shared workflow state."""
  yield Event(state={"uppercased_text": node_input.upper()})


def read_state_via_ctx(ctx):
  """Reads a state variable via direct dictionary access and appends to it."""
  original = ctx.state["original_text"]
  uppercased = ctx.state["uppercased_text"]
  result = f"{uppercased} (Original was: {original})"
  ctx.state["appended_text"] = result
  return result


def read_state_via_param(ctx, appended_text: str):
  """Reads a state variable via automatic parameter injection."""
  result = f"Final Result: {appended_text}!"
  ctx.state["final_text"] = result
  out = output_data(
    original = ctx.state["original_text"],
    uppercased = ctx.state["uppercased_text"],
    appended = ctx.state["appended_text"],
    final = result
  )
  yield Event(output=out,output_schema=output_data,)
 

def read_state_via_output_model(ctx,node_input: output_data):
  """Reads a data model from previous node's output"""  
  if isinstance(node_input,dict): 
    out = output_data( 
      original = node_input.original,
      uppercased = node_input.uppercased,
      appended = node_input.appended,
      final = node_input.final,
      reverse = node_input.final[::-1]
    )  
  else:
    out = output_data(
      original = ctx.state["original_text"],
      uppercased = ctx.state["uppercased_text"],
      appended = ctx.state["appended_text"],
      final = ctx.state["final_text"],
      reverse = ctx.state["final_text"][::-1]
    )
  yield Event(output=out)


root_agent = Workflow(
    name="state_sample",
    edges=[
        (
            "START",
            process_initial_input,
            update_state_via_event,
            read_state_via_ctx,
            read_state_via_param,
            read_state_via_output_model,
        ),
    ],
)