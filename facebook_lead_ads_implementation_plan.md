# Facebook Lead Ads Integration - Implementation Plan

## 1. Overview
This plan outlines the integration of Facebook Lead Ads into the FastAPI middleware service. The goal is to capture leads generated from Facebook Lead Ads (associated with specific campaigns), fetch the user-submitted form details, and securely transmit this data to the main CRM backend.

## 2. Facebook App & Page Configuration
To access Lead Ads data, the following configurations are required on the Facebook Developer portal:
- **Permissions:** The Facebook App must be granted the `leads_retrieval` permission (requires App Review) along with `pages_read_engagement` and `pages_show_list`.
- **System User/Access Token:** Ensure the Page Access Token used has the appropriate scopes to read leads.
- **Webhooks (Recommended for Real-time):** Subscribe the app to the Page's `leadgen` field. This allows Facebook to push a notification to our API the moment a user submits a form.

## 3. FastAPI Implementation Steps

### Phase 3.1: Webhook Endpoints (Real-time Lead Notifications)
Create a new router (e.g., `api/v1/webhooks.py`) to handle Facebook webhooks.
- **GET `/webhooks/facebook`:** 
  - Required by Facebook to verify the webhook subscription (handles `hub.mode`, `hub.challenge`, and `hub.verify_token`).
- **POST `/webhooks/facebook`:** 
  - Receives the real-time payload when a form is submitted.
  - The payload will contain a `leadgen_id` (the ID of the specific lead) and the `form_id`.

### Phase 3.2: Fetching Lead Details (Graph API)
Create a service function in `services/facebook.py` to fetch the actual user data.
- **Function:** `get_lead_details(lead_id: str, page_access_token: str)`
- **Graph API Endpoint:** `GET https://graph.facebook.com/v19.0/{lead_id}`
- **Processing:** The API will return the field data (e.g., email, full_name, phone_number). This data needs to be parsed into a structured Pydantic model.

### Phase 3.3: Manual Sync / Polling (Fallback Mechanism)
For cases where webhooks might fail, or to do historical syncs, implement a manual sync endpoint in `api/v1/campaigns.py`.
- **Endpoint:** `POST /api/v1/campaigns/{campaign_id}/sync-leads`
- **Workflow:** 
  1. Fetch forms for the page/ad: `GET /{page_id}/leadgen_forms`
  2. Fetch leads for the form: `GET /{form_id}/leads`
  3. Filter leads by time or ID to process new ones.

## 4. CRM Backend Integration (Laravel)
Since this FastAPI service acts as middleware, it needs to forward the fetched lead data to the Laravel backend.
- Once the lead data is parsed, make an HTTP POST request to the Laravel CRM webhook/API endpoint (e.g., `/api/facebook/leads`).
- **Payload mapping:** Ensure the lead is associated with the correct Campaign in the CRM. The Facebook webhook/API provides `ad_id` and `adgroup_id`, which can be mapped to our internal CRM `campaign_id`.

## 5. Security & Error Handling
- **App Secret Proof:** Consider enabling App Secret Proofing for Graph API calls to enhance security.
- **Webhook Signature Validation:** Validate the `X-Hub-Signature` header in the POST webhook using the Facebook App Secret to ensure the payload actually came from Facebook.
- **Rate Limiting & Retries:** Implement retry logic for network failures when fetching lead details or pushing to the CRM.

## 6. Next Actions (When ready to build)
1. Update `.env` to include `FB_APP_SECRET` and `FB_WEBHOOK_VERIFY_TOKEN`.
2. Add Pydantic schemas for Webhook Payloads and Lead Data.
3. Scaffold the `webhooks.py` router.
4. Add the `get_lead_details` method to `services/facebook.py`.
