"""
♪ SoundWave MP3 Player
A clean, modern MP3 player with recursive directory browsing.

Requirements:
    pip install pygame mutagen
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    import pygame
    pygame.mixer.init()
except ImportError:
    print("Please install pygame: pip install pygame")
    sys.exit(1)

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False

# ── Color Palette ──────────────────────────────────────────────────────────────
BG         = "#0f0f13"
BG2        = "#18181f"
BG3        = "#22222c"
ACCENT     = "#c084fc"       # purple-400
ACCENT2    = "#818cf8"       # indigo-400
TEXT       = "#f1f5f9"
TEXT_DIM   = "#64748b"
TEXT_MID   = "#94a3b8"
HIGHLIGHT  = "#2d2d3f"
SEL_BG     = "#3b3b52"
TRACK_BG   = "#2a2a38"
PROGRESS   = "#c084fc"

FONT_TITLE  = ("Helvetica", 22, "bold")
FONT_SONG   = ("Helvetica", 14, "bold")
FONT_SUB    = ("Helvetica", 10)
FONT_SMALL  = ("Helvetica", 9)
FONT_LIST   = ("Helvetica", 11)
FONT_MONO   = ("Courier", 9)


def format_time(seconds):
    if seconds is None or seconds < 0:
        return "0:00"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def get_mp3_meta(path):
    meta = {"title": Path(path).stem, "artist": "Unknown", "album": "Unknown", "duration": 0}
    if HAS_MUTAGEN:
        try:
            audio = MP3(path)
            meta["duration"] = audio.info.length
            tags = ID3(path)
            if TIT2 in tags: meta["title"]  = str(tags[TIT2])
            if TPE1 in tags: meta["artist"] = str(tags[TPE1])
            if TALB in tags: meta["album"]  = str(tags[TALB])
        except Exception:
            pass
    return meta


def scan_directory(root_path):
    """Recursively find all MP3 files."""
    files = []
    for dirpath, _, filenames in os.walk(root_path):
        for f in sorted(filenames):
            if f.lower().endswith(".mp3"):
                files.append(os.path.join(dirpath, f))
    return sorted(files)


class MP3Player:
    def __init__(self, root):
        self.root = root
        self.root.title("SoundWave")
        self.root.configure(bg=BG)
        self.root.minsize(720, 580)
        self.root.geometry("820x640")

        # State
        self.playlist     = []   # list of dicts {path, title, artist, duration}
        self.current_idx  = -1
        self.is_playing   = False
        self.is_paused    = False
        self.duration     = 0
        self.seek_pos     = 0.0  # seconds elapsed (simulated)
        self._play_start  = 0    # wall-clock time when play started
        self._dragging    = False
        self.volume       = 0.7
        self.shuffle      = False
        self.repeat       = False  # repeat current track

        pygame.mixer.music.set_volume(self.volume)

        self._build_ui()
        self._poll_playback()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Left sidebar: controls + info
        left = tk.Frame(self.root, bg=BG, width=280)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)
        left.pack_propagate(False)

        # Right panel: playlist
        right = tk.Frame(self.root, bg=BG2)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_sidebar(left)
        self._build_playlist_panel(right)

    def _build_sidebar(self, parent):
        # App title
        hdr = tk.Frame(parent, bg=BG, pady=20)
        hdr.pack(fill=tk.X, padx=24)

        tk.Label(hdr, text="♪ SoundWave", font=FONT_TITLE,
                 bg=BG, fg=ACCENT).pack(anchor="w")
        tk.Label(hdr, text="MP3 Player", font=FONT_SMALL,
                 bg=BG, fg=TEXT_DIM).pack(anchor="w")

        sep = tk.Frame(parent, bg=BG3, height=1)
        sep.pack(fill=tk.X, padx=20)

        # Album art placeholder
        art_frame = tk.Frame(parent, bg=BG2, width=220, height=180)
        art_frame.pack(pady=20)
        art_frame.pack_propagate(False)

        self.art_canvas = tk.Canvas(art_frame, width=220, height=180,
                                    bg=BG2, highlightthickness=0)
        self.art_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_default_art()

        # Track info
        info = tk.Frame(parent, bg=BG)
        info.pack(fill=tk.X, padx=24)

        self.lbl_title = tk.Label(info, text="No track loaded",
                                  font=FONT_SONG, bg=BG, fg=TEXT,
                                  wraplength=220, justify="center")
        self.lbl_title.pack()

        self.lbl_artist = tk.Label(info, text="—",
                                   font=FONT_SUB, bg=BG, fg=TEXT_DIM)
        self.lbl_artist.pack(pady=(2, 0))

        self.lbl_album = tk.Label(info, text="",
                                  font=FONT_SMALL, bg=BG, fg=TEXT_DIM)
        self.lbl_album.pack()

        # Progress bar
        prog_frame = tk.Frame(parent, bg=BG)
        prog_frame.pack(fill=tk.X, padx=24, pady=(18, 0))

        time_row = tk.Frame(prog_frame, bg=BG)
        time_row.pack(fill=tk.X)
        self.lbl_elapsed = tk.Label(time_row, text="0:00", font=FONT_MONO,
                                    bg=BG, fg=TEXT_DIM)
        self.lbl_elapsed.pack(side=tk.LEFT)
        self.lbl_total = tk.Label(time_row, text="0:00", font=FONT_MONO,
                                  bg=BG, fg=TEXT_DIM)
        self.lbl_total.pack(side=tk.RIGHT)

        self.progress_var = tk.DoubleVar(value=0)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TScale",
                        background=BG, troughcolor=TRACK_BG,
                        sliderlength=14, sliderrelief="flat")
        self.progress_bar = ttk.Scale(prog_frame, from_=0, to=100,
                                      orient=tk.HORIZONTAL,
                                      variable=self.progress_var,
                                      style="Custom.Horizontal.TScale",
                                      command=self._on_seek_drag)
        self.progress_bar.pack(fill=tk.X, pady=4)
        self.progress_bar.bind("<ButtonPress-1>",   lambda e: setattr(self, '_dragging', True))
        self.progress_bar.bind("<ButtonRelease-1>", self._on_seek_release)

        # Controls
        ctrl = tk.Frame(parent, bg=BG)
        ctrl.pack(pady=12)

        btn_cfg = dict(bg=BG, fg=TEXT, relief="flat", cursor="hand2",
                       activebackground=HIGHLIGHT, activeforeground=ACCENT,
                       bd=0, padx=6, pady=4)

        self.btn_shuffle = tk.Button(ctrl, text="⇌", font=("Helvetica", 14),
                                     command=self._toggle_shuffle, **btn_cfg)
        self.btn_shuffle.grid(row=0, column=0, padx=4)

        tk.Button(ctrl, text="⏮", font=("Helvetica", 18),
                  command=self._prev_track, **btn_cfg).grid(row=0, column=1, padx=4)

        self.btn_play = tk.Button(ctrl, text="▶", font=("Helvetica", 22),
                                   command=self._play_pause, **btn_cfg)
        self.btn_play.grid(row=0, column=2, padx=6)

        tk.Button(ctrl, text="⏭", font=("Helvetica", 18),
                  command=self._next_track, **btn_cfg).grid(row=0, column=3, padx=4)

        self.btn_repeat = tk.Button(ctrl, text="↺", font=("Helvetica", 14),
                                    command=self._toggle_repeat, **btn_cfg)
        self.btn_repeat.grid(row=0, column=4, padx=4)

        # Volume
        vol_frame = tk.Frame(parent, bg=BG)
        vol_frame.pack(fill=tk.X, padx=24, pady=(4, 16))

        tk.Label(vol_frame, text="🔈", bg=BG, fg=TEXT_DIM,
                 font=("Helvetica", 11)).pack(side=tk.LEFT)

        self.vol_var = tk.DoubleVar(value=self.volume * 100)
        vol_slider = ttk.Scale(vol_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                               variable=self.vol_var,
                               style="Custom.Horizontal.TScale",
                               command=self._on_volume)
        vol_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        tk.Label(vol_frame, text="🔊", bg=BG, fg=TEXT_DIM,
                 font=("Helvetica", 11)).pack(side=tk.LEFT)

        # Open buttons
        sep2 = tk.Frame(parent, bg=BG3, height=1)
        sep2.pack(fill=tk.X, padx=20, pady=4)

        btn2_cfg = dict(bg=BG3, fg=TEXT_MID, relief="flat", cursor="hand2",
                        activebackground=SEL_BG, activeforeground=ACCENT,
                        bd=0, padx=12, pady=7, font=FONT_SUB)

        tk.Button(parent, text="📂  Open Folder", command=self._open_folder,
                  **btn2_cfg).pack(fill=tk.X, padx=16, pady=(8, 4))
        tk.Button(parent, text="➕  Add Files", command=self._add_files,
                  **btn2_cfg).pack(fill=tk.X, padx=16, pady=4)
        tk.Button(parent, text="🗑   Clear Playlist", command=self._clear_playlist,
                  **btn2_cfg).pack(fill=tk.X, padx=16, pady=4)

    def _build_playlist_panel(self, parent):
        # Header
        hdr = tk.Frame(parent, bg=BG2, pady=14)
        hdr.pack(fill=tk.X, padx=20)

        tk.Label(hdr, text="Playlist", font=("Helvetica", 14, "bold"),
                 bg=BG2, fg=TEXT).pack(side=tk.LEFT)
        self.lbl_count = tk.Label(hdr, text="0 tracks", font=FONT_SMALL,
                                  bg=BG2, fg=TEXT_DIM)
        self.lbl_count.pack(side=tk.LEFT, padx=10)

        # Search
        search_frame = tk.Frame(parent, bg=BG3, padx=12, pady=6)
        search_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        tk.Label(search_frame, text="🔍", bg=BG3, fg=TEXT_DIM,
                 font=("Helvetica", 11)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._on_search)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                bg=BG3, fg=TEXT, insertbackground=ACCENT,
                                relief="flat", font=FONT_LIST, bd=0)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        # Playlist listbox
        list_frame = tk.Frame(parent, bg=BG2)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 bg=BG3, troughcolor=BG2,
                                 relief="flat", bd=0, width=8)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame,
                                  bg=BG2, fg=TEXT_MID,
                                  selectbackground=SEL_BG,
                                  selectforeground=ACCENT,
                                  activestyle="none",
                                  relief="flat", bd=0,
                                  font=FONT_LIST,
                                  yscrollcommand=scrollbar.set,
                                  highlightthickness=0,
                                  cursor="hand2")
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        self.listbox.bind("<Double-Button-1>", self._on_double_click)
        self.listbox.bind("<Return>", self._on_double_click)

        # Status bar
        self.status_var = tk.StringVar(value="Ready  —  Open a folder or add files to get started.")
        status = tk.Label(parent, textvariable=self.status_var,
                          bg=BG3, fg=TEXT_DIM, font=FONT_SMALL,
                          anchor="w", padx=14, pady=6)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Art ───────────────────────────────────────────────────────────────────

    def _draw_default_art(self):
        c = self.art_canvas
        c.delete("all")
        # Background gradient approximation
        for i in range(180):
            ratio = i / 180
            r = int(0x22 + (0x0f - 0x22) * ratio)
            g = int(0x22 + (0x0f - 0x22) * ratio)
            b = int(0x2c + (0x13 - 0x2c) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            c.create_line(0, i, 220, i, fill=color)
        # Music note
        c.create_text(110, 90, text="♪", font=("Helvetica", 72),
                      fill=ACCENT, anchor="center")
        c.create_text(110, 155, text="No track selected",
                      font=FONT_SMALL, fill=TEXT_DIM, anchor="center")

    def _draw_playing_art(self, title, artist):
        c = self.art_canvas
        c.delete("all")
        for i in range(180):
            ratio = i / 180
            r = int(0x3b + (0x18 - 0x3b) * ratio)
            g = int(0x0f + (0x0f - 0x0f) * ratio)
            b = int(0x52 + (0x1f - 0x52) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            c.create_line(0, i, 220, i, fill=color)
        c.create_text(110, 70, text="♫", font=("Helvetica", 56),
                      fill="#e9d5ff", anchor="center")
        c.create_text(110, 130, text=title[:20], font=("Helvetica", 10, "bold"),
                      fill=TEXT, anchor="center")
        c.create_text(110, 150, text=artist[:24], font=FONT_SMALL,
                      fill="#c4b5fd", anchor="center")

    # ── Playlist Helpers ──────────────────────────────────────────────────────

    def _refresh_list(self, filter_text=""):
        self.listbox.delete(0, tk.END)
        ft = filter_text.lower()
        for i, t in enumerate(self.playlist):
            label = f"{t['artist']} — {t['title']}"
            if ft and ft not in label.lower():
                continue
            dur = f"  [{format_time(t['duration'])}]" if t['duration'] else ""
            self.listbox.insert(tk.END, f"  {label}{dur}")

        self.lbl_count.config(text=f"{len(self.playlist)} tracks")

        if self.current_idx >= 0:
            self.listbox.selection_clear(0, tk.END)
            idx = min(self.current_idx, self.listbox.size() - 1)
            self.listbox.selection_set(idx)
            self.listbox.see(idx)

    def _on_search(self, *args):
        self._refresh_list(self.search_var.get())

    # ── File I/O ──────────────────────────────────────────────────────────────

    def _open_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if not folder:
            return
        self.status_var.set(f"Scanning {folder} ...")
        self.root.update()

        def do_scan():
            files = scan_directory(folder)
            tracks = [get_mp3_meta(f) | {"path": f} for f in files]
            self.root.after(0, lambda: self._load_tracks(tracks, replace=True,
                                                          source=folder))
        threading.Thread(target=do_scan, daemon=True).start()

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Add MP3 Files",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if not paths:
            return
        tracks = [get_mp3_meta(p) | {"path": p} for p in paths]
        self._load_tracks(tracks, replace=False, source=f"{len(paths)} files")

    def _load_tracks(self, tracks, replace, source):
        if replace:
            self.playlist = tracks
        else:
            self.playlist.extend(tracks)
        self._refresh_list()
        n = len(tracks) if replace else len(tracks)
        self.status_var.set(f"Loaded {n} track(s) from {source}")
        if replace and self.playlist:
            self.current_idx = 0
            self._load_track(0)

    def _clear_playlist(self):
        self._stop()
        self.playlist = []
        self.current_idx = -1
        self._refresh_list()
        self.lbl_title.config(text="No track loaded")
        self.lbl_artist.config(text="—")
        self.lbl_album.config(text="")
        self.progress_var.set(0)
        self.lbl_elapsed.config(text="0:00")
        self.lbl_total.config(text="0:00")
        self._draw_default_art()
        self.status_var.set("Playlist cleared.")

    # ── Playback ──────────────────────────────────────────────────────────────

    def _load_track(self, idx):
        if idx < 0 or idx >= len(self.playlist):
            return
        self.current_idx = idx
        track = self.playlist[idx]
        self.duration = track["duration"]
        self.seek_pos = 0.0

        self.lbl_title.config(text=track["title"])
        self.lbl_artist.config(text=track["artist"])
        self.lbl_album.config(text=track["album"])
        self.lbl_total.config(text=format_time(self.duration))
        self.lbl_elapsed.config(text="0:00")
        self.progress_var.set(0)
        self._draw_playing_art(track["title"], track["artist"])

        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

        try:
            pygame.mixer.music.load(track["path"])
            pygame.mixer.music.play()
            self._play_start = time.time()
            self.is_playing = True
            self.is_paused = False
            self.btn_play.config(text="⏸")
            self.status_var.set(f"♪ Playing: {track['artist']} — {track['title']}")
        except Exception as e:
            messagebox.showerror("Playback Error", str(e))

    def _play_pause(self):
        if not self.playlist:
            return
        if self.current_idx < 0:
            self._load_track(0)
            return

        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self._pause_pos = time.time() - self._play_start
            self.btn_play.config(text="▶")
            self.status_var.set("Paused")
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self._play_start = time.time() - self._pause_pos
            self.is_paused = False
            self.btn_play.config(text="⏸")
            t = self.playlist[self.current_idx]
            self.status_var.set(f"♪ Playing: {t['artist']} — {t['title']}")
        else:
            self._load_track(self.current_idx)

    def _stop(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.btn_play.config(text="▶")

    def _next_track(self):
        if not self.playlist:
            return
        if self.shuffle:
            import random
            idx = random.randint(0, len(self.playlist) - 1)
        else:
            idx = (self.current_idx + 1) % len(self.playlist)
        self._load_track(idx)

    def _prev_track(self):
        if not self.playlist:
            return
        elapsed = time.time() - self._play_start if self.is_playing else 0
        if elapsed > 3:
            # restart current track
            self._load_track(self.current_idx)
        else:
            idx = (self.current_idx - 1) % len(self.playlist)
            self._load_track(idx)

    def _toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.btn_shuffle.config(fg=ACCENT if self.shuffle else TEXT)

    def _toggle_repeat(self):
        self.repeat = not self.repeat
        self.btn_repeat.config(fg=ACCENT if self.repeat else TEXT)

    def _on_double_click(self, event):
        sel = self.listbox.curselection()
        if sel:
            self._load_track(sel[0])

    # ── Volume / Seek ─────────────────────────────────────────────────────────

    def _on_volume(self, val):
        self.volume = float(val) / 100
        pygame.mixer.music.set_volume(self.volume)

    def _on_seek_drag(self, val):
        if self._dragging and self.duration > 0:
            pos = float(val) / 100 * self.duration
            self.lbl_elapsed.config(text=format_time(pos))

    def _on_seek_release(self, event):
        self._dragging = False
        if self.duration > 0:
            pct = self.progress_var.get() / 100
            pos = pct * self.duration
            pygame.mixer.music.play(start=pos)
            self._play_start = time.time() - pos
            self.is_playing = True
            self.is_paused = False
            self.btn_play.config(text="⏸")

    # ── Polling ───────────────────────────────────────────────────────────────

    def _poll_playback(self):
        if self.is_playing and not self.is_paused and not self._dragging:
            elapsed = time.time() - self._play_start
            self.lbl_elapsed.config(text=format_time(elapsed))

            if self.duration > 0:
                pct = min(elapsed / self.duration * 100, 100)
                self.progress_var.set(pct)

            # Check if track ended
            if not pygame.mixer.music.get_busy() and elapsed >= self.duration - 0.5 and self.duration > 0:
                self.is_playing = False
                if self.repeat:
                    self._load_track(self.current_idx)
                else:
                    self._next_track()

        self.root.after(500, self._poll_playback)


# ── Entry Point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    root.configure(bg=BG)

    # Try to set icon
    try:
        root.iconbitmap(default="")
    except Exception:
        pass

    app = MP3Player(root)

    # Handle keyboard shortcuts
    root.bind("<space>",      lambda e: app._play_pause())
    root.bind("<Right>",      lambda e: app._next_track())
    root.bind("<Left>",       lambda e: app._prev_track())
    root.bind("<Up>",         lambda e: app.vol_var.set(min(app.vol_var.get() + 5, 100)))
    root.bind("<Down>",       lambda e: app.vol_var.set(max(app.vol_var.get() - 5, 0)))

    root.mainloop()


if __name__ == "__main__":
    main()