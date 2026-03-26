"""
routes.py
---------
All FastAPI routers. Keep business logic thin here — delegate to services.
"""

import json
import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import ShopModel, InvoiceModel
from llm_service import parse_order_with_llm
from shop_manager import shop_manager
from invoice import Invoice

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_bill_id() -> str:
    return f"FC-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def enrich_bill(bill: dict, customer_name: str) -> dict:
    """Attach shop metadata and round values."""
    bill["bill_id"] = make_bill_id()
    bill["timestamp"] = datetime.now().strftime("%d %b %Y, %I:%M %p")
    bill["shop_name"] = "FreshCut Meat Shop"
    bill["shop_address"] = "123, Butcher Lane, Kampli, Karnataka - 583132"
    bill["shop_phone"] = "+91 98765 43210"
    bill["customer_name"] = bill.get("customer_name") or customer_name

    for item in bill.get("items", []):
        item["item_total"] = round(item["item_total"], 2)
    bill["subtotal"] = round(bill.get("subtotal", 0), 2)
    bill["gst"] = round(bill.get("gst", 0), 2)
    bill["grand_total"] = round(bill.get("grand_total", 0), 2)
    return bill


# ── Schemas ───────────────────────────────────────────────────────────────────

class OrderRequest(BaseModel):
    message: str
    customer_name: str = "Customer"


class ConfirmRequest(BaseModel):
    bill: dict          # The final bill object from the frontend
    order_prompt: str   # The original user text


# ── Order routes ──────────────────────────────────────────────────────────────

@router.post("/parse-order")
async def parse_order(req: OrderRequest):
    """
    Generate a bill from natural language. Can be called repeatedly.
    No DB write yet — user must confirm.
    """
    try:
        bill_data, raw = parse_order_with_llm(req.message, req.customer_name)
        bill_data = enrich_bill(bill_data, req.customer_name)
        return {"bill": bill_data, "raw_response": raw}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-order")
async def confirm_order(req: ConfirmRequest, db: Session = Depends(get_db)):
    """
    User clicked Confirm. Persist invoice to DB, assign to best shop,
    add to in-memory Shop instance.
    """
    bill = req.bill
    grand_total = bill.get("grand_total", 0)
    invoice_code = bill.get("bill_id", make_bill_id())
    customer_name = bill.get("customer_name", "Customer")

    # 1. Get all serving centers from DB
    shops_db = db.query(ShopModel).all()
    if not shops_db:
        raise HTTPException(status_code=503, detail="No serving centers available.")

    serving_centers = {s.id: (s.x, s.y) for s in shops_db}

    # 2. Find best shop (strategy lives in shop_manager)
    best_shop_id = shop_manager.find_best_shop_id(
        serving_centers=serving_centers,
        order_context={"bill": bill},   # future: pass more context here
    )
    shop_db = db.query(ShopModel).filter(ShopModel.id == best_shop_id).first()

    # 3. Save invoice to DB
    invoice_db = InvoiceModel(
        invoice_code=invoice_code,
        customer_name=customer_name,
        order_prompt=req.order_prompt,
        bill_json=json.dumps(bill),
        grand_total=grand_total,
        status="queued",
        shop_id=best_shop_id,
    )
    db.add(invoice_db)
    db.commit()
    db.refresh(invoice_db)

    # 4. Create in-memory Invoice & assign to live Shop
    inv = Invoice(
        invoice_id=invoice_code,
        user_id=invoice_db.id,
        amount=grand_total,
        order=req.order_prompt,
        customer_name=customer_name,
    )
    shop_manager.assign_invoice(inv, shop_db)

    return {
        "success": True,
        "invoice_code": invoice_code,
        "assigned_shop": {
            "id": shop_db.id,
            "name": shop_db.name,
        },
        "message": f"Order confirmed and assigned to {shop_db.name}!",
    }


# ── Monitor routes ────────────────────────────────────────────────────────────

@router.get("/monitor/shops")
def list_all_shops(db: Session = Depends(get_db)):
    """All shops from DB (for the search bar and full list)."""
    shops = db.query(ShopModel).all()
    result = []
    for s in shops:
        live = shop_manager.get_shop(s.id)
        queue_count = len(live.Invoices) if live else 0
        result.append({
            "id": s.id,
            "name": s.name,
            "x": s.x,
            "y": s.y,
            "rating": s.rating,
            "active": live is not None,
            "queue_count": queue_count,
        })
    return result


@router.get("/monitor/shop/{shop_id}")
def get_shop_detail(shop_id: int, db: Session = Depends(get_db)):
    """Full shop card with live invoice queue."""
    shop_db = db.query(ShopModel).filter(ShopModel.id == shop_id).first()
    if not shop_db:
        raise HTTPException(status_code=404, detail="Shop not found")

    live = shop_manager.get_shop(shop_id)
    invoices = shop_manager.get_invoice_statuses(shop_id) if live else []

    return {
        "id": shop_db.id,
        "name": shop_db.name,
        "x": shop_db.x,
        "y": shop_db.y,
        "rating": shop_db.rating,
        "active": live is not None,
        "queue": invoices,
    }


# ── Misc ──────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "shop": "FreshCut Meat Shop"}


@router.get("/menu")
def menu():
    return {
        "products": [
            {"name": "Chicken", "price": 180, "unit": "per kg"},
            {"name": "Mutton",  "price": 360, "unit": "per kg"},
            {"name": "Beef",    "price": 200, "unit": "per kg"},
        ],
        "customizations": [
            {"name": "Deep Cut",     "extra": 20, "unit": "per kg"},
            {"name": "Keema",        "extra": 30, "unit": "per kg"},
            {"name": "Small Pieces", "extra": 10, "unit": "per kg"},
            {"name": "Soaked",       "extra": 10, "unit": "per kg"},
        ],
    }


# ── Seed route (dev only) ─────────────────────────────────────────────────────

@router.post("/seed-shops")
def seed_shops(db: Session = Depends(get_db)):
    """Creates sample shops if none exist. Call once during setup."""
    if db.query(ShopModel).count() > 0:
        return {"message": "Shops already exist"}
    sample = [
        ShopModel(name="FreshCut Kampli Central", x=10, y=20, rating=4.8),
        ShopModel(name="FreshCut Siruguppa Road",  x=30, y=15, rating=4.5),
        ShopModel(name="FreshCut Hospet Branch",   x=50, y=60, rating=4.7),
    ]
    db.add_all(sample)
    db.commit()
    return {"message": f"Seeded {len(sample)} shops"}
