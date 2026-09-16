"""Regenerate the README screenshots from a running instance.

Runs the same flow a reader sees in the README — open a source guide, ask a question, open a
citation, save a note — and captures it in light, dark and mobile. Chat and notes of the target
notebook are cleared before and after, so the shots are reproducible and nothing is left behind.

    docker compose -f docker-compose.yml -f docker-compose.override.yml \\
        -f e2e/docker-compose.e2e.yml run --rm \\
        -e E2E_BASE_URL=https://notebook.example.org -e E2E_ACCESS_KEY=... \\
        e2e sh -c "pip install -q playwright==1.55.0 && python screenshots.py"
"""

import os
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = os.environ["E2E_BASE_URL"]
KEY = os.environ["E2E_ACCESS_KEY"]
NOTEBOOK = os.environ.get("SHOTS_NOTEBOOK", "KI im Unternehmen: Recht & Verträge")
QUESTION = os.environ.get("SHOTS_QUESTION", "Was regelt Artikel 50 der KI-Verordnung?")
GUIDE_SOURCE = os.environ.get("SHOTS_SOURCE", "KI-Verordnung")
OUT = Path(os.environ.get("SHOTS_OUT", "/e2e/out/readme"))
CHIP = re.compile(r"^Quelle \d+:")


def step(name: str) -> None:
    print(f"-> {name}", flush=True)


OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    api = p.request.new_context(base_url=BASE, extra_http_headers={"X-Access-Key": KEY})
    notebooks = api.get("/api/notebooks").json()
    notebook = next((n for n in notebooks if n["title"] == NOTEBOOK), None)
    if notebook is None:
        sys.exit(f"notebook {NOTEBOOK!r} not found on {BASE}")

    def reset() -> None:
        api.delete(f"/api/notebooks/{notebook['id']}/messages")
        for note in api.get(f"/api/notebooks/{notebook['id']}/notes").json():
            api.delete(f"/api/notes/{note['id']}")

    reset()
    url = f"{BASE}/#/notebook/{notebook['id']}"

    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    context.add_init_script(f"localStorage.setItem('notebook.accessKey', {KEY!r})")
    page = context.new_page()
    page.goto(url)

    step("source guide in the main column")
    page.get_by_role("button", name=re.compile("^" + re.escape(GUIDE_SOURCE))).first.click()
    guide = page.get_by_role("region", name="Quelle", exact=True)
    expect(guide.get_by_text("QUELLEN-GUIDE")).to_be_visible(timeout=30_000)
    page.screenshot(path=OUT / "guide.png")

    step("ask and save the answer as a note")
    guide.get_by_role("button", name="Zum Chat").click()
    page.get_by_label("Frage").fill(QUESTION)
    page.get_by_label("Senden").click()
    chips = page.get_by_role("button", name=CHIP)
    expect(chips.first).to_be_visible(timeout=120_000)
    page.get_by_role("button", name="Als Notiz speichern").last.click()
    notes = page.get_by_role("region", name="Notizen")
    expect(notes.get_by_text(QUESTION)).to_be_visible()
    # open it: the point of the shot is that the citations stay clickable inside a note
    notes.get_by_text(QUESTION).click()
    expect(notes.get_by_role("button", name=CHIP).first).to_be_visible()
    page.screenshot(path=OUT / "notebook.png")

    step("citation viewer")
    chips.first.click()
    drawer = page.get_by_role("dialog")
    expect(drawer.locator("mark")).to_be_visible()
    page.screenshot(path=OUT / "citation.png")
    page.keyboard.press("Escape")

    step("dark mode")
    dark = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    dark.add_init_script(f"localStorage.setItem('notebook.accessKey', {KEY!r})")
    dark_page = dark.new_page()
    dark_page.goto(url)
    expect(dark_page.get_by_role("button", name=CHIP).first).to_be_visible(timeout=30_000)
    dark_page.screenshot(path=OUT / "dark.png")

    step("mobile")
    mobile = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    mobile.add_init_script(f"localStorage.setItem('notebook.accessKey', {KEY!r})")
    mobile_page = mobile.new_page()
    mobile_page.goto(url)
    expect(mobile_page.get_by_role("region", name="Chat")).to_be_visible(timeout=30_000)
    mobile_page.screenshot(path=OUT / "mobile.png")

    browser.close()
    reset()

print(f"\nScreenshots in {OUT}")
