"""Verify browser capture, worker processing, evidence playback, and workspace isolation."""

import hashlib
import json
import os
import secrets
import time
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright


def credentials(token_a: str, token_b: str) -> str:
    return json.dumps({
        hashlib.sha256(token.encode()).hexdigest(): {"user_id": user, "workspace_id": str(uuid4())}
        for token, user in [(token_a, "recorder"), (token_b, "other-workspace")]
    }, separators=(",", ":"))


def configure_ci() -> None:
    token_a, token_b = (secrets.token_urlsafe(32) for _ in range(2))
    with open(os.environ["GITHUB_ENV"], "a") as env_file:
        env_file.write(f"SMOKE_TOKEN_A={token_a}\nSMOKE_TOKEN_B={token_b}\n")
        env_file.write(f"PROHUMAN_CREDENTIALS={credentials(token_a, token_b)}\n")


def run() -> None:
    origin = "http://127.0.0.1:3000"
    auth = lambda name: {"Authorization": "Bearer " + os.environ[name]}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=[
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
        ])
        page = browser.new_page(permissions=["microphone"])
        page.add_init_script("""
            const NativeSocket = window.WebSocket;
            window.WebSocket = class extends NativeSocket {
                constructor(url, protocols) {
                    super(url, protocols);
                    if (!String(url).includes('/audio/stream/')) return;
                    this.addEventListener('message', ({data}) => {
                        if (!window.captureInterrupted && JSON.parse(data).type === 'ack') {
                            window.captureInterrupted = true;
                            this.close(4001, 'Smoke test disconnect');
                        }
                    });
                }
            };
        """)
        page.goto(origin)
        page.get_by_label("Workspace access token").fill(os.environ["SMOKE_TOKEN_A"])
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_role("button", name="Record", exact=True).click()
        page.wait_for_function("window.captureInterrupted === true")
        expect(page.get_by_text("Recording audio…", exact=True)).to_be_visible(timeout=15000)
        page.get_by_role("button", name="Stop & AI").click()
        expect(page.get_by_text("Recording saved. Transcription is queued.")).to_be_visible(timeout=30000)

        list_response = page.request.get(origin + "/api/v1/sessions", headers=auth("SMOKE_TOKEN_A"))
        assert list_response.ok, list_response.text()
        session, = list_response.json()["sessions"]
        session_id = session["id"]
        detail_path = origin + "/api/v1/sessions/" + session_id
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            response = page.request.get(detail_path, headers=auth("SMOKE_TOKEN_A"))
            assert response.ok, response.text()
            detail = response.json()
            if detail["status"] == "COMPLETED":
                break
            assert "failed" not in detail["pipeline_stages"].values(), detail["pipeline_stages"]
            time.sleep(1)
        else:
            raise RuntimeError("Recording did not reach all processing stages")

        play = origin + f"/api/v1/audio/{session_id}/playback"
        playback = page.request.get(play, headers={**auth("SMOKE_TOKEN_A"), "Range": "bytes=0-3"})
        assert playback.status == 206
        assert playback.body() == b"\x1a\x45\xdf\xa3", "Expected a WebM recording"
        assert page.request.get(play, headers=auth("SMOKE_TOKEN_B")).status == 404
        assert page.request.get(detail_path, headers=auth("SMOKE_TOKEN_B")).status == 404
        assert page.request.get(
            origin + f"/api/v1/export/{session_id}/mom", headers=auth("SMOKE_TOKEN_B"),
        ).status == 404
        assert page.request.patch(
            detail_path, headers=auth("SMOKE_TOKEN_B"), data={"metadata": {"label": "Blocked"}},
        ).status == 404

        search = origin + "/api/v1/search"
        for token_name, expected in [("SMOKE_TOKEN_A", 1), ("SMOKE_TOKEN_B", 0)]:
            result = page.request.post(search, headers=auth(token_name), data={
                "query": "budget", "search_mode": "LEXICAL",
            })
            assert result.ok, result.text()
            assert result.json()["total_count"] == expected

        page.get_by_role("button", name="Transcript & MOM").click()
        expect(page.get_by_text("Send the budget", exact=True)).to_be_visible(timeout=20000)
        page.get_by_role("button", name="Play at 0:00").click()
        audio = page.locator("audio")
        expect(audio).to_be_visible(timeout=15000)
        page.wait_for_function("document.querySelector('audio')?.currentTime >= 0.20")
        page.get_by_role("button", name="Edit", exact=True).click()
        page.get_by_label("Assignee", exact=True).fill("Mira Chen")
        page.get_by_role("button", name="Save changes").click()
        expect(page.get_by_text("Mira Chen", exact=False)).to_be_visible()
        exported = page.request.get(origin + f"/api/v1/export/{session_id}/mom", headers=auth("SMOKE_TOKEN_A"))
        assert exported.ok and exported.json()["action_items"][0]["assignee"] == "Mira Chen"
        browser.close()


if __name__ == "__main__":
    if os.environ.get("CONFIGURE_RELEASE_SMOKE"):
        configure_ci()
    else:
        run()
