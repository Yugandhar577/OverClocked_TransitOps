"""Generate predictable live coordinates for the seeded active fleet.

Run only in development:
    python scripts/simulate_tracking.py --steps 30 --interval 2
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import os
from uuid import uuid4

import httpx


DRIVERS = [
    ("driver@transitops.demo", (23.0225, 72.5714), (22.3072, 73.1812)),
    ("driver.meera@transitops.demo", (23.0225, 72.5714), (22.9924, 72.3815)),
    ("driver.vikram@transitops.demo", (23.0225, 72.5714), (22.6916, 72.8634)),
]


async def simulate(base_url: str, steps: int, interval: float, exercise_pause: bool) -> None:
    if os.getenv("ENVIRONMENT", "development") == "production":
        raise SystemExit("The GPS simulator is disabled in production.")
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        sessions: list[tuple[dict[str, str], str, tuple[float, float], tuple[float, float]]] = []
        for email, start, end in DRIVERS:
            login = await client.post("/auth/login", json={"email": email, "password": "demo"})
            login.raise_for_status()
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            started = await client.post("/tracking/sessions/start", headers=headers, json={"consent": True, "consent_version": "simulator-1"})
            started.raise_for_status()
            sessions.append((headers, started.json()["id"], start, end))

        for step in range(steps):
            ratio = step / max(steps - 1, 1)
            if exercise_pause and step == steps // 3:
                await asyncio.gather(*(client.post(f"/tracking/sessions/{session_id}/pause", headers=headers) for headers, session_id, _, _ in sessions))
                await asyncio.sleep(interval)
                await asyncio.gather(*(client.post(f"/tracking/sessions/{session_id}/resume", headers=headers) for headers, session_id, _, _ in sessions))
            requests = []
            for headers, _, start, end in sessions:
                latitude = start[0] + (end[0] - start[0]) * ratio
                longitude = start[1] + (end[1] - start[1]) * ratio
                payload = {"idempotency_key": f"sim-{uuid4().hex}", "latitude": latitude, "longitude": longitude, "accuracy_meters": 8, "heading_degrees": 90, "speed_mps": 11 if step < steps - 1 else 0, "captured_at": datetime.now(UTC).isoformat(), "is_mock_location": True, "metadata": {"simulator_step": step, "simulator_steps": steps}}
                requests.append(client.post("/tracking/locations", headers=headers, json=payload))
            responses = await asyncio.gather(*requests)
            for response in responses:
                response.raise_for_status()
            print(f"Sent simulator step {step + 1}/{steps}")
            await asyncio.sleep(interval)

        await asyncio.gather(*(client.post(f"/tracking/sessions/{session_id}/end", headers=headers) for headers, session_id, _, _ in sessions))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate three TransitOps driver phones.")
    parser.add_argument("--base-url", default="http://localhost:8000/api")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--exercise-pause", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(simulate(arguments.base_url, arguments.steps, arguments.interval, arguments.exercise_pause))
