"""
shop_manager.py
---------------
Keeps live Shop instances in memory.
Each Shop instance is created on first invoice assignment and destroyed when empty.

Assignment strategy is isolated in `find_best_shop_id()` — swap logic freely.
Currently: nearest Euclidean distance.
"""

import math
import asyncio
import logging
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, Optional

from invoice import Invoice
from shop import Shop

logger = logging.getLogger(__name__)

# ── How long before the first invoice in a shop is auto-removed ──────────────
SERVE_DURATION_SECONDS = 120   # 2 minutes


class ShopManager:
    """
    Single instance (created in app.py) that owns:
      - _shops: {shop_id: Shop}  — live in-memory shop objects
      - _timers: {shop_id: asyncio.Task}  — one FIFO-drain task per shop
    """

    def __init__(self):
        self._shops: Dict[int, Shop] = {}
        self._timers: Dict[int, asyncio.Task] = {}

    # ─────────────────────────────────────────────
    # Assignment strategy (easy to swap)
    # ─────────────────────────────────────────────

    def find_best_shop_id(
        self,
        serving_centers: Dict[int, tuple],   # {id: (x, y)}
        order_context: dict = None,           # future: pass rating, order type, etc.
    ) -> int:
        """
        Current logic: nearest Euclidean distance from origin (0, 0).
        Change this function to plug in rating-based, load-balanced, etc.
        """
        # For distance we just pick the shop closest to a reference point.
        # Right now reference is origin; later you could pass customer coords.
        ref_x, ref_y = 0.0, 0.0

        best_id = min(
            serving_centers,
            key=lambda sid: math.sqrt(
                (serving_centers[sid][0] - ref_x) ** 2 +
                (serving_centers[sid][1] - ref_y) ** 2
            ),
        )
        return best_id

    # ─────────────────────────────────────────────
    # Core operations
    # ─────────────────────────────────────────────

    def get_or_create_shop(self, shop_db_row) -> Shop:
        """Return existing live Shop or create a fresh one from the DB row."""
        sid = shop_db_row.id
        if sid not in self._shops:
            self._shops[sid] = Shop(
                shop_id=sid,
                name=shop_db_row.name,
                X=shop_db_row.x,
                Y=shop_db_row.y,
            )
            logger.info(f"[ShopManager] Created in-memory Shop #{sid} ({shop_db_row.name})")
        return self._shops[sid]

    def assign_invoice(self, invoice: Invoice, shop_db_row) -> Shop:
        """Add invoice to the shop, start FIFO drain timer if not already running."""
        shop = self.get_or_create_shop(shop_db_row)
        shop.add_invoice(invoice)
        logger.info(
            f"[ShopManager] Invoice {invoice.invoice_id} → Shop #{shop_db_row.id} "
            f"({len(shop.Invoices)} in queue)"
        )
        self._ensure_timer(shop_db_row.id)
        return shop

    def get_shop(self, shop_id: int) -> Optional[Shop]:
        return self._shops.get(shop_id)

    def get_all_shops(self) -> Dict[int, Shop]:
        return dict(self._shops)

    def get_invoice_statuses(self, shop_id: int) -> list:
        """Return invoices with serving/queued status."""
        shop = self._shops.get(shop_id)
        if not shop:
            return []
        invoice_ids = list(shop.Invoices.keys())
        result = []
        for i, iid in enumerate(invoice_ids):
            inv = shop.Invoices[iid]
            result.append({
                "invoice_id": iid,
                "customer_name": inv.customer_name,
                "order": inv.order,
                "amount": inv.amount,
                "status": "serving" if i == 0 else "queued",
                "position": i + 1,
            })
        return result

    # ─────────────────────────────────────────────
    # FIFO timer logic
    # ─────────────────────────────────────────────

    def _ensure_timer(self, shop_id: int):
        """Start a drain task for this shop if one isn't already running."""
        if shop_id not in self._timers or self._timers[shop_id].done():
            task = asyncio.create_task(self._drain_loop(shop_id))
            self._timers[shop_id] = task

    async def _drain_loop(self, shop_id: int):
        """
        Every SERVE_DURATION_SECONDS, remove the first invoice (FIFO).
        When the shop is empty, remove it from memory.
        """
        while True:
            await asyncio.sleep(SERVE_DURATION_SECONDS)
            shop = self._shops.get(shop_id)
            if not shop or not shop.Invoices:
                break
            # Pop first invoice (FIFO)
            first_id = next(iter(shop.Invoices))
            removed = shop.Invoices.pop(first_id)
            logger.info(
                f"[ShopManager] Invoice {first_id} served & removed from Shop #{shop_id}. "
                f"{len(shop.Invoices)} remaining."
            )
            if not shop.Invoices:
                del self._shops[shop_id]
                logger.info(f"[ShopManager] Shop #{shop_id} is empty — removed from memory.")
                break

        self._timers.pop(shop_id, None)


# ── Singleton ─────────────────────────────────────────────────────────────────
shop_manager = ShopManager()
