"""
llm_service.py
--------------
All Groq / LLM interaction lives here.
Swap out the model or provider without touching routes.
"""

import json
import os
import re
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")

SYSTEM_PROMPT = """You are an intelligent order-parsing assistant for a meat shop called "FreshCut Meat Shop".

AVAILABLE PRODUCTS (base prices per kg):
- Chicken: ₹180/kg
- Mutton: ₹360/kg  
- Beef: ₹200/kg

CUSTOMIZATIONS (extra charge per kg):
- Deep Cut: +₹20/kg
- Keema: +₹30/kg
- Small Pieces: +₹10/kg
- Soaked: +₹10/kg

Your task: Parse the customer's natural language order and extract a structured JSON bill.

Rules:
1. Extract meat type, quantity (in kg), and any customizations.
2. If quantity is not mentioned, assume 1 kg.
3. If the customer says "half kg" or "500g", use 0.5.
4. A customer can order multiple items.
5. Return ONLY a valid JSON object, no extra text.

Output format:
{
  "customer_name": "Customer" or extracted name if mentioned,
  "items": [
    {
      "meat": "chicken|mutton|beef",
      "quantity_kg": <float>,
      "customizations": ["deep cut", "keema", "small pieces", "soaked"],
      "base_price_per_kg": <int>,
      "customization_charge_per_kg": <int>,
      "total_price_per_kg": <int>,
      "item_total": <float>
    }
  ],
  "subtotal": <float>,
  "gst": <float>,
  "grand_total": <float>,
  "notes": "any special notes or friendly message"
}

Calculate:
- total_price_per_kg = base_price_per_kg + customization_charge_per_kg
- item_total = total_price_per_kg * quantity_kg
- subtotal = sum of all item_totals
- gst = subtotal * 0.05 (5% GST)
- grand_total = subtotal + gst
"""


def parse_order_with_llm(message: str, customer_name: str) -> dict:
    """
    Call Groq and return the parsed bill dict.
    Raises ValueError if the response is not valid JSON.
    """
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Customer order: {message}\nCustomer name: {customer_name}"),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    # Strip markdown fences if present
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

    try:
        return json.loads(clean), raw
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}. Raw: {raw}")
