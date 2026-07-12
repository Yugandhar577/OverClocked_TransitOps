# Location privacy and deployment notes

TransitOps collects driver location only after explicit browser permission and an explicit **Start tracking** action. Collection is scoped to the active assigned trip, visibly indicated on the driver page, and can be paused or ended when policy allows. Trip completion, cancellation, and logout terminate active tracking sessions.

## Access controls

- Fleet managers/administrators can manage tracking and geofences.
- Dispatchers and safety officers receive operational views limited by server-side role/region policy.
- Drivers see their own active vehicle by default; expanded visibility is controlled by workspace policy and locations of other vehicles are rounded.
- Financial analysts have no tracking permissions, including SSE access.

All associations are resolved on the server from the bearer identity and current trip assignment. Location payloads cannot override the driver, vehicle, or trip. Raw point retention is configurable and cleanup runs at application startup. Audit records cover important tracking lifecycle changes.

## Production requirements

- Serve the web app and API over HTTPS. The API rejects tracking requests without HTTPS when `ENVIRONMENT=production`.
- Replace seeded demo tokens with a production identity provider and short-lived signed credentials.
- Keep routing/map secrets in a secret manager. Never use an unrestricted server key in browser code.
- Add Redis/pub-sub for horizontally scaled SSE delivery and a scheduled retention worker.
- Review retention, employee notice/consent, access logs, incident response, and local privacy/employment laws before deployment.

Mobile browsers can suspend geolocation while the phone is locked, the page is backgrounded, or battery saving is enabled. This web implementation surfaces that limitation; guaranteed background collection requires a native application and platform-specific permission review.
