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
| **Mahsulotlar (Products)** | Ingredientlar va tayyor mahsulotlar — nom va "Qoldiq (Stock on Hand)". |
| **Materiallar ro‘yxati (BoM)** | "Qora shokolad"ni tarkibiy qismlariga (Kakao, Shakar) va har birining miqdoriga bog‘lash. |
| **Ishlab chiqarish buyurtmasi (MO)** | X dona shokolad ishlab chiqarish buyurtmasi yaratish va **Produce** orqali bajarish. |
| **Produce jarayoni** | Zaxira yetarli bo‘lsa — ingredientlarni ayirib, tayyor mahsulot qo‘shish; yetarli bo‘lmasa — xato ko‘rsatish va hech qanday o‘zgarish kiritmaslik. |

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
│  Brauzer (Bootstrap 5 UI)                                    │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP GET/POST
┌───────────────────────────▼─────────────────────────────────┐
│  FastAPI (app.main)                                          │
│  ├── app.api.routes — sahifalar: /, /orders, /orders/{id}/produce
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
- **bill_of_materials** — BoM: qaysi tayyor mahsulot (`finished_product_id`) uchun qaysi komponent (`component_id`) va **bitta birlik uchun** necha o‘lchov (`quantity_per_unit`). Masalan: Qora shokolad → Kakao 50 g, Shakar 20 g.
- **manufacturing_orders** — ishlab chiqarish buyurtmasi: qaysi mahsulotdan (`product_id`), nechta (`quantity`), holat (`draft` / `produced`), `created_at`, `produced_at`.

BoM orqali **Product ↔ BillOfMaterial** bog‘lanishi: bitta tayyor mahsulot bir nechta BoM qatoriga ega bo‘lishi mumkin (har biri bitta komponent va miqdor bilan). Shuning uchun turli miqdorlar (50 g, 20 g va hokazo) to‘liq qo‘llab-quvvatlanadi.

### 2.3 "Produce" jarayoni (tranzaksiya va validatsiya)

`produce_order(mo_id)` quyidagicha ishlaydi:

1. **Tranzaksiya:** Barcha o‘zgarishlar `transactional_session()` kontekstida bajariladi. Har qanday istisno (xato) yuz berganda `rollback` — bazada hech narsa o‘zgarmaydi.
2. **Buyurtmani yuklash:** MO, uning mahsuloti va shu mahsulotning BoM qatorlari (komponentlar bilan) birga olinadi.
3. **Tekshiruvlar:**
   - MO mavjudmi, allaqachon `produced` emasmi, `quantity > 0` mi?
   - Mahsulotda BoM bormi?
   - Har bir komponent uchun: `kerak = quantity_per_unit * mo.quantity`, `mavjud = component.stock_on_hand`. Agar `mavjud < kerak` bo‘lsa — `InsufficientStockError` (qisqacha shortfalls ro‘yxati bilan).
4. **O‘zgarishlar (faqat barcha tekshiruvlar o‘tsa):**
   - Har bir komponentning `stock_on_hand` dan kerak miqdor ayiriladi (keyin yana bir marta manfiy bo‘lishi tekshiriladi).
   - Tayyor mahsulotning `stock_on_hand` ga `mo.quantity` qo‘shiladi.
   - MO holati `produced`, `produced_at` yangilanadi.
5. **Commit:** Faqat barcha qadamlar muvaffaqiyatli bo‘lsa tranzaksiya commit qilinadi; aks holda — rollback, inventar o‘zgarmaydi.

Natija: **"Yoki hammasi, yoki hech narsa"** — yarim qolgan holat (masalan, shakar ayirildi, shokolad qo‘shilmadi) yuzaga kelmaydi.

### 2.4 Web interfeys va foydalanuvchi oqimi

- **`/` (Bosh sahifa):** Barcha mahsulotlar qoldig‘i va so‘nggi ishlab chiqarish buyurtmalari jadvali. Draft buyurtmalarda **Produce** tugmasi. Muvaffaqiyat/xato xabarlari `?produced=1` yoki `?error=...` orqali ko‘rsatiladi.
- **`/orders`:** Barcha buyurtmalar ro‘yxati va **yangi buyurtma yaratish** formasi (mahsulot tanlash + miqdor). Yana shu yerdan **Produce** bosish mumkin.
- **POST `/orders`:** Formadan `product_id` va `quantity` qabul qilinadi, yangi draft MO yaratiladi, `/orders` ga redirect.
- **POST `/orders/{mo_id}/produce`:** `produce_order(mo_id)` chaqiriladi. Muvaffaqiyatda `/?produced=1`, xatoda `/?error=...` ga redirect (xabar URL-da kodlanadi va sahifada dekodlanib ko‘rsatiladi).

Shuningdek, **ixtiyoriy JSON API:** `GET /api/products`, `GET /api/orders` — mahsulotlar va buyurtmalar ro‘yxati.

### 2.5 Xatolarni qayta ishlash

- **Zaxira yetarli emas:** `InsufficientStockError` — qaysi komponentda qancha kerak, qancha bor ekani xabarda va shortfalls ro‘yxatida. Redirect orqali foydalanuvchiga ko‘rsatiladi.
- **Buyurtma topilmadi / allaqachon bajarilgan / miqdor noto‘g‘ri:** `ValueError` — xabar redirect orqali sahifada chiqadi.
- **Forma validatsiyasi:** Miqdor musbat emas yoki mahsulot topilmasa HTTP 400/404 va xabar.

---

## 3. Texnologiyalar

### 3.1 Backend

| Texnologiya | Versiya / qo‘llanilishi |
|-------------|--------------------------|
| **Python** | 3.10+ |
| **FastAPI** | 0.109.x — HTTP routelar, Form, Depends, HTMLResponse, RedirectResponse |
| **Uvicorn** | ASGI server, `--reload` rejimida ishlatiladi |
| **SQLAlchemy** | 2.x — deklarativ modellar, `select()`, `selectinload`, session boshqaruvi |
| **psycopg2-binary** | PostgreSQL drayveri |
| **python-dotenv** | `.env` dan `DATABASE_URL` o‘qish |
| **Jinja2** | HTML shablonlar (FastAPI orqali) |
| **python-multipart** | Form ma’lumotlari (Form(...)) uchun |

### 3.2 Ma’lumotlar bazasi

- **PostgreSQL** — loyiha bazasi: `Choco_factory`.
- Ulanish: `DATABASE_URL` (`.env` yoki default: `postgresql://postgres:***@localhost:5432/Choco_factory`).
- Jadvalyar: `products`, `bill_of_materials`, `manufacturing_orders` — `scripts/init_db.py` orqali `Base.metadata.create_all()` bilan yaratiladi.
- Dastlabki ma’lumotlar: `scripts/seed_data.py` — mahsulotlar va BoM qatorlari.

### 3.3 Frontend (UI)

- **HTML5** — semantik struktura.
- **Bootstrap 5** — CDN orqali: grid, kartalar, jadvallar, alert, tugmalar, formlar.
- **Jinja2** — `base.html`, `index.html`, `orders.html`; bloklar va tsikllar.
- Alohida JavaScript framework yo‘q — oddiy formlar va redirectlar.

### 3.4 Loyiha tuzilishi (qisqacha)

```
app/
  config.py           # DATABASE_URL
  database.py         # engine, SessionLocal, get_db, transactional_session
  main.py             # FastAPI app, router ulash
  models/
    product.py        # Product (ingredient / finished_good)
    bill_of_material.py # BillOfMaterial (finished_product_id, component_id, quantity_per_unit)
    manufacturing_order.py # ManufacturingOrder (product_id, quantity, status)
  api/
    routes.py         # Web UI + /api/products, /api/orders
  services/
    produce_service.py # produce_order(), InsufficientStockError
  templates/          # base, index, orders
scripts/
  init_db.py          # Jadvalyar yaratish
  seed_data.py        # Mahsulotlar va BoM seed
```

### 3.5 Ishga tushirish skriptlari

- **start_backend.ps1** — venv aktivatsiya, `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
- **start_frontend.ps1** — backend javob beryaptimi tekshirib, `http://127.0.0.1:8000` ni brauzerda ochadi.

---

## 4. Xulosa

| Jihat | Tavsif |
|-------|--------|
| **Mazmun** | Kichik shokolad sexi uchun MRP MVP: mahsulotlar, BoM, ishlab chiqarish buyurtmasi va inventar logikasi. |
| **Ishlashi** | Bitta atom tranzaksiyada produce; zaxira yetmasa — xato, o‘zgarishsiz; oddiy web UI orqali buyurtma yaratish va Produce. |
| **Texnologiyalar** | Python, FastAPI, SQLAlchemy 2, PostgreSQL, Jinja2, Bootstrap 5; PowerShell skriptlar orqali lokal test. |

Loyiha texnik talablarga javob beradi: BoM orqali mahsulot–komponent bog‘lanishi va har bir qator uchun miqdor, tranzaksiya yordamida yaxlitlik, aniq nomlar va modullar, zaxira yetmasligi va boshqa xatolarning to‘g‘ri qayta ishlashi.
