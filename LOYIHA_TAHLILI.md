# The Chocolate Factory — Loyiha to'liq tahlili

Bu hujjat **The Chocolate Factory** Mini-MRP loyihasining mazmuni, ishlashi va qo‘llaniladigan texnologiyalari bo‘yicha to‘liq tahlilni o‘z ichiga oladi.

---

## 1. Loyiha mazmuni (Mazmun)

### 1.1 Maqsad

Loyiha **Manufacturing Resource Planning (MRP)** tizimining minimal ishlashi mumkin bo‘lgan versiyasi (MVP) bo‘lib, kichik shokolad ishlab chiqaruvchisi uchun inventar va ishlab chiqarishni boshqarishga mo‘ljallangan.

### 1.2 Biznes stsenariy

- **Mahsulot:** 1 dona "Qora shokolad" uchun omborda **50 g Kakao** va **20 g Shakar** bo‘lishi kerak.
- Tizim **xom ashyo** (kakao, shakar) va **tayyor mahsulot** (qora shokolad) qoldiqlarini kuzatadi.
- Foydalanuvchi **"Ishlab chiqarish" (Produce)** tugmasini bosganda tizim avtomatik ravishda:
  - xom ashyo zaxirasini kamaytiradi,
  - tayyor mahsulot zaxirasini oshiradi,
  - barcha o‘zgarishlarni **bitta atom tranzaksiyada** amalga oshiradi (yoki hech narsa o‘zgarmaydi).

### 1.3 Asosiy funksiyalar

| Modul | Vazifa |
|-------|--------|
| **Mahsulotlar (Products)** | Ingredientlar va tayyor mahsulotlar — nom va "Qoldiq (Stock on Hand)". `/products` sahifasida ro‘yxat; yangi ingredient qo‘shish/restock; yangi tayyor mahsulot yaratish (BoM bilan). |
| **Materiallar ro‘yxati (BoM)** | Tayyor mahsulotni tarkibiy qismlariga va har birining miqdoriga bog‘lash. `/products/{id}/bom` orqali BoM qatorlarini qo‘shish/o‘chirish. |
| **Ishlab chiqarish buyurtmasi (MO)** | X dona mahsulot ishlab chiqarish buyurtmasi yaratish; **Edit** orqali mahsulot va miqdorni tahrirlash; **Produce** orqali bajarish. |
| **Produce jarayoni** | Zaxira yetarli bo‘lsa — ingredientlarni ayirib, tayyor mahsulot qo‘shish; yetarli bo‘lmasa — xato ko‘rsatish va hech qanday o‘zgarish kiritmaslik. |
| **Buyurtmani tahrirlash (Edit)** | Draft buyurtmada mahsulot va miqdorni o‘zgartirish (`/orders/{id}/edit`). Produced buyurtmani tahrirlash mumkin emas. |

### 1.4 Dastlabki ma’lumotlar (Seed)

- **Kakao:** 1000 g  
- **Shakar:** 500 g  
- **Qora shokolad:** 0 dona, BoM: 1 dona uchun 50 g Kakao + 20 g Shakar  

Shu asosda, masalan, 10 dona ishlab chiqarish uchun 500 g Kakao va 200 g Shakar kerak — dastlabki zaxira yetadi. 1000 dona uchun esa zaxira yetmasligi kerak va tizim xato qaytaradi.

---

## 2. Loyihaning ishlashi (Ishlash printsipi)

### 2.1 Arxitektura

Loyiha **monolit** web-ilova: bitta FastAPI server ham API, ham HTML sahifalarni beradi. Alohida frontend framework yo‘q — server tomonida Jinja2 shablonlarida HTML generatsiya qilinadi.

```
┌─────────────────────────────────────────────────────────────┐
│  Brauzer (Bootstrap 5 UI, /api/stats orqali draft badge)    │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP GET/POST
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (app.main)                                          │
│  ├── app.api.routes — sahifalar:                             │
│  │     /, /orders, /orders/{id}/edit, /orders/{id}/produce   │
│  │     /products, /products/new, /products/{id}/bom         │
│  │     /api/stats, /api/products, /api/orders                │
│  ├── app.services.produce_service — produce_order(mo_id)    │
│  └── app.models — Product, BillOfMaterial, ManufacturingOrder│
└───────────────────────────┬─────────────────────────────────┘
                            │ SQLAlchemy 2.x, tranzaksiya
┌───────────────────────────▼─────────────────────────────────┐
│  PostgreSQL (Choco_factory)                                  │
│  products | bill_of_materials | manufacturing_orders          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Ma’lumotlar bazasi sxemasi va bog‘lanishlar

- **products** — barcha mahsulotlar (ingredient yoki tayyor mahsulot). Har birida `name`, `product_type`, `stock_on_hand`.
- **bill_of_materials** — BoM: qaysi tayyor mahsulot (`finished_product_id`) uchun qaysi komponent (`component_id`) va **bitta birlik uchun** necha o‘lchov (`quantity_per_unit`).
- **manufacturing_orders** — ishlab chiqarish buyurtmasi: `product_id`, `quantity`, holat (`draft` / `produced`), `created_at`, `produced_at`.

BoM orqali **Product ↔ BillOfMaterial** bog‘lanishi: bitta tayyor mahsulot bir nechta BoM qatoriga ega bo‘lishi mumkin.

### 2.3 "Produce" jarayoni (tranzaksiya va validatsiya)

`produce_order(mo_id)` quyidagicha ishlaydi:

1. **Tranzaksiya:** Barcha o‘zgarishlar `transactional_session()` kontekstida bajariladi. Har qanday istisno (xato) yuz berganda `rollback` — bazada hech narsa o‘zgarmaydi.
2. **Buyurtmani yuklash:** MO, uning mahsuloti va shu mahsulotning BoM qatorlari (komponentlar bilan) birga olinadi.
3. **Tekshiruvlar:** MO mavjudmi, allaqachon `produced` emasmi, `quantity > 0` mi? Mahsulotda BoM bormi? Har bir komponent uchun zaxira yetarlimi — yetmasa `InsufficientStockError`.
4. **O‘zgarishlar (faqat barcha tekshiruvlar o‘tsa):** komponentlardan ayirish, tayyor mahsulotga qo‘shish, MO holati `produced` va `produced_at` yangilanishi.
5. **Commit** yoki **rollback.**

Natija: **"Yoki hammasi, yoki hech narsa"** — yarim qolgan holat yuzaga kelmaydi.

### 2.4 Web interfeys va foydalanuvchi oqimi

- **`/` (Bosh sahifa):** Mahsulotlar qoldig‘i, so‘nggi ishlab chiqarish buyurtmalari jadvali. Draft buyurtmalarda **Edit** va **Produce** tugmalari. `draft_count`, `low_stock_count`; muvaffaqiyat/xato `?produced=1`, `?error=...`.
- **`/orders`:** Barcha buyurtmalar ro‘yxati, yangi buyurtma yaratish formasi (mahsulot + miqdor). Draft uchun **Edit** va **Produce**. Muvaffaqiyat/xato `?produced=1`, `?error=...`. BoM ma’lumotlari (`bom_json`) frontendda ishlatilishi mumkin.
- **GET `/orders/{mo_id}/edit`:** Buyurtmani tahrirlash sahifasi (faqat draft). Mahsulot tanlash va miqdor.
- **POST `/orders/{mo_id}/edit`:** Buyurtmaning `product_id` va `quantity` ni yangilash (faqat draft). Xatoda `?error=...` bilan qayta shu sahifaga redirect.
- **POST `/orders`:** Yangi draft MO yaratish, `/orders` ga redirect.
- **POST `/orders/{mo_id}/produce`:** `produce_order(mo_id)`. Muvaffaqiyatda `/orders?produced=1`, xatoda `/orders?error=...`.
- **`/products`:** Barcha mahsulotlar ro‘yxati; ingredient restock formasi; yangi tayyor mahsulot yaratishga link.
- **`/products/new`:** Yangi tayyor mahsulot + inline BoM (komponent nomlari va miqdorlar) yaratish formasi.
- **POST `/products/ingredient`:** Ingredient restock yoki yangi ingredient (nom + miqdor).
- **POST `/products`:** Yangi tayyor mahsulot + BoM qatorlari (komponent nomi orqali topish/yaratish).
- **`/products/{product_id}/bom`:** Shu mahsulotning BoM boshqaruvi — mavjud qatorlar, yangi komponent qo‘shish, qator o‘chirish.
- **POST `/products/{product_id}/bom`:** BoM ga yangi qator qo‘shish.
- **POST `/products/{product_id}/bom/{bom_id}/delete`:** BoM qatorini o‘chirish.

**Navbar:** Stock (`/`), Products (`/products`), Orders (`/orders`) — Orders yonida draft buyurtmalar soni **badge** (JavaScript orqali `GET /api/stats`).

**JSON API:** `GET /api/stats` (draft_count), `GET /api/products`, `GET /api/orders`.

### 2.5 Xatolarni qayta ishlash

- **Zaxira yetarli emas:** `InsufficientStockError` — redirect `/orders?error=...`, xabar sahifada ko‘rsatiladi.
- **Buyurtma topilmadi / allaqachon bajarilgan / miqdor noto‘g‘ri:** `ValueError` — redirect `/orders?error=...`.
- **Edit:** Produced buyurtmani tahrirlash mumkin emas (400). Miqdor musbat emas yoki mahsulot noto‘g‘ri bo‘lsa redirect bilan xato.
- **Products/BoM:** Bo‘sh nom, mavjud mahsulot, noto‘g‘ri ingredient va hokazo — redirect bilan `?error=...`.

---

## 3. Texnologiyalar

### 3.1 Backend

| Texnologiya | Versiya / qo‘llanilishi |
|-------------|--------------------------|
| **Python** | 3.10+ |
| **FastAPI** | HTTP routelar, Form, Depends, Query, HTMLResponse, RedirectResponse |
| **Uvicorn** | ASGI server, `--reload` |
| **SQLAlchemy** | 2.x — deklarativ modellar, `select()`, `selectinload`, session boshqaruvi |
| **psycopg2-binary** | PostgreSQL drayveri |
| **python-dotenv** | `.env` dan `DATABASE_URL` |
| **Jinja2** | HTML shablonlar |
| **python-multipart** | Form ma’lumotlari |

### 3.2 Ma’lumotlar bazasi

- **PostgreSQL** — baza: `Choco_factory`. Jadvalyar: `products`, `bill_of_materials`, `manufacturing_orders`. Seed: `scripts/seed_data.py`.

### 3.3 Frontend (UI)

- **HTML5**, **Bootstrap 5** (CDN) — grid, kartalar, jadvallar, alert, tugmalar, formlar.
- **Jinja2** — `base.html`, `index.html`, `orders.html`, `order_edit.html`, `products.html`, `product_new.html`, `product_bom.html`, `macros.html`.
- **JavaScript** — navbar uchun `fetch('/api/stats')` va draft badge ko‘rsatish (minimal, framework yo‘q).

### 3.4 Loyiha tuzilishi (qisqacha)

```
app/
  config.py
  database.py
  main.py
  models/
    product.py
    bill_of_material.py
    manufacturing_order.py
  api/
    routes.py         # Web UI + Products, Orders, Edit, BoM + /api/stats, /api/products, /api/orders
  services/
    produce_service.py
  templates/
    base.html, index.html, orders.html, order_edit.html
    products.html, product_new.html, product_bom.html
    macros.html
scripts/
  init_db.py
  seed_data.py
```

### 3.5 Ishga tushirish skriptlari

- **start_backend.ps1** — venv aktivatsiya, `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
- **start_frontend.ps1** — backend tekshirib, brauzerda ochish (8000 yoki 8001).

---

## 4. Xulosa

| Jihat | Tavsif |
|-------|--------|
| **Mazmun** | Kichik shokolad sexi uchun MRP MVP: mahsulotlar (ingredient + tayyor), BoM boshqaruvi, ishlab chiqarish buyurtmasi, Edit, Produce, inventar logikasi. |
| **Ishlashi** | Bitta atom tranzaksiyada produce; zaxira yetmasa — xato, o‘zgarishsiz; web UI orqali buyurtma yaratish/tahrirlash va Produce; mahsulotlar va BoM CRUD. |
| **Texnologiyalar** | Python, FastAPI, SQLAlchemy 2, PostgreSQL, Jinja2, Bootstrap 5; navbar draft badge uchun /api/stats. |

Loyiha BoM orqali mahsulot–komponent bog‘lanishi, tranzaksiya yordamida yaxlitlik, buyurtmani tahrirlash, mahsulotlar va BoM boshqaruvi, zaxira yetmasligi va boshqa xatolarning qayta ishlanishini qo‘llab-quvvatlaydi.
