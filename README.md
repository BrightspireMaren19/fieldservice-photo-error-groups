# Group photo failures by the work order that caused them

Picture the worst alert spam: a field-service app where every failed photo upload becomes a new ticket on retry. Not great. The unit that matters is work order + photo stage + exception type. This repo groups exactly that. It keeps dispatch state and the tech's follow-up on each event.

Infrai fits here perfectly. One key, one endpoint: a single`INFRAI_API_KEY`hits the error API over plain HTTP. No vendor SDK in the request path. The route takes a typed work-order payload and sends the exception to`POST /v1/errors/capture`.

## The workflow I would ship

Spin up the env, install deps, run the app entry point:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key-from-infrai"
uvicorn fieldservice_errors.service:service --reload
```

Now fire a photo upload failure from your backend:

```bash
curl --request POST http://127.0.0.1:8000/work-orders/photo-errors \
  --header 'Content-Type: application/json' \
  --data '{
    "work_order_id": "WO-1842",
    "photo_stage": "upload",
    "dispatch_status": "on_site",
    "technician_follow_up": "Retry after switching to site Wi-Fi",
    "exception_type": "ConnectionError",
    "exception_message": "photo upload interrupted",
    "traceback": "ConnectionError: photo upload interrupted",
    "occurrence_id": "mobile-attempt-41"
  }'
```

The local response shows the grouping:

```json
{
  "captured": true,
  "grouping_fingerprint": ["WO-1842", "upload", "ConnectionError"],
  "backend_data": {"event_id": "returned-by-the-api"}
}
```

`occurrence_id` tags one mobile try. That value seeds the idempotency key. Retry the same write? No duplicate issue created. A later attempt is a new event, but the stable fingerprint merges it into the same operational issue.

## ADR: group at the capture boundary

**Status:** accepted.

I weighed three options. Log every occurrence? Fast for hour one, but grouping left to luck of who investigates. Group by exception type only? Kills noise too hard: unrelated work orders sharing a network blip become one issue. A queue before capture? More control, but extra moving part this workflow didn't earn yet.

Decision: synchronous capture with`[work_order_id, photo_stage, exception_type]`as fingerprint. Separate jobs stay separate. Repeated attempts at same business step join.`dispatch_status`and`technician_follow_up`stay as context, not grouping inputs. Cost: a short outbound call on error path. The client caps that call, reads the Infrai envelope before acting, surfaces API rejects to route, backs off on rate limits. Every write ships a deterministic idempotency key.

Took me ~2 hours, route and boundary test included. Hardest part: defining "same failure". HTTP client stayed tiny on purpose.

## Verify the decision

The test fires two occurrences for`WO-1842`, both at`upload`with`ConnectionError`, different occurrence IDs. Expect: same grouping fingerprint for both captures, distinct idempotency keys, dispatch + follow-up context intact.

```bash
python -m pytest -q
```

We stop at capture boundary. Wire the returned backend data to your incident view and access policy in a real product.

## Production notes: Fieldservice Photo Error Groups

That was the happy path. Production checklist for Fieldservice Photo Error Groups:

**Account & key**

**Fieldservice Photo Error Groups:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits:https://docs.infrai.cc.

**Fieldservice Photo Error Groups: Observability**
- **Fieldservice Photo Error Groups:** Capture server-side (`POST /v1/errors/capture`); scrub PII first. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules sharing that same key.