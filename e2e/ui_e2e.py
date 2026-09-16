"""Browser E2E: the core loop from plan.md (upload → guide → question → citation → note).

Fails on any browser console error/warning. Screenshots land in e2e/out/.
Optional: E2E_IMPORT_URL=https://… also exercises the URL import (needs internet).
"""

import os
import re
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://frontend")
KEY = os.environ["E2E_ACCESS_KEY"]
IMPORT_URL = os.environ.get("E2E_IMPORT_URL", "")
PDF_URL = os.environ.get("E2E_PDF_URL", "https://arxiv.org/pdf/1706.03762")
TITLE = "E2E · Attention Is All You Need"
OUT = Path(__file__).parent / "out"
PDF = OUT / "attention.pdf"

problems: list[str] = []


def watch_console(page: Page, label: str) -> None:
    page.on(
        "console",
        lambda m: m.type in ("error", "warning")
        and problems.append(f"[{label}] console.{m.type}: {m.text}"),
    )
    page.on("pageerror", lambda e: problems.append(f"[{label}] pageerror: {e}"))
    page.on(
        "dialog",
        lambda d: problems.append(f"[{label}] native dialog: {d.message}") or d.dismiss(),
    )


def rename_in_dialog(page: Page, value: str) -> None:
    """Fill the in-app rename dialog (replaced window.prompt)."""
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox").fill(value)
    dialog.get_by_role("button", name="Speichern").click()
    expect(dialog).to_be_hidden()


def step(name: str) -> None:
    print(f"-> {name}", flush=True)


OUT.mkdir(exist_ok=True)
if not PDF.exists():
    urllib.request.urlretrieve(PDF_URL, PDF)  # noqa: S310 - fixed https URL

with sync_playwright() as p:
    api = p.request.new_context(base_url=BASE, extra_http_headers={"X-Access-Key": KEY})
    for notebook in api.get("/api/notebooks").json():
        if notebook["title"].startswith("E2E ·"):
            api.delete(f"/api/notebooks/{notebook['id']}")

    browser = p.chromium.launch()
    context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    page = context.new_page()
    watch_console(page, "desktop")

    step("wrong key is rejected")
    page.goto(BASE)
    page.get_by_placeholder("Zugangsschlüssel").fill("falscher-schluessel")
    page.get_by_role("button", name="Öffnen").click()
    expect(page.get_by_text("Zugangsschlüssel ungültig.")).to_be_visible()
    problems.clear()  # the browser logs the expected 401

    step("unlock")
    page.get_by_placeholder("Zugangsschlüssel").fill(KEY)
    page.get_by_role("button", name="Öffnen").click()
    expect(page.get_by_role("heading", name="Notebooks")).to_be_visible()

    step("create and rename notebook")
    page.get_by_role("button", name="Neues Notebook").click()
    expect(page.get_by_role("heading", name="Unbenanntes Notebook")).to_be_visible()
    page.get_by_role("heading", name="Unbenanntes Notebook").click()
    rename_in_dialog(page, TITLE)
    expect(page.get_by_role("heading", name=TITLE)).to_be_visible()

    step("upload pdf")
    page.get_by_role("button", name="Hinzufügen", exact=True).click()
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Dateien auswählen").click()
    chooser.value.set_files(str(PDF))
    expect(page.get_by_text("Wird verarbeitet …")).to_be_visible()
    expect(page.get_by_text(re.compile(r"PDF · \d+ S\. · \d+ Abschnitte"))).to_be_visible(
        timeout=120_000
    )

    step("source guide opens in the main column")
    page.get_by_role("button", name=re.compile(r"öffnen$")).first.click()
    guide = page.get_by_role("region", name="Quelle", exact=True)
    expect(guide).to_be_visible()
    expect(guide.get_by_text("Das Paper stellt den Transformer vor")).to_be_visible(timeout=30_000)
    # the chat is only hidden, not unmounted, so a running answer survives a lookup
    expect(page.get_by_role("region", name="Chat")).to_be_hidden()
    page.screenshot(path=OUT / "01-guide.png")

    step("notebook overview greets the empty chat")
    guide.get_by_role("button", name="Zum Chat").click()
    # built from the source guides once they are ready, so the UI has to poll for it
    expect(page.get_by_text("Die Sammlung dreht sich um")).to_be_visible(timeout=60_000)
    expect(
        page.get_by_role("button", name="Welche Bausteine hat die Transformer-Architektur?")
    ).to_be_visible()
    page.screenshot(path=OUT / "01b-overview.png")

    step("rename source")
    page.get_by_role("button", name=re.compile(r"öffnen$")).first.click()
    page.get_by_role("button", name="Umbenennen").click()
    rename_in_dialog(page, "Transformer-Paper")
    expect(page.get_by_role("button", name=re.compile(r"^Transformer-Paper"))).to_be_visible()

    step("suggested question → answer with citation chips")
    guide.get_by_role("button", name="Wie viele Attention-Heads nutzt das Basismodell?").click()
    expect(guide).to_be_hidden()  # asking returns to the chat
    chips = page.get_by_role("button", name=re.compile(r"^Quelle \d+:"))
    expect(chips.first).to_be_visible(timeout=30_000)
    answer = page.locator("article").last.inner_text()
    assert "[2, 19]" not in answer, "invalid citation group must be stripped"
    assert chips.count() >= 2, f"expected ≥ 2 citation chips, got {chips.count()}"
    page.screenshot(path=OUT / "02-answer.png")

    step("citation chip previews the passage on hover")
    chips.first.hover()
    preview = page.get_by_role("tooltip")
    expect(preview).to_be_visible()
    expect(preview.get_by_text("Klicken öffnet die Passage")).to_be_visible()
    page.screenshot(path=OUT / "02b-preview.png")

    step("citation drawer shows highlighted passage")
    chips.first.click()
    drawer = page.get_by_role("dialog")
    expect(drawer.locator("mark")).to_be_visible()
    expect(drawer.get_by_text(re.compile(r"Seite \d+"))).to_be_visible()
    page.screenshot(path=OUT / "03-citation.png")
    page.keyboard.press("Escape")
    expect(drawer).to_be_hidden()

    step("question outside the sources")
    send = page.get_by_label("Senden")
    background = "el => getComputedStyle(el).backgroundColor"
    # grey while there is nothing to send, accent colour as soon as there is
    expect(send).to_be_disabled()
    idle = send.evaluate(background)
    page.get_by_label("Frage").fill("Wie wird das Wetter morgen?")
    expect(send).to_be_enabled()
    page.wait_for_timeout(400)  # the button transitions its colours
    assert send.evaluate(background) != idle, "send button must change colour once there is text"
    page.screenshot(path=OUT / "02c-composer.png")
    page.keyboard.press("Enter")
    expect(page.get_by_text("Dazu enthalten die Quellen keine Angaben.")).to_be_visible(
        timeout=30_000
    )

    step("save answer as note and edit it")
    page.get_by_role("button", name="Als Notiz speichern").first.click()
    notes = page.get_by_role("region", name="Studio")
    notes.get_by_role("button", name=re.compile("Wie viele Attention-Heads")).click()
    # the saved answer keeps clickable citations, not a flat list of source names
    expect(notes.get_by_role("button", name=re.compile(r"^Quelle \d+:")).first).to_be_visible()
    notes.get_by_role("button", name="Bearbeiten").click()
    notes.get_by_label("Titel der Notiz").fill("Attention-Heads (bearbeitet)")
    notes.get_by_role("button", name="Speichern").click()
    expect(notes.get_by_text("Attention-Heads (bearbeitet)")).to_be_visible()
    page.screenshot(path=OUT / "04-notes.png")

    step("topic map leads back into the chat")
    notes.get_by_role("button", name="Themenkarte").click()
    topics = page.get_by_role("region", name="Themenkarte")
    expect(topics).to_be_visible()
    expect(topics.get_by_role("button", name="Transformer", exact=True)).to_be_visible()
    page.screenshot(path=OUT / "08-topics.png")
    topics.get_by_role("button", name="Self-Attention", exact=True).click()
    # asking from the map returns to the chat and sends the question
    expect(topics).to_be_hidden()
    expect(page.get_by_text("Was sagen die Quellen zu")).to_be_visible(timeout=30_000)

    step("briefing document")
    notes.get_by_role("button", name="Briefing").click()
    briefing = notes.locator("article", has_text="Briefing:")
    expect(briefing).to_be_visible(timeout=120_000)
    # one section per key question of the overview, each with working citations
    expect(briefing.get_by_text("Welche Bausteine hat die Transformer-Architektur?")).to_be_visible()
    expect(briefing.get_by_role("button", name=re.compile(r"^Quelle \d+:")).first).to_be_visible()
    page.screenshot(path=OUT / "06-briefing.png")

    step("faq report")
    notes.get_by_role("button", name="FAQ").click()
    faq = notes.locator("article", has_text="FAQ:")
    expect(faq).to_be_visible(timeout=120_000)
    # the FAQ asks what the source guide proposes, the briefing what the overview proposes
    expect(faq.get_by_text("Wie viele Attention-Heads nutzt das Basismodell?")).to_be_visible()
    expect(faq.get_by_role("button", name=re.compile(r"^Quelle \d+:")).first).to_be_visible()

    step("source filter")
    checkbox = page.get_by_label(re.compile("für Antworten verwenden"))
    checkbox.uncheck()
    expect(page.get_by_label("Frage")).to_be_disabled()
    checkbox.check()
    expect(page.get_by_label("Frage")).to_be_enabled()

    if IMPORT_URL:
        step("url import")
        page.get_by_role("button", name="Hinzufügen", exact=True).click()
        page.get_by_label("Webseite importieren").fill(IMPORT_URL)
        page.get_by_role("button", name="Import").click()
        expect(page.get_by_text(re.compile(r"URL · \d+ Abschnitte"))).to_be_visible(timeout=60_000)

    step("url import blocks internal addresses")
    page.get_by_role("button", name="Hinzufügen", exact=True).click()
    page.get_by_label("Webseite importieren").fill("http://169.254.169.254/latest/meta-data")
    page.get_by_role("button", name="Import").click()
    expect(page.get_by_text("interne Adresse")).to_be_visible(timeout=30_000)

    step("reload keeps state")
    page.reload()
    expect(page.get_by_text("Dazu enthalten die Quellen keine Angaben.")).to_be_visible()
    notebook_url = page.url

    step("dark mode")
    dark = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    dark.add_init_script(f"localStorage.setItem('notebook.accessKey', {KEY!r})")
    dark_page = dark.new_page()
    watch_console(dark_page, "dark")
    dark_page.goto(notebook_url)
    expect(dark_page.get_by_role("button", name=re.compile(r"^Quelle \d+:")).first).to_be_visible()
    dark_page.screenshot(path=OUT / "05-dark.png")
    dark_page.goto(BASE)
    expect(dark_page.get_by_role("heading", name="Notebooks")).to_be_visible()
    dark_page.screenshot(path=OUT / "05b-dark-list.png")

    step("mobile layout")
    mobile = browser.new_context(
        viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
    )
    mobile.add_init_script(f"localStorage.setItem('notebook.accessKey', {KEY!r})")
    mobile_page = mobile.new_page()
    watch_console(mobile_page, "mobile")
    mobile_page.goto(notebook_url)
    expect(mobile_page.get_by_role("region", name="Chat")).to_be_visible()
    expect(mobile_page.get_by_role("region", name="Quellen")).to_be_hidden()
    width = mobile_page.evaluate("document.documentElement.scrollWidth")
    assert width <= 390, f"horizontal overflow on mobile: {width}px"
    mobile_page.screenshot(path=OUT / "06-mobile.png")
    mobile_page.get_by_role("button", name="Quellen", exact=True).click()
    expect(mobile_page.get_by_role("region", name="Quellen")).to_be_visible()

    step("notebook list: search and view switch")
    page.goto(BASE)
    expect(page.locator("li", has_text=TITLE)).to_be_visible()
    page.get_by_role("button", name="Notebooks durchsuchen").click()
    page.get_by_label("Notebooks durchsuchen").fill("gibtesnicht")
    expect(page.get_by_text("Kein Notebook mit")).to_be_visible()
    page.get_by_label("Notebooks durchsuchen").fill("E2E")
    expect(page.locator("li", has_text=TITLE)).to_be_visible()
    page.get_by_role("button", name="Suche schließen").click()
    page.get_by_role("button", name="Liste", exact=True).click()
    expect(page.locator("li", has_text=TITLE)).to_be_visible()
    page.screenshot(path=OUT / "07-list.png")
    page.get_by_role("button", name="Kacheln", exact=True).click()

    step("delete notebook")
    card = page.locator("li", has_text=TITLE)
    card.get_by_role("button", name="Löschen").click()
    page.get_by_role("dialog").get_by_role("button", name="Löschen").click()
    expect(card).to_have_count(0)

    browser.close()

if problems:
    print("\nBrowser console problems:")
    for problem in problems:
        print(f"  {problem}")
    sys.exit(1)
print("\nE2E OK – no console errors or warnings")
