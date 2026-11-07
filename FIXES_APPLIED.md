# FDR Portal Fixes Applied

This file records changes made during the ZIP-based repair pass.

## Frontend/backend contract corrections
- Instrument list filters translate `bank` to `issuing_bank` and `skip` to `offset`; unsupported `institution_id` and `expiring_within_days` query parameters are not sent.
- Lifecycle transitions now submit multipart form fields, matching the FastAPI `Form(...)` endpoint.
- Renewal initiation now calls `/renewals/{instrument_id}/initiate` and sends `review_observations`.
- Replacement registration now sends the backend's required query parameters; a registration form is available in the renewals queue.
- Renewal decisions now send `remarks`.
- Release submissions now send the backend-required `reason` and checklist object.
- Release decisions now send the backend's supported decision vocabulary and checklist object. The UI no longer implies a separate officer/final-approver stage that the current API does not implement.
- Notifications now use `/notifications/generate`, `/notifications/read-all` (PUT), and `is_read=false`.
- Dashboard response now includes bank counts and uses the same upcoming-maturity field names as the frontend. The frontend maps KPI aliases to the backend response.

## Release workflow alignment
- Release UI reads backend fields (`review_status`, `instrument_number`, `institution_name`) rather than legacy nested DTO fields.
- Checklist keys now match the backend prototype checklist. Approval will be blocked until mandatory checklist items are marked satisfied.

## Validation status
- Python source syntax compilation passed (`python -m compileall -q app`).
- Full backend tests could not start because the current execution environment does not have the `imagehash` package installed. It is already listed in `backend/requirements.txt`.
- Frontend dependency installation did not finish within the available execution window, so TypeScript/Vite build validation remains outstanding.
- These changes have not been deployed or pushed to GitHub. This is a locally modified project archive.
- External bank/registry responses remain simulated. This is a demo prototype, not a live bank-connected or production-ready deployment.
