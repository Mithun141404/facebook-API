# Facebook CRM API

Standalone Python REST API for Facebook Graph API integration.
Consumed by the Laravel CRM backend as a microservice.

## Stack
- **FastAPI** — REST framework
- **SQLAlchemy 2 (async)** — ORM with SQLite (dev) / PostgreSQL (prod)
- **httpx** — Async HTTP client for Facebook Graph API calls
- **Fernet** — Access token encryption at rest

## Quick Start

```bash
# 1. Clone / navigate to project
cd /home/legend/Desktop/facebook-api

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies (Python 3.14 note: uses pre-release pydantic)
pip install --pre pydantic pydantic-settings
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set API_KEY, and generate TOKEN_ENCRYPT_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 5. Run dev server
venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API Docs
- Swagger UI: http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc
- Health:      http://localhost:8000/health

## Authentication
All endpoints (except `/health`) require:
```
X-API-Key: <your API_KEY from .env>
```

## Endpoints

### Page Configs
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/page-configs` | List all page configs |
| POST | `/api/v1/page-configs` | Create page config |
| GET | `/api/v1/page-configs/{id}` | Get single config |
| PUT | `/api/v1/page-configs/{id}` | Update config |
| DELETE | `/api/v1/page-configs/{id}` | Delete config |
| POST | `/api/v1/page-configs/{id}/fetch` | Fetch posts for this page |
| POST | `/api/v1/page-configs/fetch-all` | Fetch posts for all active pages |

### Posts
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/posts` | List posts (filter: page_config_id, campaign_id, active) |
| GET | `/api/v1/posts/{id}` | Get post with comments |
| PUT | `/api/v1/posts/{id}/campaign` | Assign post to campaign |
| DELETE | `/api/v1/posts/{id}` | Soft-delete post |
| GET | `/api/v1/posts/{id}/comments` | List comments for a post |

### Campaigns
| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/v1/campaigns` | List all campaigns |
| POST | `/api/v1/campaigns` | Create campaign |
| GET | `/api/v1/campaigns/{id}` | Get campaign |
| PUT | `/api/v1/campaigns/{id}` | Update campaign |
| DELETE | `/api/v1/campaigns/{id}` | Delete campaign |
| GET | `/api/v1/campaigns/{id}/stats` | Live stats (likes, comments, posts) |

### Publish
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/v1/publish/text` | Publish text post (Form data) |
| POST | `/api/v1/publish/photo` | Publish photo post (multipart file upload) |

## CRM Integration (Laravel)

Add to `crmbackend/.env`:
```env
FACEBOOK_API_URL=http://localhost:8000
FACEBOOK_API_KEY=facebook-crm-dev-key-2025
```

Example Laravel call:
```php
use Illuminate\Support\Facades\Http;

// Fetch posts for page config ID 1
$response = Http::withHeaders(['X-API-Key' => env('FACEBOOK_API_KEY')])
    ->post(env('FACEBOOK_API_URL') . '/api/v1/page-configs/1/fetch');

// Publish a text post
$response = Http::withHeaders(['X-API-Key' => env('FACEBOOK_API_KEY')])
    ->asForm()
    ->post(env('FACEBOOK_API_URL') . '/api/v1/publish/text', [
        'page_config_id' => 1,
        'message' => 'Hello from CRM!',
    ]);

// Publish a photo
$response = Http::withHeaders(['X-API-Key' => env('FACEBOOK_API_KEY')])
    ->attach('image', file_get_contents($imagePath), 'photo.jpg')
    ->post(env('FACEBOOK_API_URL') . '/api/v1/publish/photo', [
        'page_config_id' => 1,
        'caption' => 'Check this out!',
    ]);
```
