# Plate & Face Recognition for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/timohaberl/hacs-plate-face-recognition.svg)](https://github.com/timohaberl/hacs-plate-face-recognition/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration for **local** license plate and face recognition using a companion Docker container. All AI/ML processing runs locally — **no cloud, no subscription**.

![Management UI Preview](docs/preview.png)

---

## ✨ Features

- 🚗 **License Plate Recognition** via EasyOCR (local, offline)
- 👤 **Face Recognition** via dlib & face_recognition (local, offline)
- 🔗 **Person Profiles** – link plates and faces to a named person
- 🏠 **HA User Linking** – associate recognized persons with HA users
- 📱 **Management UI** – built-in web panel for managing profiles
- ⚡ **Automation Triggers** – fire events when a known person is detected
- 🔒 **100% Local** – no data leaves your network

---

## 📋 Requirements

| Component | Requirement |
|-----------|-------------|
| Home Assistant | 2023.1.0 or newer |
| HACS | For easy installation |
| Docker | For the ML Add-on backend |

---

## 🚀 Installation

### Step 1: Install via HACS

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click the **⋮** menu → **Custom Repositories**
4. Add: `https://github.com/timohaberl/hacs-plate-face-recognition`
5. Search for **Plate & Face Recognition** and install it
6. Restart Home Assistant

### Step 2: Start the ML Add-on

The integration requires a companion Docker container for all AI processing.

**Option A: Docker Compose (recommended)**

```bash
git clone https://github.com/timohaberl/hacs-plate-face-recognition.git
cd hacs-plate-face-recognition
docker-compose up -d pfr-addon
```

**Option B: Docker Run**

```bash
docker run -d \
  --name pfr-addon \
  -p 8585:8585 \
  -v pfr-data:/data \
  timohaberl/pfr-addon:latest
```

### Step 3: Configure the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Plate & Face Recognition**
3. Enter the Add-on URL: `http://localhost:8585` (or your server IP)
4. Select your camera entities

---

## ⚙️ Configuration

### Management Panel

After installation, a **"Personen & Kennzeichen"** panel appears in the HA sidebar.

From there you can:
- Create person profiles
- Link license plates to persons
- Upload face photos for biometric recognition
- Assign HA users to recognized persons

### Automation Examples

**Trigger when a known person is detected:**

```yaml
alias: "Welcome Max home"
trigger:
  - platform: event
    event_type: plate_face_recognition_face_detected
    event_data:
      faces:
        - "Max"
action:
  - service: notify.mobile_app
    data:
      message: "Max arrived home!"
```

**Open garage when car plate is detected:**

```yaml
alias: "Open garage for known car"
trigger:
  - platform: event
    event_type: plate_face_recognition_plate_detected
    event_data:
      plates:
        - "W-12345"
action:
  - service: cover.open_cover
    target:
      entity_id: cover.garage
```

---

## 📡 Services

| Service | Description |
|---------|-------------|
| `plate_face_recognition.register_face` | Register a face from a file path |
| `plate_face_recognition.capture_face_from_camera` | Capture & register face from camera |
| `plate_face_recognition.save_profile` | Save/update a person profile |
| `plate_face_recognition.delete_profile` | Delete a person profile |
| `plate_face_recognition.delete_face` | Remove face encodings |

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐
│         Home Assistant          │
│  ┌──────────────────────────┐   │
│  │  plate_face_recognition  │   │
│  │  (custom_component)      │   │
│  │  - Coordinator           │   │
│  │  - Sensors               │   │
│  │  - Services              │   │
│  └────────────┬─────────────┘   │
└───────────────┼─────────────────┘
                │ HTTP REST (port 8585)
                ▼
┌─────────────────────────────────┐
│        pfr-addon (Docker)       │
│  - FastAPI REST Server          │
│  - EasyOCR (License Plates)     │
│  - dlib + face_recognition      │
│  - Profile Manager              │
└─────────────────────────────────┘
```

---

## 🐛 Troubleshooting

**Add-on not reachable:**
- Ensure Docker container is running: `docker ps | grep pfr-addon`
- Check add-on logs: `docker logs pfr-addon`
- Verify port 8585 is not blocked by firewall

**No faces detected:**
- Use a clear, well-lit portrait photo
- Ensure only one face is visible per photo
- Try multiple photos per person for better accuracy

---

## 📄 License

MIT License – see [LICENSE](LICENSE) file.

## 🤝 Contributing

Pull requests welcome! Please open an issue first to discuss major changes.
