# PyBeats

---

# 📄 `README.md`

````markdown
# 🎵 PyBeats – Dockerized Python MP3 Player

PyBeats is a simple desktop MP3 player built using Python.  
It uses **Tkinter** for the GUI and **Pygame (SDL2)** for audio playback.

This project is fully containerized and available on **Docker Hub**.

---

## 🚀 Features

- 🎵 Play MP3 files
- 📂 Load folders recursively
- 🔀 Shuffle mode
- ⏯ Play / Pause / Stop
- 📊 Seek bar (track progress)
- 🔊 Volume control
- 🏷 ID3 metadata support (Title, Artist, Album)
- 🐳 Fully Dockerized

---

## 🧰 Tech Stack

### Standard Library
- `tkinter`
- `threading`
- `os`
- `pathlib`
- `random`
- `time`

### Third-Party Libraries
- `pygame` – Audio engine (SDL2 backend)
- `mutagen` – Reads MP3 metadata (ID3 tags)

Install locally:
```bash
pip install pygame mutagen
````

---

# 🐳 Docker Image

The official Docker image is available on Docker Hub:

👉 **[https://hub.docker.com/r/tejalonkar15/pybeats](https://hub.docker.com/r/tejalonkar15/pybeats)**

Pull image:

```bash
docker pull tejalonkar15/pybeats:4.0
```

---

# ⚠️ Important (Linux Only)

This is a **GUI desktop application**.

Docker containers do NOT automatically support:

* GUI display
* Sound hardware access

You must enable:

* X11 forwarding
* ALSA audio device access

---

# ▶️ Run Instructions (Linux)

### Step 1: Allow Docker to access display

```bash
xhost +local:docker
```

---

### Step 2: Run container

```bash
docker run \
  --device /dev/snd \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  tejalonkar15/pybeats:4.0
```

---

### Step 3: After closing app

```bash
xhost -local:docker
```

---

# 🔊 Audio Notes

If you see this error:

```
pygame.error: ALSA: Couldn't open audio device
```

It means the container cannot access your sound hardware.

Make sure:

* You are on Linux
* `/dev/snd` exists
* Docker has permission to access audio devices

---

# 🖥 GUI Notes

If you see:

```
_tkinter.TclError: no display name and no $DISPLAY environment variable
```

It means X11 forwarding is not configured properly.

Make sure:

```bash
xhost +local:docker
```

And that `$DISPLAY` is set:

```bash
echo $DISPLAY
```

---

# 📦 Dockerfile Overview

Base Image:

```
python:3.12-slim
```

Includes:

* SDL2 development libraries
* Tkinter system libraries
* Audio dependencies
* Python build tools

Optimized using:

```
--no-cache-dir
rm -rf /var/lib/apt/lists/*
```

---


---

# 🧠 Architecture

```
Tkinter GUI
      ↓
Pygame (SDL2 Mixer)
      ↓
ALSA / Host Audio Device
```

Container Runtime:

```
Docker → X11 Socket → Linux Display Server
Docker → /dev/snd → Host Audio
```

---

# 🎓 Learning Objectives

This project demonstrates:

* Python GUI development
* Audio playback with SDL2
* Docker containerization
* Handling GUI apps inside Docker
* ALSA device mapping
* X11 forwarding
* Image tagging and publishing to Docker Hub

---

# 🔐 Security Note

`xhost +local:docker` temporarily allows Docker containers to access your display.

Always disable after use:

```bash
xhost -local:docker
```

---

# 👩‍💻 Author

Tejal Onkar
Docker Hub: [https://hub.docker.com/u/tejalonkar15](https://hub.docker.com/u/tejalonkar15)

---

# ⭐ Future Improvements

* Reduce image size
* Add playlist saving
* Add dark theme
* Multi-stage Docker build
* Web-based version

---

