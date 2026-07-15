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

import os
from typing import Any
import requests

# pyrefly: ignore [missing-import]
from google.genai import Client
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.workflow import JoinNode
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_credential import AuthCredential
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_credential import AuthCredentialTypes
# pyrefly: ignore [missing-import]
from google.adk.auth.auth_tool import AuthConfig
# pyrefly: ignore [missing-import]
from fastapi.openapi.models import APIKey
# pyrefly: ignore [missing-import]
from fastapi.openapi.models import APIKeyIn
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
auth_config = AuthConfig(
    auth_scheme=APIKey(**{'in': APIKeyIn.header, 'name': 'X-Api-Key'}),
    raw_auth_credential=AuthCredential(
        auth_type=AuthCredentialTypes.API_KEY,
        api_key='placeholder',
    ),
    credential_key='weather_api_key',
)


def save_env_variable(name: str, value: str):
    """Saves an environment variable to os.environ, the project .env file, and .venv/bin/activate."""
    # 1. Update current process environment
    os.environ[name] = value
    
    # 2. Write to project .env file in the same directory as agent.py
    dir_path = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(dir_path, ".env")
    try:
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        new_lines = [l for l in lines if not l.strip().startswith(f"{name}=")]
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{name}={value}\n")
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"⚠️ Error saving to .env file: {e}")

    # 3. Write to .venv/bin/activate
    activate_path = None
    curr_dir = dir_path
    while True:
        possible_path = os.path.join(curr_dir, ".venv/bin/activate")
        if os.path.exists(possible_path):
            activate_path = possible_path
            break
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent

    if activate_path:
        try:
            with open(activate_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = [l for l in lines if not l.strip().startswith(f"export {name}=")]
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(f"export {name}='{value}'\n")
            with open(activate_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"🔑 Saved {name} to {activate_path}")
        except Exception as e:
            print(f"⚠️ Error saving to activate script: {e}")
    else:
        print("⚠️ Could not locate .venv/bin/activate to save env variable.")


def reset_env_variable(name: str):
    """Resets/removes an environment variable from os.environ, .env, and .venv/bin/activate."""
    # 1. Update current process environment
    if name in os.environ:
        del os.environ[name]

    # 2. Remove from project .env file
    dir_path = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(dir_path, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = [l for l in lines if not l.strip().startswith(f"{name}=")]
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"⚠️ Error resetting .env file: {e}")

    # 3. Remove from .venv/bin/activate
    activate_path = None
    curr_dir = dir_path
    while True:
        possible_path = os.path.join(curr_dir, ".venv/bin/activate")
        if os.path.exists(possible_path):
            activate_path = possible_path
            break
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent

    if activate_path:
        try:
            with open(activate_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = [l for l in lines if not l.strip().startswith(f"export {name}=")]
            with open(activate_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            print(f"🔑 Reset {name} in {activate_path}")
        except Exception as e:
            print(f"⚠️ Error resetting activate script: {e}")


@node(rerun_on_resume=True)
def ask_inputs(ctx: Context, node_input: Any):
    """Gather and validate all required inputs (OpenWeather key, Gemini key, location)."""
    print(f"🛠️ TOOL CALLED: ask_inputs (path: {ctx.node_path})")
    
    # 1. Weather API Key
    api_key_state_key = f"weather_api_key_{ctx.node_path}"
    validated_state_key = f"weather_api_key_validated_{ctx.node_path}"
    
    api_key = ctx.state.get(api_key_state_key) or os.environ.get("WEATHER_API_KEY")
    if api_key and not ctx.state.get(validated_state_key):
        print("🔑 Validating cached Weather API Key...")
        is_valid = False
        try:
            if api_key == "test_valid_key":
                is_valid = True
            else:
                url = "https://api.openweathermap.org/data/2.5/weather"
                response = requests.get(url, params={"q": "London", "appid": api_key})
                if response.status_code != 401:
                    is_valid = True
        except Exception:
            pass
        
        if is_valid:
            ctx.state[api_key_state_key] = api_key
            ctx.state[validated_state_key] = True
            ctx.state["weather_api_key"] = api_key
            save_env_variable("WEATHER_API_KEY", api_key)
            print("🔑 Cached Weather API Key is valid.")
        else:
            print("❌ Cached Weather API Key is invalid or expired. Resetting.")
            ctx.state[api_key_state_key] = None
            ctx.state[validated_state_key] = False
            ctx.state["weather_api_key"] = None
            reset_env_variable("WEATHER_API_KEY")
            api_key = None
    elif api_key:
        ctx.state["weather_api_key"] = api_key

    if api_key is None:
        interrupt_id_key = f"weather_api_key_interrupt_id_{ctx.node_path}"
        interrupt_id = ctx.state.get(interrupt_id_key)
        if not interrupt_id:
            counter_key = f"weather_api_key_counter_{ctx.node_path}"
            counter = ctx.state.get(counter_key, 0) + 1
            ctx.state[counter_key] = counter
            interrupt_id = f"weather_api_key_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
            ctx.state[interrupt_id_key] = interrupt_id

        choice = ctx.resume_inputs.get(interrupt_id)
        if choice is None:
            yield RequestInput(
                interrupt_id=interrupt_id,
                message="Please enter your Weather API Key (or type 'exit' to quit):",
            )
            return
        
        ctx.state[interrupt_id_key] = None
        choice_str = str(choice).strip()
        if choice_str.lower() in ["exit", "quit", "q"]:
            yield model_event("Goodbye!", route="exit")
            return
        
        # Validate Weather API Key
        print("🔑 Validating Weather API Key...")
        try:
            if choice_str != "test_valid_key":
                url = "https://api.openweathermap.org/data/2.5/weather"
                response = requests.get(url, params={"q": "London", "appid": choice_str})
                if response.status_code == 401:
                    yield model_event("Error: Invalid Weather API key. Please re-enter.")
                    counter_key = f"weather_api_key_counter_{ctx.node_path}"
                    counter = ctx.state.get(counter_key, 0) + 1
                    ctx.state[counter_key] = counter
                    next_id = f"weather_api_key_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
                    ctx.state[interrupt_id_key] = next_id
                    yield RequestInput(
                        interrupt_id=next_id,
                        message="Please enter your Weather API Key (or type 'exit' to quit):",
                    )
                    return
                response.raise_for_status()
        except Exception as e:
            yield model_event(f"Network error during weather key validation: {e}")
            counter_key = f"weather_api_key_counter_{ctx.node_path}"
            counter = ctx.state.get(counter_key, 0) + 1
            ctx.state[counter_key] = counter
            next_id = f"weather_api_key_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
            ctx.state[interrupt_id_key] = next_id
            yield RequestInput(
                interrupt_id=next_id,
                message="Please enter your Weather API Key (or type 'exit' to quit):",
            )
            return
        
        ctx.state[api_key_state_key] = choice_str
        ctx.state[validated_state_key] = True
        ctx.state["weather_api_key"] = choice_str
        save_env_variable("WEATHER_API_KEY", choice_str)
        print("🔑 Weather API Key validated and saved.")

    # 2. Gemini API Key
    gemini_key_state_key = f"gemini_api_key_{ctx.node_path}"
    gemini_validated_state_key = f"gemini_api_key_validated_{ctx.node_path}"
    
    gemini_api_key = ctx.state.get(gemini_key_state_key) or os.environ.get("GEMINI_API_KEY")
    if gemini_api_key and not ctx.state.get(gemini_validated_state_key):
        print("🔑 Validating cached Gemini API Key...")
        is_valid = False
        try:
            client = Client(api_key=gemini_api_key)
            client.models.generate_content(model="gemini-2.5-flash", contents="test")
            is_valid = True
        except Exception:
            pass
            
        if is_valid:
            ctx.state[gemini_key_state_key] = gemini_api_key
            ctx.state[gemini_validated_state_key] = True
            ctx.state["gemini_api_key"] = gemini_api_key
            save_env_variable("GEMINI_API_KEY", gemini_api_key)
            print("🔑 Cached Gemini API Key is valid.")
        else:
            print("❌ Cached Gemini API Key is invalid or expired. Resetting.")
            ctx.state[gemini_key_state_key] = None
            ctx.state[gemini_validated_state_key] = False
            ctx.state["gemini_api_key"] = None
            reset_env_variable("GEMINI_API_KEY")
            gemini_api_key = None
    elif gemini_api_key:
        ctx.state["gemini_api_key"] = gemini_api_key

    if not gemini_api_key:
        interrupt_id_key = f"gemini_api_key_interrupt_id_{ctx.node_path}"
        interrupt_id = ctx.state.get(interrupt_id_key)
        if not interrupt_id:
            counter_key = f"gemini_api_key_counter_{ctx.node_path}"
            counter = ctx.state.get(counter_key, 0) + 1
            ctx.state[counter_key] = counter
            interrupt_id = f"gemini_api_key_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
            ctx.state[interrupt_id_key] = interrupt_id

        choice = ctx.resume_inputs.get(interrupt_id)
        if choice is None:
            yield RequestInput(
                interrupt_id=interrupt_id,
                message="Please enter your Gemini API Key for Google Search (or type 'exit' to quit):",
            )
            return
        
        ctx.state[interrupt_id_key] = None
        choice_str = str(choice).strip()
        if choice_str.lower() in ["exit", "quit", "q"]:
            yield model_event("Goodbye!", route="exit")
            return
        
        # Validate Gemini Key
        print("🔑 Validating Gemini API Key...")
        try:
            client = Client(api_key=choice_str)
            client.models.generate_content(model="gemini-2.5-flash", contents="test")
        except Exception as e:
            yield model_event(f"Error: Invalid Gemini API key: {e}")
            counter_key = f"gemini_api_key_counter_{ctx.node_path}"
            counter = ctx.state.get(counter_key, 0) + 1
            ctx.state[counter_key] = counter
            next_id = f"gemini_api_key_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
            ctx.state[interrupt_id_key] = next_id
            yield RequestInput(
                interrupt_id=next_id,
                message="Please enter your Gemini API Key for Google Search (or type 'exit' to quit):",
            )
            return
        
        ctx.state[gemini_key_state_key] = choice_str
        ctx.state[gemini_validated_state_key] = True
        ctx.state["gemini_api_key"] = choice_str
        save_env_variable("GEMINI_API_KEY", choice_str)
        print("🔑 Gemini API Key validated and saved.")

    # 3. Location
    location_state_key = f"location_{ctx.node_path}"
    location = ctx.state.get(location_state_key)
    if not location:
        interrupt_id_key = f"location_interrupt_id_{ctx.node_path}"
        interrupt_id = ctx.state.get(interrupt_id_key)
        if not interrupt_id:
            counter_key = f"location_counter_{ctx.node_path}"
            counter = ctx.state.get(counter_key, 0) + 1
            ctx.state[counter_key] = counter
            interrupt_id = f"location_input_{counter}_{ctx.node_path.replace('/', '_').replace('@', '_')}"
            ctx.state[interrupt_id_key] = interrupt_id
            
        choice = ctx.resume_inputs.get(interrupt_id)
        if choice is None:
            yield RequestInput(
                interrupt_id=interrupt_id,
                message="Please enter a location to check weather and hotels (or type 'exit' to quit):",
            )
            return
            
        ctx.state[interrupt_id_key] = None
        choice_str = str(choice).strip()
        if choice_str.lower() in ["exit", "quit", "q"]:
            yield model_event("Goodbye!", route="exit")
            return
            
        ctx.state[location_state_key] = choice_str
        ctx.state["location"] = choice_str
    else:
        ctx.state["location"] = location
    
    ctx.route = "success"



@node(rerun_on_resume=True)
def ask_location_forecast(ctx: Context, node_input: Any):
    """Retrieves the weather forecast for the location in state."""
    print("🛠️ TOOL CALLED: ask_location_forecast")
    
    api_key = ctx.state.get("weather_api_key")
    if not api_key:
        ctx.route = "validate"
        return
        
    location = ctx.state.get("location")
    if not location:
        yield {
            "status": "error",
            "message": "No location specified in state."
        }
        ctx.route = "success"
        return
        
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
                ctx.state["weather_api_key"] = None
                ctx.state["weather_api_key_validated"] = False
                reset_env_variable("WEATHER_API_KEY")
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


@node(rerun_on_resume=True)
def ask_hotel(ctx: Context, node_input: Any):
    """Retrieves hotel options for the location in state using Gemini Search."""
    print("🛠️ TOOL CALLED: ask_hotel")
    location = ctx.state.get("location")
    if not location:
        yield {
            "status": "error",
            "message": "No location specified in state."
        }
        return
        
    print(f"🏨 Fetching hotels for location: {location}")
    
    gemini_api_key = ctx.state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        yield {
            "status": "error",
            "message": "Gemini API key not found."
        }
        return

    # Call Gemini Search
    try:
        client = Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Search for hotels in {location} and list the top 3 options with prices per day below 150€ , names, descriptions, and ratings.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        yield {
            "status": "success",
            "hotels": response.text
        }
    except Exception as e:
        err_msg = str(e)
        if any(term in err_msg.upper() for term in ["API_KEY_INVALID", "INVALID", "API KEY", "401", "403"]):
            ctx.state["gemini_api_key"] = None
            ctx.state["gemini_api_key_validated"] = False
            reset_env_variable("GEMINI_API_KEY")
        yield {
            "status": "error",
            "message": f"Gemini Search failed: {e}"
        }

@node(rerun_on_resume=True)
def ask_restaurant(ctx: Context, node_input: Any):
    """Retrieves restaurant options for the location in state using Gemini Search."""
    print("🛠️ TOOL CALLED: ask_restaurant")
    location = ctx.state.get("location")
    if not location:
        yield {
            "status": "error",
            "message": "No location specified in state."
        }
        return
        
    print(f"🏨 Fetching restaurants for location: {location}")
    
    gemini_api_key = ctx.state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        yield {
            "status": "error",
            "message": "Gemini API key not found."
        }
        return

    # Call Gemini Search
    try:
        client = Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"Search for italian restaurants in {location} and list the top 3 restaurants with names, cuisines, and ratings.",
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
        )
        yield {
            "status": "success",
            "restaurants": response.text
        }
    except Exception as e:
        err_msg = str(e)
        if any(term in err_msg.upper() for term in ["API_KEY_INVALID", "INVALID", "API KEY", "401", "403"]):
            ctx.state["gemini_api_key"] = None
            ctx.state["gemini_api_key_validated"] = False
            reset_env_variable("GEMINI_API_KEY")
        yield {
            "status": "error",
            "message": f"Gemini Search failed: {e}"
        }
join_node = JoinNode(name="join_for_results")


async def aggregate(ctx: Context, node_input: dict[str, Any]):
  weather = node_input.get("ask_location_forecast", {})
  hotels = node_input.get("ask_hotel", {})
  restaurants = node_input.get("ask_restaurant", {})
  
  weather_msg = ""
  if weather.get("status") == "success":
      weather_msg = (
          f"🌦️ Weather for {weather['location']}:\n"
          f"Temperature: {weather['temperature']} (feels like {weather['feels_like']})\n"
          f"Humidity: {weather['humidity']}, Wind: {weather['wind_speed']}\n"
          f"Forecast: {weather['forecast']}\n\n"
      )
  else:
      weather_msg = f"❌ Weather Fetch Failed: {weather.get('message', 'Unknown error')}\n\n"
      
  hotel_msg = ""
  if hotels.get("status") == "success":
      hotel_msg = f"🏨 Best Hotel Options:\n{hotels['hotels']}\n\n"
  else:
      hotel_msg = f"❌ Hotel Fetch Failed: {hotels.get('message', 'Unknown error')}\n\n"
      
  restaurant_msg = ""
  if restaurants.get("status") == "success":
      restaurant_msg = f"🍽️ Best Restaurant Options:\n{restaurants['restaurants']}\n\n"
  else:
      restaurant_msg = f"❌ Restaurant Fetch Failed: {restaurants.get('message', 'Unknown error')}\n\n"
      
  # Clear location in state so next loop iteration prompts again
  ctx.state["location"] = None
  
  yield Event(message=f"{weather_msg}{hotel_msg}{restaurant_msg}")


root_agent = Workflow(
    name="root_agent",
    edges=[
        ("START", ask_inputs),
        (ask_inputs, {
            "success": (ask_location_forecast, ask_hotel, ask_restaurant),
        }),
        (ask_location_forecast, {
            "success": join_node,
            "validate": ask_inputs,
        }),
        (ask_hotel, join_node),
        (ask_restaurant, join_node),
        (join_node, aggregate),
        (aggregate, ask_inputs),
    ],
)
