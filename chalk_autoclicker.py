import sys
import os
import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import ctypes
import ctypes.wintypes

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

try:
    import mouse
except ImportError:
    mouse = None

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    ImageTk = None

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(SCRIPT_DIR, "assets", "icon.png")

BG = "#1b1d26"
PANEL = "#22242f"
FIELD = "#2a2c38"
ACCENT = "#3ddc84"
OFF_GREY = "#4a4d5a"
TEXT = "#e7e8ec"
SUBTEXT = "#8b8e9c"
BORDER = "#33364a"


class RealClickTracker:
    """
    Tracks whether the left/right mouse button is REALLY, physically held
    down, using Windows' own "injected" flag on every low-level mouse
    event - this flag is set by the OS itself and definitively tells us
    whether an event came from real hardware or from software (SendInput),
    so our own synthetic clicks can never be confused for a real release.
    """

    WH_MOUSE_LL = 14
    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    LLMHF_INJECTED = 0x00000001

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class _MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", ctypes.c_long * 2),
            ("mouseData", ctypes.wintypes.DWORD),
            ("flags", ctypes.wintypes.DWORD),
            ("time", ctypes.wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    def __init__(self):
        self.left_down = False
        self.right_down = False
        self._hook_id = None
        self._proc = None
        self._user32 = None
        self._ready = False
        self.on_middle_down = None

        if sys.platform == "win32":
            self._HOOKPROC = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

    def note_synthetic_click(self, button):
        pass

    def _callback(self, nCode, wParam, lParam):
        try:
            if nCode == 0 and lParam:
                try:
                    info = ctypes.cast(lParam, ctypes.POINTER(self._MSLLHOOKSTRUCT)).contents
                    injected = bool(info.flags & self.LLMHF_INJECTED)
                except Exception:
                    injected = True  # fail safe: if we can't tell, don't trust it as real
                if not injected:
                    if wParam == self.WM_LBUTTONDOWN:
                        self.left_down = True
                    elif wParam == self.WM_LBUTTONUP:
                        self.left_down = False
                    elif wParam == self.WM_RBUTTONDOWN:
                        self.right_down = True
                    elif wParam == self.WM_RBUTTONUP:
                        self.right_down = False
                    elif wParam == self.WM_MBUTTONDOWN:
                        if self.on_middle_down is not None:
                            try:
                                self.on_middle_down()
                            except Exception:
                                pass
        except Exception:
            pass

        try:
            return self._user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)
        except Exception:
            return 0

    def start(self):
        if sys.platform != "win32":
            return
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            user32 = ctypes.windll.user32
            self._user32 = user32

            # Explicit, correct types for every call
            # what was missing last time and caused an uncaught overflow.
            user32.SetWindowsHookExA.restype = ctypes.c_void_p
            user32.SetWindowsHookExA.argtypes = [
                ctypes.c_int, self._HOOKPROC, ctypes.c_void_p, ctypes.wintypes.DWORD]

            user32.CallNextHookEx.restype = ctypes.c_long
            user32.CallNextHookEx.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]

            user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
            user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

            user32.GetMessageW.restype = ctypes.c_int
            user32.GetMessageW.argtypes = [
                ctypes.POINTER(ctypes.wintypes.MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]

            user32.TranslateMessage.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]
            user32.DispatchMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]

            self._proc = self._HOOKPROC(self._callback)
            self._hook_id = user32.SetWindowsHookExA(self.WH_MOUSE_LL, self._proc, None, 0)

            if not self._hook_id:
                return

            self._ready = True
            msg = ctypes.wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass


class MiniToggle(tk.Canvas):
    def __init__(self, master, initial=False, on_change=None):
        super().__init__(master, width=18, height=18, bg=PANEL, highlightthickness=0)
        self.state = initial
        self.on_change = on_change
        self.bind("<Button-1>", self._toggle)
        self.draw()

    def _toggle(self, event=None):
        self.state = not self.state
        self.draw()
        if self.on_change:
            self.on_change(self.state)

    def draw(self):
        self.delete("all")
        if self.state:
            self.create_rectangle(1, 1, 17, 17, fill=ACCENT, outline=ACCENT)
            self.create_text(9, 9, text="\u2713", fill="#0e0f14", font=("Segoe UI", 10, "bold"))
        else:
            self.create_rectangle(1, 1, 17, 17, fill=FIELD, outline=OFF_GREY)


class ChalksAutoclicker:
    TOGGLE_OPTIONS = ["F6", "F7", "F8", "Mouse 3 (Middle)", "Mouse 4 (Back)", "Mouse 5 (Forward)"]

    def __init__(self, root):
        self.root = root
        self.root.title("Chalkclicker")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.configure(highlightbackground=BORDER, highlightthickness=1)
        self._drag_offset = (0, 0)
        self._apply_window_icon()

        self.enabled = False
        self.is_clicking = False
        self.actual_clicks_this_second = 0
        self._cached_low = 8
        self._cached_high = 12
        self._cached_right_click = False
        self._last_toggle_time = 0.0

        self._current_hotkey_down = None
        self._current_hotkey_up = None
        self._current_mouse_hook = None
        self.tray_icon = None
        self.compact_win = None
        self.compact_x = None  # None = auto-position at screen edge
        self.compact_y = None
        self.settings_win = None
        self.real_click_tracker = RealClickTracker()
        self.real_click_tracker.start()

        self._build_title_bar()
        self._build_ui()
        self._bind_toggle_button()
        self._update_cps_display_loop()

        threading.Thread(target=self._click_poll_loop, daemon=True).start()

        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        self.root.geometry(f"{w}x{h}")

        # Tray icon is always present from launch, not just while minimized
        self._ensure_tray_icon()

        if mouse is None or keyboard is None:
            missing = [n for n, m in (("mouse", mouse), ("keyboard", keyboard)) if m is None]
            self._show_missing_packages(missing)

    # ---------------- Custom title bar ----------------
    def _build_title_bar(self):
        bar = tk.Frame(self.root, bg="#14151c", height=26)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        label = tk.Label(bar, text="Chalkclicker", bg="#14151c", fg=SUBTEXT,
                          font=("Segoe UI", 8, "bold"))
        label.pack(side="left", padx=8)

        close_btn = tk.Label(bar, text="\u2715", bg="#14151c", fg=SUBTEXT, font=("Segoe UI", 9), cursor="hand2")
        close_btn.pack(side="right", padx=(0, 8))
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg="#ff5f56"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=SUBTEXT))
        close_btn.bind("<Button-1>", lambda e: self._on_close())

        min_btn = tk.Label(bar, text="\u2014", bg="#14151c", fg=SUBTEXT, font=("Segoe UI", 9), cursor="hand2")
        min_btn.pack(side="right", padx=(0, 4))
        min_btn.bind("<Enter>", lambda e: min_btn.config(fg=TEXT))
        min_btn.bind("<Leave>", lambda e: min_btn.config(fg=SUBTEXT))
        # Shrinks to a small floating ON/OFF widget instead of going to
        # tray: closing (X) is still what sends it to the tray.
        min_btn.bind("<Button-1>", lambda e: self._enter_compact_mode())

        for widget in (bar, label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag_move)

    def _start_drag(self, event):
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _on_drag_move(self, event):
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    # ---------------- UI ----------------
    def _build_ui(self):
        content = tk.Frame(self.root, bg=BG)
        content.pack(padx=5, pady=5)
        self.main_content = content

        top_row = tk.Frame(content, bg=BG)
        top_row.pack(pady=(0, 5), fill="x")

        self.cps_number_label = tk.Label(top_row, text="0", bg=BG, fg=ACCENT, font=("Segoe UI", 16, "bold"))
        self.cps_number_label.pack(side="left", padx=(0, 6))

        self.status_label = tk.Label(top_row, text="DISARMED", bg=BG, fg="#e74c3c", font=("Segoe UI", 8, "bold"))
        self.status_label.pack(side="left")

        panel = tk.Frame(content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        panel.pack(fill="x")

        tk.Label(panel, text="CPS RANGE", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 7, "bold")).pack(pady=(6, 3))

        range_row = tk.Frame(panel, bg=PANEL)
        range_row.pack(pady=(0, 5))

        self.min_cps_var = tk.StringVar(value="8")
        self.max_cps_var = tk.StringVar(value="12")

        min_box = tk.Entry(range_row, textvariable=self.min_cps_var, width=3, justify="center",
                            bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                            font=("Segoe UI", 9, "bold"))
        min_box.pack(side="left", ipady=2)
        min_box.bind("<FocusOut>", lambda e: self._clamp_range())
        min_box.bind("<Return>", lambda e: self._clamp_range())

        tk.Label(range_row, text=" to ", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="left")

        max_box = tk.Entry(range_row, textvariable=self.max_cps_var, width=3, justify="center",
                            bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat",
                            font=("Segoe UI", 9, "bold"))
        max_box.pack(side="left", ipady=2)
        max_box.bind("<FocusOut>", lambda e: self._clamp_range())
        max_box.bind("<Return>", lambda e: self._clamp_range())

        tk.Label(range_row, text=" CPS", bg=PANEL, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="left")

        tk.Frame(panel, bg=BORDER, height=1).pack(fill="x", padx=6)

        toggles_col = tk.Frame(panel, bg=PANEL)
        toggles_col.pack(pady=5, padx=6, fill="x")

        overlay_cell = tk.Frame(toggles_col, bg=PANEL)
        overlay_cell.pack(fill="x", anchor="w")
        self.overlay_toggle = MiniToggle(overlay_cell, initial=True, on_change=self._on_overlay_change)
        self.overlay_toggle.pack(side="left")
        tk.Label(overlay_cell, text="OVERLAY", bg=PANEL, fg=TEXT, font=("Segoe UI", 8, "bold")).pack(
            side="left", padx=(4, 0))

        rc_cell = tk.Frame(toggles_col, bg=PANEL)
        rc_cell.pack(fill="x", anchor="w", pady=(4, 0))
        self.right_click_toggle = MiniToggle(rc_cell, initial=False, on_change=self._on_right_click_change)
        self.right_click_toggle.pack(side="left")
        tk.Label(rc_cell, text="RIGHT CLICK", bg=PANEL, fg=TEXT, font=("Segoe UI", 8, "bold")).pack(
            side="left", padx=(4, 0))

        toggle_row = tk.Frame(panel, bg=PANEL)
        toggle_row.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(toggle_row, text="TOGGLE", bg=PANEL, fg=SUBTEXT,
                 font=("Segoe UI", 7, "bold")).pack(side="left")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT,
                         arrowcolor=TEXT, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD)
        style.map("Dark.TCombobox", fieldbackground=[("readonly", FIELD)])

        self.toggle_choice = tk.StringVar(value="Mouse 3 (Middle)")
        combo = ttk.Combobox(toggle_row, textvariable=self.toggle_choice, values=self.TOGGLE_OPTIONS,
                              state="readonly", style="Dark.TCombobox", width=11, font=("Segoe UI", 8))
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self._bind_toggle_button())

        self.bind_status_label = tk.Label(content, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 7))
        self.bind_status_label.pack(pady=(4, 0), anchor="w")

        self.root.attributes("-topmost", True)

    def _clamp_range(self):
        try:
            low = int(float(self.min_cps_var.get()))
        except ValueError:
            low = 1
        try:
            high = int(float(self.max_cps_var.get()))
        except ValueError:
            high = 1
        low = max(1, min(999, low))
        high = max(1, min(999, high))
        if low > high:
            low, high = high, low
        self.min_cps_var.set(str(low))
        self.max_cps_var.set(str(high))
        self._cached_low = low
        self._cached_high = high

    # ---------------- Toggle button binding ----------------
    def _bind_toggle_button(self):
        if keyboard is not None:
            for handle in (self._current_hotkey_down, self._current_hotkey_up):
                if handle:
                    try:
                        keyboard.unhook(handle)
                    except Exception:
                        pass
            self._current_hotkey_down = None
            self._current_hotkey_up = None
        if self._current_mouse_hook and mouse is not None:
            try:
                mouse.unhook(self._current_mouse_hook)
            except Exception:
                pass
            self._current_mouse_hook = None
        self.real_click_tracker.on_middle_down = None

        choice = self.toggle_choice.get()
        error = None
        if choice.startswith("F"):
            if keyboard is None:
                error = "'keyboard' package not installed"
            else:
                key = choice.lower()
                try:
                    self._current_hotkey_down = keyboard.on_press_key(
                        key, lambda e: self._on_toggle_key_event("DOWN"))
                    self._current_hotkey_up = keyboard.on_release_key(
                        key, lambda e: self._on_toggle_key_event("UP"))
                except Exception as e:
                    error = str(e)
        elif choice == "Mouse 3 (Middle)":
            self.real_click_tracker.on_middle_down = lambda: self._on_toggle_key_event("DOWN")
        elif choice.startswith("Mouse"):
            if mouse is None:
                error = "'mouse' package not installed"
            else:
                button_map = {"Mouse 4 (Back)": "x", "Mouse 5 (Forward)": "x2"}
                btn = button_map.get(choice)
                if btn:
                    def handler(event):
                        if isinstance(event, mouse.ButtonEvent) and event.button == btn:
                            if event.event_type == "down":
                                self._on_toggle_key_event("DOWN")
                            elif event.event_type == "up":
                                self._on_toggle_key_event("UP")
                    try:
                        self._current_mouse_hook = mouse.hook(handler)
                    except Exception as e:
                        error = str(e)

        if error:
            self.bind_status_label.config(text=f"Not listening: {error} (try Run as Administrator)",
                                           fg="#e74c3c")
        else:
            self.bind_status_label.config(text=f"Toggle key: {choice}", fg=ACCENT)

    def _on_toggle_key_event(self, direction):
        if direction != "DOWN":
            return
        now = time.time()
        if now - self._last_toggle_time < 0.25:
            return
        self._last_toggle_time = now
        self.root.after(0, self.toggle_enabled)

    def _on_overlay_change(self, state):
        self.root.attributes("-topmost", state)

    def _on_right_click_change(self, state):
        self._cached_right_click = state

    def _show_missing_packages(self, missing):
        top = tk.Toplevel(self.root, bg=BG)
        top.title("Missing packages")
        msg = ("Please install the following before this works fully:\n\n"
               f"pip install {' '.join(missing)}")
        tk.Label(top, text=msg, bg=BG, fg=TEXT, justify="left", padx=16, pady=16).pack()

    # ---------------- Toggle (arm/disarm) ----------------
    def toggle_enabled(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.status_label.config(text="ARMED", fg=ACCENT)
        else:
            self.status_label.config(text="DISARMED", fg="#e74c3c")
        self._refresh_compact_widget()

    # ---------------- Compact mode ----------------
    def _enter_compact_mode(self):
        if self.compact_win is not None:
            return
        self.root.withdraw()

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BG, highlightbackground=BORDER, highlightthickness=1)

        row = tk.Frame(win, bg=BG)
        row.pack(padx=8, pady=6)

        dot = tk.Canvas(row, width=14, height=14, bg=BG, highlightthickness=0)
        dot.pack(side="left", padx=(0, 6))
        label = tk.Label(row, text="", bg=BG, fg=TEXT, font=("Segoe UI", 9, "bold"))
        label.pack(side="left")


        self.compact_win = win
        self.compact_dot = dot
        self.compact_label = label
        self._refresh_compact_widget()  # sets the ON/OFF text first...
        self._apply_compact_position()  # ...then size the window to fit it

    def _apply_compact_position(self):
        win = self.compact_win
        if win is None:
            return
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        if self.compact_x is not None and self.compact_y is not None:
            x, y = self.compact_x, self.compact_y
        else:
            screen_w = win.winfo_screenwidth()
            screen_h = win.winfo_screenheight()
            x = screen_w - w - 12
            y = screen_h // 2 - h // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _refresh_compact_widget(self):
        win = self.compact_win
        if win is None:
            return
        color = ACCENT if self.enabled else "#e74c3c"
        text = "ON" if self.enabled else "OFF"
        self.compact_dot.delete("all")
        self.compact_dot.create_oval(2, 2, 12, 12, fill=color, outline=color)
        self.compact_label.config(text=text, fg=color)
        self._apply_compact_position()

    def _exit_compact_mode(self):
        win = self.compact_win
        if win is not None:
            win.destroy()
            self.compact_win = None
        self.root.deiconify()
        self.root.attributes("-topmost", self.overlay_toggle.state)

    def _open_settings_dialog(self):
        if getattr(self, "settings_win", None) is not None:
            try:
                self.settings_win.lift()
                return
            except Exception:
                pass

        win = tk.Toplevel(self.root)
        self.settings_win = win
        win.title("Settings")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.attributes("-topmost", True)

        def on_close():
            self.settings_win = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        pad = {"padx": 14}
        tk.Label(win, text="Minimized Widget Position", bg=BG, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(pady=(14, 4), **pad)
        tk.Label(win, text="Screen X / Y coordinates for the small ON/OFF box\n"
                            "shown while minimized. Leave blank for automatic\n"
                            "placement at the right edge of the screen.",
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 8), justify="left").pack(pady=(0, 10), **pad)

        row = tk.Frame(win, bg=BG)
        row.pack(pady=(0, 6), **pad)

        tk.Label(row, text="X:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        x_var = tk.StringVar(value=str(self.compact_x) if self.compact_x is not None else "")
        x_entry = tk.Entry(row, textvariable=x_var, width=6, justify="center",
                            bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        x_entry.pack(side="left", padx=(4, 12), ipady=2)

        tk.Label(row, text="Y:", bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(side="left")
        y_var = tk.StringVar(value=str(self.compact_y) if self.compact_y is not None else "")
        y_entry = tk.Entry(row, textvariable=y_var, width=6, justify="center",
                            bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 9))
        y_entry.pack(side="left", padx=(4, 0), ipady=2)

        def save():
            x_text, y_text = x_var.get().strip(), y_var.get().strip()
            if x_text == "" and y_text == "":
                self.compact_x, self.compact_y = None, None
            else:
                try:
                    self.compact_x = int(x_text)
                    self.compact_y = int(y_text)
                except ValueError:
                    status.config(text="X and Y must both be whole numbers, or both left blank.",
                                   fg="#e74c3c")
                    return
            self._apply_compact_position()
            status.config(text="Saved.", fg=ACCENT)

        def use_default():
            x_var.set("")
            y_var.set("")
            self.compact_x, self.compact_y = None, None
            self._apply_compact_position()
            status.config(text="Reset to automatic placement.", fg=ACCENT)

        btn_row = tk.Frame(win, bg=BG)
        btn_row.pack(pady=(6, 4), **pad)
        tk.Button(btn_row, text="Save", command=save, bg=ACCENT, fg="#0e0f14",
                  relief="flat", font=("Segoe UI", 9, "bold"), padx=10).pack(side="left", padx=(0, 8))
        tk.Button(btn_row, text="Use Default", command=use_default, bg=FIELD, fg=TEXT,
                  relief="flat", font=("Segoe UI", 9), padx=10).pack(side="left")

        status = tk.Label(win, text="", bg=BG, fg=SUBTEXT, font=("Segoe UI", 8))
        status.pack(pady=(4, 14), **pad)



    # ---------------- Click-while-held logic ----------------
    def _click_poll_loop(self):
        # Runs for the whole app lifetime on its own background thread.
        # Uses RealClickTracker, which only trusts genuine (non-injected)
        # mouse events where our own synthetic clicks never confuse it, unlike
        # a plain Windows button-state query would.
        release_streak = 0
        while True:
            if self.enabled and mouse is not None:
                right = self._cached_right_click
                really_held = self.real_click_tracker.right_down if right else self.real_click_tracker.left_down
                if really_held:
                    release_streak = 0
                    if not self.is_clicking:
                        self.is_clicking = True
                        self.root.after(0, lambda: self.status_label.config(text="CLICKING...", fg=ACCENT))
                    low = max(1, min(999, self._cached_low))
                    high = max(low, min(999, self._cached_high))
                    cps = random.uniform(low, high)
                    interval = 1.0 / cps if cps > 0 else 0.1
                    button = "right" if right else "left"
                    try:
                        self.real_click_tracker.note_synthetic_click(button)
                        mouse.click(button)
                        self.actual_clicks_this_second += 1
                    except Exception:
                        pass
                    time.sleep(interval)
                    continue
                else:
                    release_streak += 1
                    if self.is_clicking and release_streak >= 2:
                        self.is_clicking = False
                        self.root.after(0, lambda: self.status_label.config(text="ARMED", fg=ACCENT))
            else:
                release_streak = 0
                if self.is_clicking:
                    self.is_clicking = False
            time.sleep(0.01)

    def _update_cps_display_loop(self):
        displayed = self.actual_clicks_this_second
        self.actual_clicks_this_second = 0
        self.cps_number_label.config(text=str(displayed))
        self.root.after(1000, self._update_cps_display_loop)

    # ---------------- Icons ----------------
    def _apply_window_icon(self):
        # Uses Pillow to decode the PNG rather than Tk's own built-in
        if not os.path.isfile(ICON_PATH):
            return
        try:
            if Image is not None and ImageTk is not None:
                pil_img = Image.open(ICON_PATH).convert("RGBA")
                self._window_icon_image = ImageTk.PhotoImage(pil_img)
            else:
                self._window_icon_image = tk.PhotoImage(file=ICON_PATH)
            self.root.iconphoto(True, self._window_icon_image)
        except Exception:
            pass

    # ---------------- System tray ----------------
    def _make_tray_image(self):
        if os.path.isfile(ICON_PATH) and Image is not None:
            try:
                return Image.open(ICON_PATH)
            except Exception:
                pass
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, 60, 60), fill=(61, 220, 132, 255))
        draw.text((22, 18), "C", fill=(14, 15, 20, 255))
        return img

    def _ensure_tray_icon(self):
        if pystray is None or self.tray_icon is not None:
            return
        image = self._make_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("Expand", self._tray_expand, default=True),
            pystray.MenuItem("Settings", self._tray_open_settings),
            pystray.MenuItem("Exit", self._tray_exit),
        )
        self.tray_icon = pystray.Icon("chalks_autoclicker", image, "Chalkclicker", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _stop_tray_icon(self):
        if self.tray_icon is not None:
            self.tray_icon.stop()
            self.tray_icon = None

    def _tray_expand(self, icon=None, item=None):
        self.root.after(0, self._do_expand)

    def _do_expand(self):
        if self.compact_win is not None:
            self.compact_win.destroy()
            self.compact_win = None
        self.root.deiconify()
        self.root.attributes("-topmost", self.overlay_toggle.state)

    def _tray_open_settings(self, icon=None, item=None):
        self.root.after(0, self._open_settings_dialog)

    def _tray_exit(self, icon=None, item=None):
        self.root.after(0, self._do_exit)

    def _do_exit(self):
        self._stop_tray_icon()
        self.root.destroy()

    def _on_close(self):
        self._stop_tray_icon()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ChalksAutoclicker(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
