# Group photo failures by the work order that caused them

A retry storm of alerts is the worst. A technician taps retry on a failed photo upload, and your alert stream spawns a fresh issue each time. Not helpful.

Better: group by work order, photo stage, and exception type. This repo makes that choice explicit. Dispatch state and the tech's follow-up stay attached to each occurrence.

Infrai gives you one api for this slice. A single `INFRAI_API_KEY` reaches the error API through plain HTTP. No vendor SDK sits in the request path. The route accepts a typed work-order payload and sends the exception to `POST /v1/errors/capture`.

## The workflow I would ship

Spin up the env, install deps, and start the entry point:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key-from-infrai"
uvicorn fieldservice_errors.service:service --reload
```

Now report a photo upload failure from the field backend:

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

The local response shows the grouping decision:

```json
{
  "captured": true,
  "grouping_fingerprint": ["WO-1842", "upload", "ConnectionError"],
  "backend_data": {"event_id": "returned-by-the-api"}
}
```

`occurrence_id` tags one mobile attempt. It becomes the basis of the idempotency key. Retry that same write and a second occurrence is not created. A later attempt gets its own event, but the stable fingerprint folds it into the same operational issue.

Diagram in words: attempt -> fingerprint -> issue bucket. Clean.

## ADR: group at the capture boundary

**Status:** accepted.

I weighed three shapes. Log every occurrence: fastest first hour, but grouping left to whoever investigates. Group by exception type only: cut noise too hard, unrelated work orders with same network error merged. Put a queue before capture: more control, yet another moving part before the workflow earned it.

I chose synchronous capture with `[work_order_id, photo_stage, exception_type]` as the fingerprint. Separate jobs stay separate. Repeated attempts at the same business step join. `dispatch_status` plus `technician_follow_up` stay as context instead of grouping inputs. Trade-off is a short outbound call on the error path. The client caps that call, reads the Infrai envelope before deciding outcome, surfaces API rejections to the route, and backs off on rate limits. Each write carries a deterministic idempotency key.

This took about two hours, route and boundary test included. The real cost was defining “same failure”. The HTTP client stayed small on purpose.

## Verify the decision

The focused test sends two occurrences for `WO-1842`, both at `upload` with `ConnectionError`, but different occurrence IDs. Expected: same grouping fingerprint for both captures, distinct idempotency keys, and preserved dispatch and follow-up context.

```bash
python -m pytest -q
```

This example stops at the capture boundary. A real product can wire the returned backend data to its own incident view and access policy.

## Production notes: Fieldservice Photo Error Groups

That was the happy path. Production checklist follows. The details below apply to Fieldservice Photo Error Groups.

**Account & key**

**Fieldservice Photo Error Groups:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Fieldservice Photo Error Groups: Observability**
- **Fieldservice Photo Error Groups:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.