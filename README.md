# FreshCut Meat Shop — v2

## File Structure

```
freshcut/
├── app.py            ← FastAPI entry point  (uvicorn app:app --reload)
├── routes.py         ← All API endpoints
├── database.py       ← SQLAlchemy engine + session
├── models.py         ← DB table definitions (ShopModel, InvoiceModel)
├── shop_manager.py   ← In-memory Shop instances + FIFO drain logic
├── llm_service.py    ← Groq / LangChain order parsing
├── invoice.py        ← Invoice class
├── shop.py           ← Shop class (OrderedDict queue)
├── customer.html     ← Customer chat UI
├── monitor.html      ← Operations monitor UI
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

Then seed sample shops (one-time):
```
POST http://localhost:8000/seed-shops
```

Open `customer.html` in browser for the order chat.  
Open `monitor.html` in browser for the live operations monitor.

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /parse-order | Generate bill (no DB write) |
| POST | /confirm-order | Persist + assign to best shop |
| GET | /monitor/shops | All shops overview |
| GET | /monitor/shop/{id} | Single shop with live queue |
| POST | /seed-shops | Create sample shops (dev) |
| GET | /menu | Menu listing |
| GET | /health | Health check |

## Swapping Assignment Logic

Open `shop_manager.py` and edit `find_best_shop_id()`.  
The method receives `serving_centers` (dict of id→(x,y)) and `order_context` (the full bill dict).  
Return whichever shop ID you want. Distance, rating, queue depth — all yours.

## Queue Behavior

- Each confirmed order creates an `Invoice` assigned to a live `Shop` instance.
- After 2 minutes (configurable via `SERVE_DURATION_SECONDS` in `shop_manager.py`), the first invoice is removed (FIFO).
- When a shop's queue hits zero, its in-memory instance is destroyed.
- A new order to that shop recreates the instance fresh.

## Monitor UI

- Search by shop ID or load all shops.
- Click a shop card to expand and see the live queue.
- Green blinking dot = currently being served.
- Orange blinking dot = in queue.
- Auto-refreshes every 10 seconds.
