"""Create the demo notebook "KI im Unternehmen" with public sources.

Idempotent: sources that already exist (same URL) are skipped. Sources are imported one after
another so embedding and guide generation stay within the free-tier rate limits.

Usage (standard library only):
    ACCESS_KEY=... python demo/seed.py --base-url http://localhost:8080
Inside the backend container:
    docker compose cp demo/seed.py backend:/tmp/seed.py
    docker compose exec backend python /tmp/seed.py --base-url http://localhost:8000
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

NOTEBOOK_TITLE = "KI im Unternehmen: Recht & Verträge"

# Short sources first, the 200-page regulation last. Ingesting it takes minutes and many
# guide calls; if it fails, the notebook is still usable with the three others.
SOURCES = [
    {
        "title": "Mustervertrag Auftragsverarbeitung nach Art. 28 DSGVO (WKO)",
        "url": "https://www.wko.at/oe/datenschutz/eu-dsgvo-mustervertrag-vereinbarung-auftragsverarbeitung.pdf",
    },
    {
        "title": "EU-Mustervertragsklauseln für KI-Beschaffung (MVK-KI) – Kommentar",
        "url": "https://public-buyers-community.ec.europa.eu/sites/default/files/2025-06/GROW-2025-00573-02-01-DE-TRA-00.pdf",
    },
    {
        "title": "DSK: Orientierungshilfe generative KI mit RAG (2025)",
        "url": "https://www.datenschutzkonferenz-online.de/media/oh/DSK_OH_RAG.pdf",
    },
    {
        "title": "KI-Verordnung (EU) 2024/1689",
        # Amtsblatt-PDF, gespiegelt von der IHK – EUR-Lex blockt automatisierte Abrufe
        "url": "https://www.ihk.de/blueprint/servlet/resource/blob/6203774/d2e3f88248a0a4951beb9eb8c3050d51/eu-ki-verordnung-data.pdf",
    },
]

TIMEOUT_SECONDS = 20 * 60


class Api:
    def __init__(self, base_url: str, key: str) -> None:
        self.base = base_url.rstrip("/") + "/api"
        self.key = key

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(  # noqa: S310 - base URL comes from the operator
            self.base + path,
            data=data,
            method=method,
            headers={"X-Access-Key": self.key, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            sys.exit(f"{method} {path} failed: HTTP {exc.code} {exc.read()[:300]!r}")
        return json.loads(raw) if raw else None


def wait_until_done(api: Api, notebook_id: str, source_id: str) -> dict[str, Any]:
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        source = next(
            s for s in api.call("GET", f"/notebooks/{notebook_id}/sources") if s["id"] == source_id
        )
        if source["status"] == "error":
            return source
        if source["status"] == "ready" and source["guide_status"] != "pending":
            return source
        time.sleep(3)
    sys.exit(f"timeout while processing source {source_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8080")
    args = parser.parse_args()
    key = os.environ.get("ACCESS_KEY") or os.environ.get("NOTEBOOK_ACCESS_KEY")
    if not key:
        sys.exit("ACCESS_KEY environment variable is required")
    api = Api(args.base_url, key)

    notebook = next(
        (nb for nb in api.call("GET", "/notebooks") if nb["title"] == NOTEBOOK_TITLE), None
    ) or api.call("POST", "/notebooks", {"title": NOTEBOOK_TITLE})
    print(f"Notebook: {notebook['title']} ({notebook['id']})")

    existing = {s["origin"]: s for s in api.call("GET", f"/notebooks/{notebook['id']}/sources")}
    failures = 0
    for spec in SOURCES:
        started = time.time()
        source = existing.get(spec["url"])
        if source and source["status"] == "ready":
            print(f"  = {spec['title']} (vorhanden)")
            if source["guide_status"] == "error":
                api.call("POST", f"/sources/{source['id']}/guide")
                source = wait_until_done(api, notebook["id"], source["id"])
        else:
            if source:  # failed earlier: remove and retry
                api.call("DELETE", f"/sources/{source['id']}")
            source = api.call(
                "POST", f"/notebooks/{notebook['id']}/sources/url", {"url": spec["url"]}
            )
            source = wait_until_done(api, notebook["id"], source["id"])
        if source["status"] == "error":
            failures += 1
            print(f"  ! {spec['title']}: {source['error']}")
            continue
        if source["title"] != spec["title"]:
            source = api.call("PATCH", f"/sources/{source['id']}", {"title": spec["title"]})
        guide = "Guide ok" if source["guide_status"] == "ready" else f"Guide: {source['guide_error']}"
        print(
            f"  + {spec['title']}: {source['page_count']} S., {source['chunk_count']} Abschnitte, "
            f"{guide} ({time.time() - started:.0f}s)"
        )
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
