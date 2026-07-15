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
from os import name
 
# pyrefly: ignore [missing-import]
from google.adk import Agent
# pyrefly: ignore [missing-import]
from google.adk import Event
# pyrefly: ignore [missing-import]
from google.adk import Workflow
# pyrefly: ignore [missing-import]
from google.adk.events import RequestInput
# pyrefly: ignore [missing-import]
from google.genai import types
# pyrefly: ignore [missing-import]
from google.adk.agents.context import Context
# pyrefly: ignore [missing-import]
from google.genai import Client
# pyrefly: ignore [missing-import]
from google.adk.workflow import node
# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
import re
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from google.adk.workflow import JoinNode, Edge
# pyrefly: ignore [missing-import]
from pydantic import Field


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

class InvoiceRequest(BaseModel):
  vendor: str | None = Field(default=None, description="Vendor name.")
  amount: float = Field(description="Amount of the invoice.")
  invoice_number: int = Field( description="Invoice number.")
  invoice_date: str | None = Field(default=None, description="Date of the invoice.")
  subscription_type: str | None = Field(default=None, description="Subscription type.")
  account_number: str | None = Field(default=None, description="Account number of the customer.")
  payment_method: str | None = Field(default=None, description="Payment method used for the invoice.")

class ComplaintCategory(BaseModel):
  route: str = Field(description="Route to the category of the complaint.")
  summary: str = Field(description="Summary of the complaint.")
  # customer_details: str = Field(description="Details of the customer.")
  feedback: str = Field(description="Feedback of the complaint.")
  
class CustomerDetails(BaseModel):
    account_number: str | None = Field(default=None, description="Account number of the customer.")
    customer_name: str = Field(description="Name of the customer.")
    phone_number: str = Field(description="Phone number of the customer.")
    email: str | None = Field(default=None, description="Email of the customer.")
   # order_number: str | None = Field(default=None, description="Order number of the customer.")
    shipping_address: str | None = Field(default=None, description="Shipping address of the customer.")

class ComplaintDetails(BaseModel):
    product_name: str | None = Field(default=None, description="Product name.")
    order_number: str | None = Field(default=None, description="Order number.")
    customer_name: str = Field(description="Name of the customer.")
    customer_account_number: str | None = Field(default=None, description="Account number of the customer.")
    customer_phone: str | None = Field(default=None, description="Phone number of the customer.")
    complaint: str = Field(description="Complaint details.")

@node(rerun_on_resume=True)
def ask_structured_invoice(ctx: Context, node_input: str):
  invoice = ctx.state.get("invoice")
  if invoice is not None:
    yield Event(output=invoice)
    return

  interrupt_id = ctx.state.get("invoice_interrupt_id")
  if not interrupt_id:
    counter = ctx.state.get("invoice_counter", 0) + 1
    ctx.state["invoice_counter"] = counter
    interrupt_id = f"invoice_form_{counter}"
    ctx.state["invoice_interrupt_id"] = interrupt_id

  user_input = ctx.resume_inputs.get(interrupt_id)
  if user_input is None:
    yield RequestInput(
        interrupt_id=interrupt_id,
        message="Please fill out the following details:",
        response_schema=InvoiceRequest,
    )
    return
  '''

  Added .model_dump() conversion in ask_structured_invoice 
  and check_structured_response before storing the invoice in 
  ctx.state or yielding it in the Event's output:

  '''
  ctx.state["invoice_interrupt_id"] = None
  invoice_dict = user_input.model_dump() if hasattr(user_input, "model_dump") else user_input
  ctx.state["invoice"] = invoice_dict
  yield Event(state={"invoice": invoice_dict}, output=invoice_dict)


@node(rerun_on_resume=True)
def check_structured_invoice_response(ctx: Context, node_input: InvoiceRequest):
    invoice = node_input
    invoice_dict = invoice.model_dump() if hasattr(invoice, "model_dump") else invoice
    ctx.state["invoice"] = invoice_dict
    if isinstance(invoice, InvoiceRequest):
        if str(invoice.invoice_number) != "12345":
            yield Event(message="Invalid invoice number.", route="fail", output=invoice_dict)
            ctx.route = "fail"
        else:
            yield Event(output=invoice_dict, route="success")
            ctx.route = "success"
    else:
        yield Event(message="Invalid invoice format.", route="fail", output=invoice_dict)
        ctx.route = "fail"

@node(rerun_on_resume=True)
def ask_structured_customer_details(ctx: Context, node_input: str):
    customer = ctx.state.get("customer")
    if customer is not None:
        yield Event(output=customer)
        return
    interrupt_id = ctx.state.get("customer_interrupt_id")
    if not interrupt_id:
        counter = ctx.state.get("customer_counter", 0) + 1
        ctx.state["customer_counter"] = counter
        interrupt_id = f"customer_form_{counter}"
        ctx.state["customer_interrupt_id"] = interrupt_id

    user_input = ctx.resume_inputs.get(interrupt_id)
    if user_input is None:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message="Please fill out the customer details:",
            response_schema=CustomerDetails,
        )
        return
    ctx.state["customer_interrupt_id"] = None
    customer_dict = user_input.model_dump() if hasattr(user_input, "model_dump") else user_input
    #ctx.state["customer"] = customer_dict
    yield Event(state={"customer": customer_dict}, output=customer_dict)


@node(rerun_on_resume=True)
def check_structured_customer_response(ctx: Context, node_input: CustomerDetails):
    customer = node_input
    customer_dict = customer.model_dump() if hasattr(customer, "model_dump") else customer
    ctx.state["customer"] = customer_dict
    if isinstance(customer, CustomerDetails):
        if str(customer.phone_number) != "1234567890" or str(customer.customer_name) != "Paul":
            yield Event(message="Invalid customer phone number or name.", route="fail", output=customer_dict)
            ctx.route = "fail"
        else:
            yield Event(output=customer_dict, route="success")
            ctx.route = "success"
    else:
        yield Event(message="Invalid customer format.", route="fail", output=customer_dict)
        ctx.route = "fail"


@node(rerun_on_resume=True)
def ask_structured_complaint(ctx: Context, node_input):
    structured_complaint = ctx.state.get("structured_complaint")
    if structured_complaint is not None:
        yield Event(output=structured_complaint)
        return
    interrupt_id = ctx.state.get("complaint_interrupt_id")
    if not interrupt_id:
        counter = ctx.state.get("complaint_counter", 0) + 1
        ctx.state["complaint_counter"] = counter
        interrupt_id = f"complaint_form_{counter}"
        ctx.state["complaint_interrupt_id"] = interrupt_id

    user_input = ctx.resume_inputs.get(interrupt_id)
    if user_input is None:
        yield RequestInput(
            interrupt_id=interrupt_id,
            message="Please enter the customer's complaint:",
            response_schema = ComplaintDetails    
        )
        return

    #ctx.state["complaint"] = user_input
    #yield Event(state={"complaint": user_input, "feedback": ""}, output=user_input)

    ctx.state["complaint_interrupt_id"] = None
    complaint_dict = user_input.model_dump() if hasattr(user_input, "model_dump") else user_input
    ctx.state["structured_complaint"] = complaint_dict
    yield Event(state={"structured_complaint": complaint_dict}, output=complaint_dict)
 
@node(rerun_on_resume=True)
def process_structured_complaint(ctx: Context, node_input: ComplaintDetails):
    complaint_details = node_input
    complaint_dict = complaint_details.model_dump() if hasattr(complaint_details, "model_dump") else complaint_details
    ctx.state["structured_complaint"] = complaint_dict
    if isinstance(complaint_details, ComplaintDetails):
        if complaint_details.customer_name and complaint_details.complaint:
            yield Event(output=complaint_dict, route="success")
            ctx.route = "success"
        else:
            yield Event(message="Required fields (customer_name, complaint) are missing.", route="fail", output=complaint_dict)
            ctx.route = "fail"
    else:
        yield Event(message="Invalid complaint details.", route="fail", output=complaint_dict)
        ctx.route = "fail"
   
@node
def invoice_branch_resolved(ctx: Context, node_input):
  """Passes the resolved invoice value to the branch_resolved node."""
  return ctx.state.get("invoice")


@node
def customer_branch_resolved(ctx: Context, node_input):
  """Passes the resolved customer value to the branch_resolved node."""
  return {
    "customer": ctx.state.get("customer")}


@node
def branch_resolved(ctx: Context, node_input):
  """Passes through the resolved inputs to the join node."""
  return {
      "invoice": ctx.state.get("invoice"),
      "customer": ctx.state.get("customer"),
      "structured_complaint": ctx.state.get("structured_complaint")
  }


@node(rerun_on_resume=True)
def process_complaint_input(ctx: Context, node_input: str):
    # Call Gemini to categorize the complaint and extract details
    gemini_api_key = ctx.state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    client = Client(api_key=gemini_api_key)
    
    prompt = f"""
    Analyze the customer's complaint: "{node_input}"
    
    Categorize the complaint into exactly one of these categories (which will be set as the 'route'):
    1. "product defect"
    2. "shipping issue"
    3. "billing error"
    4. "customer service"
    5. "other"
    
    Also extract a summary of the complaint, customer details if available, and feedback if any.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ComplaintCategory,
            )
        )
        
        import json
        data = json.loads(response.text)
        
        category = data.get("route", "").strip().lower()
        summary = data.get("summary", "")
        customer_details = data.get("customer_details", "")
        feedback = data.get("feedback", "")
        
        # Ensure category matches one of the expected routes
        valid_categories = ["product defect", "shipping issue", "billing error", "customer service", "other"]
        if category not in valid_categories:
            category = "other"
            
        ctx.state["complaint"] = node_input
        ctx.state["category"] = category
        ctx.state["summary"] = summary
        ctx.state["customer_details"] = customer_details
        ctx.state["feedback"] = feedback
        
        yield Event(
            state={
                "complaint": node_input,
                "category": category,
                "summary": summary,
                "customer_details": customer_details,
                "feedback": feedback
            },
            output=summary,
            route=category
        )
        ctx.route = category
    except Exception as e:
        # Fallback on error
        ctx.state["complaint"] = node_input
        ctx.state["category"] = "other"
        yield Event(state={"complaint": node_input, "category": "other"}, route="other")
        ctx.route = "other"



join_node = JoinNode(name="join_for_results")

draft_email = Agent(
    name="draft_email",
    instruction="""
    Please write a polite, helpful response email to the following customer complaint: "{complaint}"

    Depending on the category, use the following details if available:
    - Invoice details: "{invoice?}"
    - Customer details: "{customer?}"
    - Structured complaint details: "{structured_complaint?}"
    

    If there is any feedback from the manager to revise the draft, please incorporate it: "{feedback?}"
    """,
    output_key="draft",
)

def ask_manager_feedback(draft: str):
  yield RequestInput(
      message=(
          "Please review the following draft email and provide 'approve'," 
          f" 'reject', or feedback to revise.\n\n---\n{draft}\n---"
      ),
  )

def handle_manager_feedback(node_input: str):
  if node_input.strip().lower() == "approve":
    yield Event(route="approved")
  elif node_input.strip().lower() == "reject":
    yield Event(route="rejected")
  else:
    yield Event(state={"feedback": node_input}, route="needs_revision")
def reject_email():
  yield Event(message="Draft rejected.")


def send_email(draft: str):
  yield Event(message="Draft approved and sent successfully.")
 

root_agent = Workflow(
    name="request_input",
    edges=[
        ("START", validate_api_key),
        (
            validate_api_key,
            {"success": process_complaint_input},
        ),
        Edge( 
            from_node=process_complaint_input,
            to_node=ask_structured_invoice,
            route=["billing error", "product defect","other"]
        ),
        Edge(
            from_node=process_complaint_input,
            to_node=ask_structured_customer_details,
            route=["shipping issue","customer service"]
        ),
        # Invoice validation branch
        (ask_structured_invoice, check_structured_invoice_response),
        (
            check_structured_invoice_response,
            {
                "success": invoice_branch_resolved,
                "fail": ask_structured_complaint,
            },
        ),
        (ask_structured_complaint, branch_resolved),
        (invoice_branch_resolved, branch_resolved),
        
        # Customer validation branch
        (ask_structured_customer_details, check_structured_customer_response),
        (
            check_structured_customer_response,
            {
                "success": customer_branch_resolved,
                "fail": ask_structured_complaint,
            },
        ),
        (customer_branch_resolved, branch_resolved),
        # Complaint validation branch
        (ask_structured_complaint, process_structured_complaint),
        Edge(
            from_node=process_structured_complaint,
            to_node=branch_resolved,
            route="success"
        ),
        Edge(
            from_node=process_structured_complaint,
            to_node=ask_structured_complaint,
            route="fail"
        ),
        # Merge and continue
        (process_complaint_input, join_node),
        (branch_resolved, join_node),
        (
            join_node,
            draft_email,
            ask_manager_feedback,
            handle_manager_feedback,
        ),
        (
            handle_manager_feedback,
            {
                "needs_revision": draft_email,
                "approved": send_email,
                "rejected": reject_email,
            },
        ),
    ],
)