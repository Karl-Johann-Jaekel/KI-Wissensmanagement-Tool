# ADR-11: Notizen behalten die Belege der gespeicherten Antwort

Status: angenommen · ersetzt eine frühere Umsetzung innerhalb von [ADR-05](005-validated-citations.md)

## Kontext

Der Kern des Projekts ist: jede Aussage lässt sich an ihrer Quelle nachlesen. Beim Speichern
einer Antwort als Notiz endete das. Die Belege wurden zu Text verflacht und unter die Notiz
geschrieben:

```
Der Umsatz stieg um 12 % [1].

Quellen:
[1] bericht, S. 5
```

Das `[1]` im Text war danach ein totes Zeichen. Wer in der Notiz auf einen Beleg klicken wollte,
musste zurück in den Chat — sofern der Verlauf noch existierte. Genau die Zusammenfassung, die
man behalten will, war die einzige Stelle ohne prüfbare Quelle.

## Entscheidung

`notes` bekommt eine Spalte `citations` (JSONB, Migration 0003) mit derselben Struktur wie
`messages.citations`. Beim Speichern einer Antwort werden die Belege mitkopiert statt in Text
aufgelöst; die angehängte Quellenliste entfällt, weil die Marker im Text wieder funktionieren.

Die Belege hängen an der Notiz, nicht am Text: Wer die Notiz bearbeitet, behält sie. Selbst
geschriebene Notizen haben eine leere Liste — ein `[1]` darin bleibt gewöhnlicher Text.

## Konsequenzen

- Zitate verhalten sich überall gleich: Chip anklicken öffnet die Passage, egal ob im Chat oder
  in einer Notiz.
- Die Belege sind eine Kopie, kein Verweis. Wird die Quelle später gelöscht, zeigt der Chip ins
  Leere und der Zitat-Viewer meldet, dass die Passage nicht mehr existiert. Das ist gewollt: eine
  Notiz soll festhalten, worauf sie sich gestützt hat, auch wenn die Quelle verschwindet.
- Eine bearbeitete Notiz kann Belege führen, deren Marker der Nutzer aus dem Text entfernt hat.
  Sichtbar ist nur, was im Text steht, daher ohne Wirkung.

## Verworfene Alternativen

- **Auf die Nachricht verweisen statt kopieren:** die Notiz hinge am Chatverlauf, den man löschen
  kann — und genau deshalb speichert man sie.
- **Die Marker beim Speichern durch Quellennamen ersetzen:** lesbar, aber nicht nachprüfbar; das
  ist der Zustand, den diese Entscheidung behebt.
