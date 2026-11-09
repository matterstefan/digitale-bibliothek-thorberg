# Digitale Bibliothek Thorberg

Interaktiver Forschungsprototyp zur Erkundung historischer Standortsignaturen der aus der Kartause Thorberg erhaltenen physischen Bücher. Enthält 108 Banddatensätze, zugeordnete Fotografien, Signaturübersicht und experimentelle schematische Stapelansicht.

Die Darstellung ist **keine gesicherte Rekonstruktion** der historischen Aufstellung. Lesungssicherheiten sind teilweise nur heuristisch gekennzeichnet. Die Forschungsdaten können wachsen und korrigiert werden.

## Website

Die Website funktioniert ohne Server direkt über `index.html` und lässt sich über GitHub Pages bereitstellen: *Settings → Pages → Deploy from a branch → main → / (root)*.

## Änderungsvorschläge

In jeder Bandansicht führt **Änderung vorschlagen** zu einem vorausgefüllten GitHub Issue. Vorschläge werden **nicht automatisch in die Forschungsdaten übernommen**. Für die Einsendung ist ein GitHub-Konto nötig. Auch im Repository können Vorschläge über Issues eingereicht werden.

## Dateien

- `index.html`: statische Webanwendung
- `daten.json`: Forschungsdaten für die Webanwendung, einschliesslich Feldwerten, Medien-IDs und Zuordnungen
- `bilder/`: kleinere Ansichtsdateien
- `originale/`: Originalaufnahmen, die in den Banddetailansichten geöffnet werden können

Die Omeka-Ausgangssicherung vom 9. November 2026 sollte zusätzlich ausserhalb des Repositories archiviert bleiben. Für neue und korrigierte Daten wird langfristig eine eigene Bearbeitungsmöglichkeit entwickelt.
