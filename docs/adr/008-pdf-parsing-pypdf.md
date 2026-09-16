# ADR-08: PDF-Parsing mit pypdf statt PyMuPDF

Status: angenommen (weicht von plan.md ab)

## Kontext

plan.md sah PyMuPDF vor. PyMuPDF steht unter AGPL-3.0 (oder kommerzieller Lizenz); dieses Repo
ist MIT-lizenziert und wird als öffentlicher Webdienst betrieben.

## Entscheidung

- `pypdf` (BSD-3-Clause), reines Python, Textextraktion seitenweise → Seitenzahl bleibt pro
  Chunk erhalten.
- Unterstützt werden Text-PDFs. Seiten ohne extrahierbaren Text werden übersprungen; hat das
  ganze Dokument keinen Text (Scan), wird die Quelle mit verständlicher Fehlermeldung auf
  `error` gesetzt.

## Konsequenzen

- Keine Lizenzkollision mit MIT, kein Binär-Wheel.
- pypdf ist langsamer und bei komplexen Layouts (mehrspaltig, Tabellen) ungenauer als PyMuPDF.
  Demo-Quellen werden vorab getestet.

## Verworfene Alternativen

- PyMuPDF: beste Qualität, aber AGPL.
- pdfplumber/pdfminer.six: MIT, gute Layouts, aber deutlich langsamer bei großen Dokumenten.
- OCR (Tesseract): gescannte PDFs sind bewusst out of scope.
