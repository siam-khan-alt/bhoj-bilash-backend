# Bhoj Bilash — Backend (Django DRF + PostgreSQL)

Staff-only dokan OS API — POS billing, menu/packages, khata, settings.
Contract source of truth: `frontend/types/index.ts` + repo-root `LEARNING_MODULES.md` cheat sheet.

## Setup (local)

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # DB_PASSWORD + SECRET_KEY bosao
createdb -O bhojbilash_user bhojbilash   # postgres superuser hisebe, 1 bar
venv/bin/python manage.py migrate
venv/bin/python manage.py seed_users      # admin@test.com/admin123 + cashier@test.com/cashier123
venv/bin/python manage.py seed_menu       # 28 foods + 2 packages (re-run safe)
venv/bin/python manage.py seed_settingsplus
venv/bin/python manage.py runserver       # :8000
```

Frontend connect (backend age chalate hobe):
```env
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

## Endpoints (Dhap 1-6)

| Frontend fn | Real | Access |
|---|---|---|
| `login()` | `POST /api/auth/login` → `{user, token}` | public |
| `me()` | `GET /api/auth/me` | staff |
| `getFoods/add/update/delete` | `/api/foods` CRUD (list public, write admin) | public/admin |
| `getPackages/...` | `/api/packages?active=1` | public/admin |
| `createOrder()` | `POST /api/orders` (atomic, server-trust price) | staff |
| `getAllOrders/getOrderById` | `GET /api/orders`, `GET /api/orders/:id` | staff |
| `getCustomerOrders(phone)` | `GET /api/orders/by-phone?phone=` | staff |
| `updateOrderStatus()` | `PATCH /api/orders/:id/status` | admin |
| staff/attendance/expenses/salary | `/api/staff`, `/api/attendance...`, `/api/expenses`, `/api/salary...` | admin/staff matrix (tests-e) |
| hisab | `GET /api/hisab/summary?month=YYYY-MM` (1 call, 8 aggregates) | admin |
| config/options/reviews | `GET/PATCH /api/config`, `/api/options?key=`, `/api/reviews` | public GET / admin write |

Field rules: `_id` string, money JSON number, `createdAt` ISO, errors `{message}`.
Enums lowercase: `admin|cashier`, `placed|preparing|delivered|cancelled`, `pending|paid|failed`, `dine_in|parcel|both`.

## 401/403 matrix (Dhap 6 proof — `users/tests.py::test_401_403_matrix_documented`)

| Endpoint | no-token | cashier | admin |
|---|---|---|---|
| `POST /api/foods` | 401 | 403 | 201 |
| `GET /api/staff` | 401 | 403 | 200 |
| `GET /api/hisab/summary` | 401 | 403 | 200 |
| `GET /api/foods` (public) | 200 | 200 | 200 |
| `PATCH /api/orders/:id/status` | 401 | 403 | 200 |

## Query budgets (fixed — `assertNumQueries` in tests)

| Endpoint | Budget | Note |
|---|---|---|
| `POST login` | 1 + JWT | `email` UNIQUE |
| `GET foods` | 2 | COUNT + page rows |
| `GET packages` | 4 | COUNT + pkgs + items + foods |
| `POST orders` | 9 | JWT + bulk fetch + atomic insert + refetch |
| `GET orders` page | 5 | JWT + COUNT + rows + items + foods |
| `GET hisab/summary` | 9 | 8 aggregates + JWT |
| `GET config` | 2 | config + 7 hours |
| `GET options?key=` | 1 | `(list_key,sort)` index |
| `GET reviews/stats` | 1 | AVG/COUNT |

## Security (Dhap 6 pass)

- `.env` git-ignored, never committed; `SECRET_KEY` env-only (prod-e missing hole boot fail kore).
- `config/settings/prod.py`: `DEBUG=False`, `ALLOWED_HOSTS` + `CORS_ALLOWED_ORIGINS` env whitelist (no `*`), `SESSION/CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER`.
- Passwords PBKDF2 (Django default); test settings-e sudhu MD5 (speed).
- Money `DecimalField`, server recompute; `transaction.atomic` on order create; throttle on reviews + login (429 on spam).

## Tests

```bash
venv/bin/python manage.py test --settings=config.settings.test
# 42 tests: auth shape + 401/403 matrix, menu contract + budgets + PROTECT,
# orders wrong-price attack + clamp + atomicity + by-phone, khata math, settings locks/cascade/throttle
```

## Deploy (Render + Neon)

1. Neon/Supabase-e Postgres → `DB_*` env copy koro.
2. Render Web Service: `pip install -r requirements.txt`, start `gunicorn config.wsgi --env DJANGO_SETTINGS_MODULE=config.settings.prod` (ba `daphne` lagbe na).
3. Env set koro: `SECRET_KEY, DEBUG=False, DB_*, ALLOWED_HOSTS=your-api.onrender.com, CORS_ALLOWED_ORIGINS=https://bhoj-bilash.vercel.app`.
4. `migrate + seed_users + seed_menu + seed_settingsplus` 1 bar run koro.
5. Frontend Vercel-e `NEXT_PUBLIC_API_URL=https://your-api.onrender.com/api` set kore rebuild.
6. Smoke check: login → POS bill → hisab mile kina dekho (purono `mock_*` localStorage key thakle clear koro).

Demo creds: `admin@test.com/admin123` (full), `cashier@test.com/cashier123` (POS + khata entry only).
