# Meta Ads Webhook & Lead Sync Implementation Plan

This plan outlines the requirements specified for the Python FastAPI service, using the Laravel `crmbackend` implementation as a reference point. 

## Open Questions

> [!IMPORTANT]
> 1. **Graph API Fetching vs. Webhook Payload:** The Laravel app's cron job parsed `field_data` directly from the raw webhook payload. However, standard Facebook Lead Ads webhooks usually only send `leadgen_id` and `form_id`, requiring a Graph API call to fetch the actual `field_data`. Should the Python cron job make the Graph API call using the `leadgen_id`, or are you using a custom payload structure that already includes `field_data`?
> 2. **Existing Notification Architecture:** The requirements mention using the "existing notification architecture to broadcast new lead events instantly to the frontend". The current FastAPI codebase only has an email alerting system (`services.email`). Should we implement a FastAPI WebSocket endpoint for real-time frontend notifications, or do you integrate with a service like Redis Pub/Sub, Pusher, or Socket.io?
> 3. **Contact Model:** The Python service currently doesn't have `Contact`, `Phone`, or `Email` tables (unlike the Laravel app). I will add a `Contact` model to store these processed leads. Should we keep it simple (a single `contacts` table with email/phone columns), or replicate the Laravel normalized structure (separate `emails` and `phones` tables)?

---

## Proposed Changes

### 1. Configuration (`config.py` & `.env.example`)
- Add `meta_webhook_secret` (for signature validation).
- Add `meta_verify_token` (for the GET verification challenge).
- Add `sync_cron_interval_minutes` (default: 2, configurable via `.env`).

---

### 2. Database Models (`db/models.py`)
- **`RawLead`:** A table to store the raw webhook payload.
  - Columns: `id`, `lead_id` (unique), `platform` (e.g., facebook, instagram), `form_id`, `ad_id`, `raw_payload` (JSON), `processed` (boolean, default `False`), `error_message` (text), `processed_at`.
- **`Contact`:** A table for the parsed and synced leads.
  - Columns: `id`, `first_name`, `last_name`, `email`, `phone`, `source` (e.g., Facebook, Instagram, LinkedIn, X).

---

### 3. API Contracts (Schemas) (`schemas/webhook.py` & `schemas/contact.py`)
- **`schemas/webhook.py`**: Pydantic models for the incoming Meta webhook payload to ensure type safety.
- **`schemas/contact.py`**: 
  - `ContactOut`: JSON schema for the frontend to consume (includes `id`, `first_name`, `last_name`, `email`, `phone`, `source`, `created_at`).

---

### 4. Meta Webhook Endpoint (`api/v1/webhooks.py`)
- `GET /api/v1/webhooks/meta`: Handles the hub challenge verification.
- `POST /api/v1/webhooks/meta`: 
  1. Validates `X-Hub-Signature-256` using the App Secret.
  2. Extracts the `leadgen_id` and `platform`.
  3. Inserts a new `RawLead` record with `processed=False`.
  4. Returns `200 OK` immediately (no processing done here).

---

### 5. Configurable Data Sync Cron Job (`services/cron.py`)
- Implement an async background task loop (using `APScheduler` or `asyncio` tasks tied to the FastAPI lifespan).
- **Logic (`sync_meta_leads`):**
  1. Fetch `RawLead` records where `processed=False`.
  2. Parse the payload (and fetch `field_data` via Graph API if necessary).
  3. Map the source dynamically based on the platform (`facebook` -> `Facebook`, `instagram` -> `Instagram`, `x` -> `X`, `linkedin` -> `LinkedIn`).
  4. Create the `Contact` record.
  5. Mark `RawLead` as `processed=True`.
  6. Trigger the notification broadcast.

---

### 6. API Delivery Endpoints (`api/v1/contacts.py`)
- `GET /api/v1/contacts`: Endpoint for the frontend to fetch the list of synced contacts, supporting pagination and filtering by `source`.

---

### 7. Notification System (`api/v1/notifications.py` or similar)
- Broadcast the newly created contact to the frontend. (Pending clarification on the preferred architecture: WebSockets vs external service).

## Verification Plan
1. **Webhook Testing:** Use the Meta App Dashboard "Test Webhooks" tool to fire a sample leadgen payload. Verify the signature validation passes and the `RawLead` is stored as unprocessed.
2. **Cron Job Testing:** Verify the background job picks up the unprocessed lead every `X` minutes (based on the `.env`), maps the fields and source correctly, creates a `Contact`, and marks it as processed.
3. **API Contracts:** Generate the OpenAPI (Swagger) JSON and provide it to Adithya to confirm the request/response structures.
