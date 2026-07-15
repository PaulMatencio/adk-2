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

"""Auth API Key sample: FunctionNode with API key authentication.

Demonstrates how to use `auth_config` on a FunctionNode to pause
the workflow and request user credentials before running the node.

Flow:
  1. User sends any message to start the workflow.
  2. The `fetch_weather` node pauses and requests an API key.
  3. The user provides the API key through the auth UI.
  4. The node runs with the credential available in session state.
  5. The `summarize` node displays the result.
"""
"""
   To start the web UI and test this agent:
  
   adk web auth_api_key --port 8080
   or adk web auth_api_key --port 8080
 
   To stop the web UI: 
   ctrl + c
   Open the following URL in your browser:
   http://localhost:8080

   e.g. 
   To provide the API key:
   Enter the location e.g. "London" in the chat box to start the workflow.
   The `fetch_weather` node will pause and request an API key.
   Provide the API key in the auth UI.
   The node will run with the credential available in session state.
   The `summarize` node will display the result.
"""

# pyrefly: ignore [missing-import]
from typing import Any
import requests
import json

# pyrefly: ignore [missing-import]
from google.adk.workflow import RetryConfig

# pyrefly: ignore [missing-import]
from fastapi.openapi.models import APIKey
# pyrefly: ignore [missing-import]
from fastapi.openapi.models import APIKeyIn
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_credential import AuthCredential
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_credential import AuthCredentialTypes
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_tool import AuthConfig
# pyrefly: ignore [missing-import]
from google.adk.workflow import node

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

# --- Auth configuration ---
# Uses API key auth: the simplest credential type.
# The user will be prompted to provide an API key via the auth UI.
auth_config = AuthConfig(
    auth_scheme=APIKey(**{'in': APIKeyIn.header, 'name': 'X-Api-Key'}),
    raw_auth_credential=AuthCredential(
        auth_type=AuthCredentialTypes.API_KEY,
        api_key='placeholder',
    ),
    credential_key='weather_api_key',
)





@node(rerun_on_resume=True)
def validate_api_key(ctx: Context, node_input: Any):
    """Prompts for the OpenWeather API Key and checks its validity."""
    print("🛠️ TOOL CALLED: validate_api_key")
    
    api_key = ctx.state.get("weather_api_key")
    if api_key is None:
        interrupt_id = ctx.state.get("weather_api_key_interrupt_id")
        if not interrupt_id:
            counter = ctx.state.get("weather_api_key_counter", 0) + 1
            ctx.state["weather_api_key_counter"] = counter
            interrupt_id = f"weather_api_key_{counter}"
            ctx.state["weather_api_key_interrupt_id"] = interrupt_id

        choice = ctx.resume_inputs.get(interrupt_id)
        if choice is None:
            yield RequestInput(
                interrupt_id=interrupt_id,
                message="Please enter your Weather API Key (or type 'exit' to quit):",
            )
            return
        
        ctx.state["weather_api_key_interrupt_id"] = None
        
        choice_str = str(choice).strip()
        if choice_str.lower() in ["exit", "quit", "q"]:
            yield model_event(
                "Goodbye!",
                route="exit",
            )
            return
            
        api_key = choice_str
        print(f"🔑 Validating API Key: {api_key[:4]}...")
        
        # Test key validity using OpenWeather API with a dummy location (London)
        try:
            if api_key == "test_valid_key":
                # Mock successful validation response
                pass
            else:
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": "London",
                    "appid": api_key
                }
                response = requests.get(url, params=params)
                if response.status_code == 401:
                    yield model_event("Error: Invalid API key. Please re-enter.")
                    counter = ctx.state.get("weather_api_key_counter", 0) + 1
                    ctx.state["weather_api_key_counter"] = counter
                    next_id = f"weather_api_key_{counter}"
                    ctx.state["weather_api_key_interrupt_id"] = next_id
                    yield RequestInput(
                        interrupt_id=next_id,
                        message="Please enter a valid Weather API Key (or type 'exit' to quit):",
                    )
                    return
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            yield model_event(f"Network error during key validation: {e}")
            counter = ctx.state.get("weather_api_key_counter", 0) + 1
            ctx.state["weather_api_key_counter"] = counter
            next_id = f"weather_api_key_{counter}"
            ctx.state["weather_api_key_interrupt_id"] = next_id
            yield RequestInput(
                interrupt_id=next_id,
                message="Please enter your Weather API Key (or type 'exit' to quit):",
            )
            return
            
        ctx.state["weather_api_key"] = api_key
        print("🔑 API Key is valid, saving to state.")
    
    ctx.route = "success"



@node(rerun_on_resume=True,retry_config=RetryConfig(max_attempts=3, initial_delay=1))
def ask_location_forecast(ctx: Context, node_input: Any):
    """Prompts for location and retrieves the weather forecast."""
    print("🛠️ TOOL CALLED: ask_location_forecast")
    
    api_key = ctx.state.get("weather_api_key")
    if not api_key:
        # If API key is somehow missing, route back to validate
        ctx.route = "validate"
        return
        
    interrupt_id = ctx.state.get("location_interrupt_id")
    if not interrupt_id:
        counter = ctx.state.get("location_counter", 0) + 1
        ctx.state["location_counter"] = counter
        interrupt_id = f"location_input_{counter}"
        ctx.state["location_interrupt_id"] = interrupt_id
        
    choice = ctx.resume_inputs.get(interrupt_id)
    if choice is None:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message="Please enter a location to check weather (or type 'exit' to quit):",
        )
        return
        
    ctx.state["location_interrupt_id"] = None
    
    choice_str = str(choice).strip()
    if choice_str.lower() in ["exit", "quit", "q"]:
        yield model_event(
            "Goodbye!",
            route="exit",
        )
        return
        
    location = choice_str
    print(f"🌦️ Fetching weather for location: {location}")
    try:
        if api_key == "test_valid_key":
            detailed_forecast = f"Mock clear sky in {location} with temperature of 20°C."
            yield {
                "status": "success",
                "location": location,
                "temperature": "20°C",
                "feels_like": "20°C",
                "humidity": "50%",
                "wind_speed": "5 m/s",
                "forecast": detailed_forecast,
            }
        else:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": location,
                "units": "metric",
                "appid": api_key
            }
            response = requests.get(url, params=params)
            if response.status_code == 401:
                # The key became invalid or was revoked
                ctx.state["weather_api_key"] = None
                yield model_event("Error: Cached API key is now invalid. Redirecting to validation.")
                ctx.route = "validate"
                return
                
            if response.status_code == 404:
                yield {
                    "status": "error",
                    "message": f"Location '{location}' not found by OpenWeather."
                }
                ctx.route = "success"
                return
                
            response.raise_for_status()
            data = response.json()
            
            temp = data['main']['temp']
            feels_like = data['main']['feels_like']
            description = data['weather'][0]['description']
            humidity = data['main']['humidity']
            wind_speed = data['wind']['speed']
            
            detailed_forecast = f"{description.capitalize()} with a temperature of {temp}°C (feels like {feels_like}°C). Humidity is {humidity}% and wind speed is {wind_speed} m/s."
            
            yield {
                "status": "success",
                "location": location,
                "temperature": f"{temp}°C",
                "feels_like": f"{feels_like}°C",
                "humidity": f"{humidity}%",
                "wind_speed": f"{wind_speed} m/s",
                "forecast": detailed_forecast,
            }
    except requests.exceptions.RequestException as e:
        yield {
            "status": "error",
            "message": f"API request failed: {e}"
        }
        
    ctx.route = "success"


def summarize(node_input: dict):
  """Displays the weather result."""
  if node_input["status"] == "success":
    yield model_event(
        f"Weather for {node_input['location']}:"
        f" {node_input['temperature']}, {node_input['feels_like']}, {node_input['humidity']}, {node_input['wind_speed']}.)"
    )
  else:
    yield model_event(f"Error: {node_input['message']}")


root_agent = Workflow(
    name='auth_api_key',
    edges=[
        ('START', validate_api_key),
        (validate_api_key, {
            "success": ask_location_forecast,
        }),
        (ask_location_forecast, {
            "success": summarize,
            "validate": validate_api_key,
        }),
        (summarize, ask_location_forecast),
    ],
)