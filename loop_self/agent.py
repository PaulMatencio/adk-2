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


import random
import os

# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.workflow import node, Edge
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from google.genai import types

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
def get_max_min_number(ctx: Context):
  min_number = ctx.state.get('min_number')
  max_number = ctx.state.get('max_number')

  # Step 1: Ask for min_number if not already set and valid in context state
  if min_number is None:
    interrupt_id = ctx.state.get("min_number_interrupt_id")
    if not interrupt_id:
      counter = ctx.state.get("min_number_counter", 0) + 1
      ctx.state["min_number_counter"] = counter
      interrupt_id = f"min_number_{counter}"
      ctx.state["min_number_interrupt_id"] = interrupt_id

    choice = ctx.resume_inputs.get(interrupt_id)
    if choice is None:
      yield RequestInput(
          interrupt_id=interrupt_id,
          message="Please enter your min number (or type 'exit' to quit):",
      )
      return

    ctx.state["min_number_interrupt_id"] = None
    choice_str = str(choice).strip()
    if choice_str.lower() in ["exit", "quit", "q"]:
      #yield Event(message="Goodbye!")
      yield model_event(
          "Goodbye!",
          route="exit",
      )
      return

    try:
      min_number = int(choice_str)
      ctx.state['keep_min_number'] = min_number
      ctx.state['min_number'] = min_number
    except ValueError:
      yield Event(message="Invalid input. Please enter a valid integer for min number.")
      # Generate new interrupt ID to loop and prompt again
      counter = ctx.state.get("min_number_counter", 0) + 1
      ctx.state["min_number_counter"] = counter
      next_id = f"min_number_{counter}"
      ctx.state["min_number_interrupt_id"] = next_id
      yield RequestInput(
          interrupt_id=next_id,
          message="Please enter your min number (or type 'exit' to quit):",
      )
      return

  # Step 2: Ask for max_number if not already set and valid in context state
  if max_number is None:
    interrupt_id = ctx.state.get("max_number_interrupt_id")
    if not interrupt_id:
      counter = ctx.state.get("max_number_counter", 0) + 1
      ctx.state["max_number_counter"] = counter
      interrupt_id = f"max_number_{counter}"
      ctx.state["max_number_interrupt_id"] = interrupt_id

    choice = ctx.resume_inputs.get(interrupt_id)
    if choice is None:
      yield RequestInput(
          interrupt_id=interrupt_id,
          message="Please enter your max number (or type 'exit' to quit):",
      )
      return

    ctx.state["max_number_interrupt_id"] = None
    choice_str = str(choice).strip()
    if choice_str.lower() in ["exit", "quit", "q"]:
       yield model_event(
                "Goodbye!",
                route="exit",
            )
       return

    try:
      max_number = int(choice_str)
      if max_number <= min_number:
        yield Event(message=f"Please provide a valid max number greater than min number ({min_number}).")
        # Generate new interrupt ID to loop and prompt again for max_number
        counter = ctx.state.get("max_number_counter", 0) + 1
        ctx.state["max_number_counter"] = counter
        next_id = f"max_number_{counter}"
        ctx.state["max_number_interrupt_id"] = next_id
        yield RequestInput(
            interrupt_id=next_id,
            message="Please enter your max number (or type 'exit' to quit):",
        )
        return
      ctx.state['max_number'] = max_number
      ctx.state['keep_max_number'] = max_number
    except ValueError:
      yield Event(message="Invalid input. Please enter a valid integer for max number.")
      # Generate new interrupt ID to loop and prompt again
      counter = ctx.state.get("max_number_counter", 0) + 1
      ctx.state["max_number_counter"] = counter
      next_id = f"max_number_{counter}"
      ctx.state["max_number_interrupt_id"] = next_id
      yield RequestInput(
          interrupt_id=next_id,
          message="Please enter your max number (or type 'exit' to quit):",
      )
      return

 
  if (min_number >= max_number):
    yield model_event(
      f'min should be less than max.',
      route='failed',
    )
    return
  yield Event(state={'min_number': min_number, 'max_number': max_number},route="success")
  #ctx.route = "success"

# Step 3: Ask for the target guessing number
@node(rerun_on_resume=True)
def get_target_number(ctx: Context):
  max_number = ctx.state.get('max_number')
  min_number = ctx.state.get('min_number')
  target_number = ctx.state.get('target_number')
  if target_number == None:
    interrupt_id = ctx.state.get("target_number_interrupt_id")
    if not interrupt_id:
      counter = ctx.state.get("target_number_counter", 0) + 1
      ctx.state["target_number_counter"] = counter
      interrupt_id = f"target_number_{counter}"
      ctx.state["target_number_interrupt_id"] = interrupt_id

  choice = ctx.resume_inputs.get(interrupt_id)
  if choice is None:
    yield RequestInput(
        interrupt_id=interrupt_id,
        message=f"Please enter the target number to guess between {min_number} and {max_number} (or type 'exit' to quit):")
    return

  ctx.state["target_number_interrupt_id"] = None
  choice_str = str(choice).strip()

  if choice_str.lower() in ["exit", "quit", "q"]:
    yield model_event(
                "Goodbye!",
                route="exit",
            )
    return

  try:  
    parsed_number = int(choice_str)
    ctx.state['target_number'] = parsed_number
    #ctx.state['keep_target_number'] = parsed_number
    if parsed_number < min_number or parsed_number > max_number:
      yield Event(message=f"Please provide a valid target number between {min_number} and {max_number}.")
      counter = ctx.state.get("target_number_counter", 0) + 1
      ctx.state["target_number_counter"] = counter
      next_id = f"target_number_{counter}"
      ctx.state["target_number_interrupt_id"] = next_id
      yield RequestInput(
          interrupt_id=next_id,
          message=f"Please enter the target number to guess between {min_number} and {max_number} (or type 'exit' to quit):",route="failed")
      ctx.state["target_number"] = None
      return
    
    #yield Event(state={'target_number': parsed_number}, output=parsed_number)
    yield Event(message=f"Target number set to {parsed_number}.",route="success")
    #ctx.route = "success"
    return
  except ValueError:
    yield Event(message="Invalid input. Please enter a valid integer for the target number.")
    counter = ctx.state.get("target_number_counter", 0) + 1
    ctx.state["target_number_counter"] = counter
    next_id = f"target_number_{counter}"
    ctx.state["target_number_interrupt_id"] = next_id
    yield RequestInput(
        interrupt_id=next_id,
        message=f"Please enter the target number to guess between {min_number} and {max_number} (or type 'exit' to quit):",route="failed"),
    return
  
@node(rerun_on_resume=True)
def guess_number(ctx: Context, target_number: int):
  max_number = ctx.state.get('max_number')
  min_number = ctx.state.get('min_number')
  guess = random.randint(min_number, max_number)
  yield Event(message=f'Guessing {guess}...')
  if guess == target_number:
    yield Event(message='Correct!', route='success')
    ctx.state['max_number'] = ctx.state['keep_max_number']
    ctx.state['min_number'] = ctx.state['keep_min_number'] 
    ctx.state['target_number'] = None
    return
  elif guess > target_number:
    #yield Event(route='guessed_wrong')
    yield Event(message='Too high!', route='Too high!')
    ctx.state['max_number'] = guess - 1
  else:
    yield Event(message='Too low!', route='Too low!')
    #yield Event(route='guessed_wrong')
    ctx.state['min_number'] = guess + 1

 # yield Event(route='guessed_wrong')


root_agent = Workflow(
    name='root_agent',
    edges=[
        ('START', get_max_min_number),
        (get_max_min_number, {'success': get_target_number}),
        Edge(from_node=get_max_min_number, to_node=get_max_min_number, route='failed'),
        (get_target_number, {'success':guess_number}),
        Edge(from_node=get_target_number, to_node=get_target_number, route='failed'),
        Edge(from_node=guess_number, to_node=guess_number, route=['Too high!', 'Too low!']),
        Edge(from_node=guess_number, to_node=get_target_number, route=['success']),
    ],
)