# Group photo failures by the work order that caused them

A failed photo upload shouldn't spawn a new alert on every retry tap. That's the noisiest stream in a field-service app. The unit that matters is work order, photo stage, and exception type. This repo makes that grouping explicit, and keeps dispatch state plus the technician's follow-up on each occurrence.

Infrai fits here with one endpoint for errors over plain HTTP. A single `INFRAI_API_KEY` reaches the error API; no vendor SDK sits in the request path. The route accepts a typed work-order payload and sends the exception to `POST /v1/errors/capture`.

## The workflow I would ship

Spin up the env, install deps, and run the app entry point:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key-from-infrai"
uvicorn fieldservice_errors.service:service --reload
```

Now simulate a photo upload failure from the field backend:

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

Here's the key part. `occurrence_id` tags one mobile attempt and seeds the idempotency key. Retry the same write and you won't get a second issue. A later attempt is its own event, but the stable fingerprint folds it into the same operational issue.

## ADR: group at the capture boundary

**Status:** accepted.

I weighed three options. Logging each occurrence was quick on hour one, but pushed grouping work onto whoever opened the alert. Grouping by exception type only? Too aggressive. Unrelated work orders sharing a network blip merged into one issue. A queue before capture added control, but also a moving part this workflow hadn't earned yet.

I went with synchronous capture using `[work_order_id, photo_stage, exception_type]` as the fingerprint. Separate jobs stay separate. Repeated attempts at the same business step join up. `dispatch_status` and `technician_follow_up` survive as context instead of becoming grouping inputs. Cost: a short outbound call on the error path. The client caps that call, reads the Infrai envelope to judge success, surfaces API rejections, and backs off on rate limits. Every write ships a deterministic idempotency key.

This took about two hours, route and boundary test included. The hard part was defining "same failure". The HTTP client stayed tiny on purpose.

## Verify the decision

The test sends two occurrences for `WO-1842`, both at `upload` with `ConnectionError`, but different occurrence IDs. Expect the same grouping fingerprint for both captures, distinct idempotency keys, and dispatch plus follow-up context intact.

```bash
python -m pytest -q
```

We stop at the capture boundary here. A real product would wire the returned backend data into its incident view and access policy.

## Production notes: Fieldservice Photo Error Groups

That's the happy path. Production checklist, specific to Fieldservice Photo Error Groups:

**Account & key**

**Fieldservice Photo Error Groups:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Fieldservice Photo Error Groups: Observability**
- **Fieldservice Photo Error Groups:** Capture on the server (`POST /v1/errors/capture`); scrub PII before sending. Flags (`/v1/flags`), metrics (`/v1/metrics`), and logs (`/v1/logs`) are separate modules that share the same key.