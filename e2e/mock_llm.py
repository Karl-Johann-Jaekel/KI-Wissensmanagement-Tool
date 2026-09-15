"""Mistral-compatible stand-in for browser E2E runs (never used in production).

- json_mode requests → a fixed source guide
- map-step requests → a fixed section summary
- chat requests → bullet points quoting the first passages with [n] markers, plus a fake
  academic reference "[2, 19]" that the backend must strip; questions about "Wetter" get the
  "not in the sources" answer
"""

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

PASSAGE = re.compile(
    r"\[(\d+)\] \(Quelle: [^)]*\)\n(.+?)(?=\n\n\[\d+\] \(Quelle|\n\nFrage:)", re.S
)

GUIDE = {
    "summary": (
        "Das Paper stellt den Transformer vor, eine Architektur nur aus Attention-Mechanismen. "
        "Sie erreicht bessere BLEU-Werte bei kürzerer Trainingszeit."
    ),
    "key_topics": ["Transformer", "Self-Attention", "Maschinelle Übersetzung", "BLEU"],
    "suggested_questions": [
        "Wie viele Attention-Heads nutzt das Basismodell?",
        "Welche BLEU-Werte erreicht das Modell?",
        "Wie lange dauerte das Training?",
    ],
}


def chat_answer(messages: list[dict[str, str]]) -> str:
    user = messages[-1]["content"]
    question = user.rsplit("Frage:", 1)[-1].strip()
    if "wetter" in question.lower():
        return "Dazu enthalten die Quellen keine Angaben."
    bullets = [f"- {' '.join(text.split()[:18])} [{n}]" for n, text in PASSAGE.findall(user)[:3]]
    return (
        "Die Quellen beschreiben dazu **mehrere Punkte**:\n\n"
        + "\n".join(bullets)
        + "\n\nEin Literaturverweis [2, 19] wird entfernt."
    )


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server API
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        messages = body["messages"]
        if body.get("response_format"):
            content = json.dumps(GUIDE)
        elif messages[0]["content"].startswith("Fasse den folgenden Abschnitt"):
            content = "Abschnittszusammenfassung."
        else:
            content = chat_answer(messages)
        payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()  # noqa: S104
