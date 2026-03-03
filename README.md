# The Chocolate Factory – Mini-MRP MVP

A minimal Manufacturing Resource Planning (MRP) system for a chocolate manufacturer. It tracks raw materials (Cocoa, Sugar), finished goods (Dark Chocolate), and executes **production** in a single atomic transaction so inventory never goes negative.

## Features

- **Product management**: Ingredients and finished goods with *stock on hand*. **Products** page: list all products, restock existing ingredients or add new ones, create new finished goods with inline BoM (component names and quantities).
- **Bill of Materials (BoM)**: Dark Chocolate = 50g Cocoa + 20g Sugar per unit (configurable per product). Manage BoM per finished product: add/remove component lines at `/products/{id}/bom`.
- **Manufacturing orders**: Create an order to produce X units; **Edit** draft orders (change product and quantity); **Produce** action:
  1. Checks sufficient stock for all ingredients.
  2. If insufficient → shows an error, **no changes** to the database.
  3. If sufficient → deducts ingredients and adds finished product in **one transaction** (all or nothing).
- **UI**: Navbar with Stock, Products, Orders; Orders shows a draft-count badge (via `GET /api/stats`).

## Tech stack

- **Backend**: Python 3.10+, FastAPI
- **Database**: PostgreSQL (database: `Choco_factory`)
- **ORM**: SQLAlchemy 2.x with declarative models
- **UI**: HTML + Bootstrap 5 (Jinja2 templates); minimal JS for draft badge

## Assumptions

- PostgreSQL is running locally; database `Choco_factory` exists and is accessible with the credentials you provide (see below).
- Stock for ingredients is stored in **grams**; finished goods in **units**.
- One BoM per finished product; each line has a component and `quantity_per_unit` (e.g. 50g Cocoa per 1 Dark Chocolate).
- Manufacturing orders are in status `draft` until **Produce** is run; then `produced`. Draft orders can be **edited** (product and quantity).

## How to run

### 1. Create a virtual environment and install dependencies

```bash
cd "d:\D\The Chocolate Factory"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure the database

Copy the example env and set your PostgreSQL URL (database `Choco_factory`, password as you created):

```bash
copy .env.example .env
```

Edit `.env` if your user or host differs:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/Choco_factory
```

(Replace `postgres` and password with your PostgreSQL credentials if different.)

### 3. Create tables and seed data

From the project root:

```bash
python -m scripts.init_db
python -m scripts.seed_data
```

This creates tables and seeds:

- **Cocoa**: 1000 g  
- **Sugar**: 500 g  
- **Dark Chocolate**: 0 units, BoM 50g Cocoa + 20g Sugar per unit  

### 4. Start the web app

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

**Optional:** Use the helper scripts (run from project root in PowerShell):

- `.\start_backend.ps1` — starts the FastAPI server (with reload).
- `.\start_frontend.ps1` — opens the app in your default browser (start the backend first).

**Pages:**

- **Home (`/`)**: View stock and recent orders; **Edit** and **Produce** on draft orders.
- **Orders (`/orders`)**: Create a new manufacturing order (product + quantity); **Edit** or **Produce** from the list.
- **Products (`/products`)**: List products, restock ingredients, link to create new finished good.
- **New product (`/products/new`)**: Create a finished good with component names and quantities (BoM). Ingredients are created if they don’t exist.
- **BoM (`/products/{id}/bom`)**: Add or remove component lines for a finished product.

Try producing 10 Dark Chocolates (needs 500g Cocoa, 200g Sugar) – it should succeed. Then try an order for 1,000 units to see the **insufficient stock** error and no inventory change.

## Project structure

```
app/
  config.py          # DATABASE_URL from env
  database.py        # Engine, Session, transactional_session (atomic produce)
  main.py            # FastAPI app
  models/            # Product, BillOfMaterial, ManufacturingOrder
  api/routes.py      # Web UI + Products, Orders, Edit, BoM + /api/stats, /api/products, /api/orders
  services/
    produce_service.py  # produce_order(mo_id) – validation + single transaction
  templates/         # base, index, orders, order_edit, products, product_new, product_bom, macros
scripts/
  init_db.py         # Create tables
  seed_data.py       # Seed products + BoM
```

## API (optional)

- `GET /api/stats` — `{ "draft_count": N }` for navbar badge.
- `GET /api/products` — list products with stock.
- `GET /api/orders` — list manufacturing orders.

## Evaluation notes

- **Schema**: Products ↔ BoM with `quantity_per_unit`; MO references product and quantity.
- **Integrity**: `produce_order()` runs inside `transactional_session()`; on any exception the transaction is rolled back (no partial deduction).
- **Negative stock**: Validated before any writes; shortfalls returned in `InsufficientStockError` and shown in the UI.
- **Edit order**: Draft orders can be updated (product and quantity) at `/orders/{id}/edit`; produced orders cannot be edited.
- **Separation**: Models, database session, produce logic, and routes are in separate modules with clear naming.

## Repository

GitHub: [https://github.com/UktambekA/factory](https://github.com/UktambekA/factory). Ensure `.env` is in `.gitignore` so credentials are not committed.
