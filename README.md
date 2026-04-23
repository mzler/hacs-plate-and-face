# Plate & Face Recognition – HACS Custom Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
![Version](https://img.shields.io/badge/version-1.0.0-blue)

Eine HACS Custom Integration für Home Assistant, die Nummernschilder und Gesichter von bis zu **5 Kameraentitäten** erkennt – vollständig lokal, ohne Cloud-Dienst.

---

## Features

| Feature | Beschreibung |
|---|---|
| 🚗 Nummernschilderkennung | OpenCV + EasyOCR erkennt Kennzeichen in jedem Kamerabild |
| 👤 Gesichtserkennung | `face_recognition`-Bibliothek erkennt bekannte Personen |
| 🔄 Live-Updates | Erkennung startet automatisch bei jedem neuen Kamerabild |
| 📦 Lokal | Keine Cloud, keine API-Keys – alles auf deinem HA-Server |
| 🗂️ Gesichtsdatenbank | Personen mit Namen registrieren via Service oder Kamera-Snapshot |

---

## Sensoren (pro Kamera)

Für jede konfigurierte Kamera werden **zwei Sensoren** angelegt:

| Entitäts-ID | Beschreibung |
|---|---|
| `sensor.<kamera>_license_plate` | Aktuell sichtbare Nummernschilder (kommagetrennt) |
| `sensor.<kamera>_detected_faces` | Erkannte Personen (kommagetrennt); Unbekannte als `Unknown (N)` |

Zusätzlich:

| Entitäts-ID | Beschreibung |
|---|---|
| `sensor.plate_face_recognition_known_faces` | Anzahl registrierter Gesichter + Liste als Attribut |

---

## Installation

### Voraussetzungen

- Home Assistant 2023.1 oder neuer
- HACS installiert
- Ausreichend RAM (~512 MB für EasyOCR-Modelle, ~256 MB für face_recognition)

### Via HACS (empfohlen)

1. HACS → **Benutzerdefinierte Repositories** → URL eintragen:
   ```
   https://github.com/timohaberl/hacs-plate-face-recognition
   ```
2. Kategorie: **Integration**
3. Integration installieren & Home Assistant neu starten

### Manuell

1. Dieses Repository klonen / ZIP herunterladen
2. Ordner `custom_components/plate_face_recognition` in dein
   `<config>/custom_components/` Verzeichnis kopieren
3. Home Assistant neu starten

---

## Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
2. Nach „Plate & Face Recognition" suchen
3. Kameraentitäten auswählen (bis zu 5)
4. Optionen anpassen (Toleranzen, Features aktivieren/deaktivieren)

---

## Gesichter registrieren

### Option A: Von einer Bilddatei

Lege ein Portraitfoto auf deinen HA-Server (z. B. `/config/faces/alice.jpg`) und rufe den Service auf:

```yaml
service: plate_face_recognition.register_face
data:
  name: "Alice"
  file_path: "/config/faces/alice.jpg"
```

### Option B: Live-Snapshot von einer Kamera

```yaml
service: plate_face_recognition.capture_face_from_camera
data:
  name: "Bob"
  camera_entity_id: camera.front_door
```

### Gesicht löschen

```yaml
service: plate_face_recognition.delete_face
data:
  name: "Alice"
```

### Alle Gesichter auflisten

```yaml
service: plate_face_recognition.list_faces
```
→ Feuert das Event `plate_face_recognition_faces_listed` mit Namen & Anzahl.

---

## Events für Automationen

| Event | Payload | Beschreibung |
|---|---|---|
| `plate_face_recognition_plate_detected` | `camera`, `plates` | Nummernschild erkannt |
| `plate_face_recognition_face_detected` | `camera`, `faces`, `unknown` | Gesicht erkannt |

**Beispiel-Automation:**

```yaml
automation:
  - alias: "Tor öffnen bei bekanntem Kennzeichen"
    trigger:
      - platform: event
        event_type: plate_face_recognition_plate_detected
        event_data:
          plates:
            - "W AB 1234"
    action:
      - service: cover.open_cover
        target:
          entity_id: cover.garagentor
```

---

## Konfigurationsoptionen

| Option | Standard | Beschreibung |
|---|---|---|
| `cameras` | – | Liste der Kameraentitäten (1–5) |
| `enable_plates` | `true` | Nummernschilderkennung aktivieren |
| `enable_faces` | `true` | Gesichtserkennung aktivieren |
| `face_threshold` | `0.55` | Toleranz (0 = sehr streng, 1 = sehr locker) |
| `plate_min_confidence` | `0.50` | Mindestkonfidenz für OCR-Treffer |

---

## Technische Details

### Nummernschilderkennung
1. **Regionen-Detektion**: OpenCV Canny-Edges + Kontur-Analyse findet rechteckige Bereiche mit Seitenverhältnis 1,5:1 – 7:1
2. **OCR**: EasyOCR liest Text aus den Kandidaten-Regionen + Fallback auf Vollbild
3. **Regex-Filter**: Nur Texte, die bekannten Kennzeichen-Mustern entsprechen (DE, AT, CH + generisch)

### Gesichtserkennung
- `face_recognition` (dlib HOG-Modell) für schnelle CPU-basierte Erkennung
- Mehrere Trainingsfotos pro Person möglich → verbessert Genauigkeit
- Unbekannte Gesichter werden als `Unknown (N)` ausgegeben

### Datenspeicherung
- Gesichts-Encodings gespeichert in: `<config>/plate_face_recognition/known_faces/known_faces.pkl`
- Für Backup diesen Ordner sichern

---

## Troubleshooting

### EasyOCR lädt Modelle beim ersten Start herunter
Das ist normal – EasyOCR lädt beim ersten Aufruf die OCR-Modelle (~100 MB). Danach werden sie gecacht.

### `face_recognition` lässt sich nicht installieren
Das Paket benötigt `cmake` und `dlib`. Auf Home Assistant OS:
```bash
# Im Terminal-Addon:
apk add cmake
pip install dlib face_recognition
```

### Nummernschild wird nicht erkannt
- Bild-Auflösung erhöhen (mind. 720p empfohlen)
- `plate_min_confidence` auf `0.3` senken
- Prüfen, ob das Kennzeichen im Bild klar lesbar ist

---

## Lizenz

MIT License – © 2024 timohaberl
