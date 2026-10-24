# Replit deployment

Public prototype: [https://wheat-assistant.replit.app](https://wheat-assistant.replit.app). Public three-week processing, approvals, eight-sheet downloads and the simulated handoff were verified on 2026-10-24 MYT. The deployment batch made no provider model requests; configuration availability does not establish model quality.

The cloud entry point keeps the existing workflow, approvals, eight-sheet export and explicitly simulated Orbyte task. The desktop entry point still uses local SQLite. Cloud mode uses Replit PostgreSQL for both JSON records and immutable input/export bytes; local files are an expendable cache. Cloud mode never silently falls back to SQLite.

## Import and configure

1. Use the sanitized ZIP produced by `python scripts/package_replit.py`. Import it as a new Replit project. Keep the existing Status Guard project and its provenance intact. Do not upload `.git`, `.env`, local databases, logs, caches, native bundles or the resource library.
2. Add a Replit PostgreSQL database using the Database tool. Use the platform-provided `DATABASE_URL`; never print or paste its value into code, chat, documentation or screenshots. During publishing create/select the app's production database. Development and production databases are separate; verify the production one explicitly.
3. Run the `wheat cloud` workflow. `.replit` connects the Run button to this explicit shell workflow; an imported project with no workflow may otherwise only print Replit's workflow-configuration hint. It builds with Python 3.12+, uv, Node.js 22 and the committed locks. The app listens on `0.0.0.0:3000`; port 3000 is the only exposed application port. Use the direct preview URL in a new tab, because browser privacy rules can block cookies inside an embedded preview. Keep account-specific workflow `author` fields out of upload archives.
4. Publish as **one Reserved VM instance with one application worker**. It serves the built React UI and FastAPI from the same origin. Confirm the chosen public hostname is `wheat-assistant.replit.app`, or change `WHEAT_PUBLIC_HOSTS` to the exact chosen hostname before publishing. The runtime also accepts the exact platform-injected `REPLIT_DOMAINS` and `REPLIT_DEV_DOMAIN`. Wildcards are not accepted.
5. Verify `/healthz` and run the three-week journey from README. Download a workbook, restart the deployment, reopen it in the same browser, then check the saved run and identical download. Test a second browser separately: it must not see or download the first browser's objects.

## Browser workspaces and limits

Each browser starts an independent workspace through a same-origin session request. Its random 256-bit bearer cookie is Secure, HttpOnly, host-only and SameSite=Lax; the server stores only its SHA-256 identifier. All records and blobs are filtered by that workspace. The cookie lasts 14 days; clearing it or changing browsers starts a different workspace. This is an anonymous synthetic demo, not an authenticated production tenant system. Only synthetic business data belongs here.

The demo allows 100 browser workspaces, 64 MiB of combined stored content per workspace, 1,500 records per workspace and 180 API requests per minute per workspace. A workspace processes one mutation at a time; saved-state reads remain available while a run or export is working. Existing per-file, row, worker CPU, memory and timeout limits still apply. Database outages return a generic error without database connection details. Raw account information and request access logs are not published.

Files are committed to PostgreSQL before their entity is exposed; an export is durably stored before its approval transaction marks it ready. A failed or interrupted export stays visible and can be retried. Startup marks unfinished runs/exports interrupted. These recovery rules require one application instance; do not increase the deployment instance or worker count.

## Optional live AI

The user selected live AI for the online version. The three settings `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` have been saved through Replit Secrets by an explicitly authorized operator; the public UI reports API configured. For another deployment, set your own values there. Never upload the local `.env` or send the key through chat. Before those settings exist, the UI honestly shows no configured API and the editable setup remains usable.

The Replit configuration limits provider attempts to four per browser workspace per UTC day and twenty for the whole application per UTC day. Each JSON repair consumes another attempt. The shared counter is stored in PostgreSQL and survives restarts and new browser sessions; it is reserved before any HTTP provider request. `WHEAT_CLOUD_DAILY_CALL_LIMIT` can lower the shared limit and is capped at sixty. These are request limits, not a guaranteed currency budget. Existing live-model quality limitations in ACCEPTANCE.md remain; deploying does not resolve or reclassify them. This deployment batch makes zero external model calls.

## Deployment status and rollback

The public URL above has been verified; it can be used in the submission's Live Prototype URL field. Keep the final source archive SHA-256, actual production database checks and restart result in the engineering record. Repository commit, source push, deployment and official submission are separate states.

Replit publishing/compute/database consume account resources. Review the actual estimate and available Core credits in the Publishing UI; do not enable paid add-ons or automatic credit reload for this demo. Auto-reload being off is not a hard spending cap: accounts may use repayable [grace credits](https://replit.com/help/answers/what-are-grace-credits). Check the account's actual budget controls.

To stop VM billing after the review and freeze requirements permit it, use the deployment's **Shut Down** control. **Pause** makes the app inaccessible while VM billing continues, as described in [Replit's deployment management guide](https://docs.replit.com/cloud-services/deployments/monitoring-a-deployment). Preserve the production database unless removal is separately authorized; storage can have its own charges. To roll back application code, republish a previously verified source snapshot with the same Secrets and production database, without importing development data. Desktop data is unaffected by cloud deployment.
