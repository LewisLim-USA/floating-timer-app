import os
import sys
import time
import queue
import platform
import threading
import traceback
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime

import psutil
import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

if platform.system() == "Windows":
    try:
        import winsound
    except ImportError:
        winsound = None
else:
    winsound = None


DEFAULT_MINUTES = 10
POWER_CHECK_INTERVAL = 4
TRIGGER_COOLDOWN_SECONDS = 60
RESTART_TIMER_ON_TRIGGER = False


class FloatingTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Floating Timer")
        self.root.geometry("640x430")
        self.root.minsize(520, 320)
        self.root.configure(bg="#f4f6f8")
        self.root.attributes("-topmost", True)

        self.is_pinned = True
        self.total_seconds = DEFAULT_MINUTES * 60
        self.remaining_seconds = self.total_seconds
        self.timer_running = True
        self.timer_finished = False
        self.after_id = None
        self.alarm_playing = False

        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.ui_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.tray_icon = None
        self.tray_thread = None

        self.last_trigger_ts = 0
        self.last_power_plugged = None

        self.base_dir = self.get_base_dir()
        self.note_file = os.path.join(self.base_dir, "floating_timer_note.txt")
        self.log_file = os.path.join(self.base_dir, "floating_timer_debug.log")

        self.build_ui()
        self.load_note()
        self.install_startup()
        self.start_background_watchers()
        self.start_tray_icon()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.root.bind("<Control-s>", self.save_note_shortcut)
        self.root.after(200, self.process_ui_queue)

        self.update_display()
        self.start_timer()

    def get_base_dir(self):
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(sys.argv[0]))

    def log_error(self, message):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass

    def build_ui(self):
        self.main_frame = tk.Frame(self.root, bg="#f4f6f8", bd=1, relief="solid")
        self.main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.top_bar = tk.Frame(self.main_frame, bg="#d9e2ec", height=30)
        self.top_bar.pack(fill="x")

        self.title_label = tk.Label(
            self.top_bar,
            text="Focus Timer",
            bg="#d9e2ec",
            fg="#102a43",
            font=("Segoe UI", 10, "bold")
        )
        self.title_label.pack(side="left", padx=10, pady=4)

        self.pin_button = tk.Button(
            self.top_bar,
            text="Top: ON",
            font=("Segoe UI", 8),
            command=self.toggle_topmost,
            bg="#bcccdc",
            fg="#102a43",
            relief="flat",
            padx=8
        )
        self.pin_button.pack(side="right", padx=6, pady=4)

        for widget in (self.top_bar, self.title_label):
            widget.bind("<Button-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.do_drag)

        self.time_label = tk.Label(
            self.main_frame,
            text="10:00",
            bg="#f4f6f8",
            fg="#102a43",
            font=("Segoe UI", 30, "bold")
        )
        self.time_label.pack(pady=(14, 4))

        self.status_label = tk.Label(
            self.main_frame,
            text="Running...",
            bg="#f4f6f8",
            fg="#486581",
            font=("Segoe UI", 10)
        )
        self.status_label.pack(pady=(0, 8))

        self.button_frame = tk.Frame(self.main_frame, bg="#f4f6f8")
        self.button_frame.pack(pady=4)

        self.pause_button = tk.Button(
            self.button_frame,
            text="Pause",
            width=11,
            command=self.toggle_pause,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.pause_button.grid(row=0, column=0, padx=4, pady=4)

        self.reset_button = tk.Button(
            self.button_frame,
            text="Reset 10",
            width=11,
            command=lambda: self.reset_timer(10, "Running..."),
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.reset_button.grid(row=0, column=1, padx=4, pady=4)

        self.hide_button = tk.Button(
            self.button_frame,
            text="Hide to Tray",
            width=11,
            command=self.hide_to_tray,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.hide_button.grid(row=0, column=2, padx=4, pady=4)

        self.test_alarm_button = tk.Button(
            self.button_frame,
            text="Test Alarm",
            width=11,
            command=self.play_alarm,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.test_alarm_button.grid(row=0, column=3, padx=4, pady=4)

        self.renew_frame = tk.Frame(self.main_frame, bg="#f4f6f8")
        self.renew_frame.pack(pady=(6, 8))

        self.renew_label = tk.Label(
            self.renew_frame,
            text="Renew:",
            bg="#f4f6f8",
            fg="#486581",
            font=("Segoe UI", 10, "bold")
        )
        self.renew_label.grid(row=0, column=0, padx=(0, 6))

        self.btn_5 = tk.Button(
            self.renew_frame,
            text="5 min",
            width=7,
            command=lambda: self.renew_timer(5),
            bg="#d9e2ec",
            fg="#102a43",
            relief="flat"
        )
        self.btn_5.grid(row=0, column=1, padx=3)

        self.btn_10 = tk.Button(
            self.renew_frame,
            text="10 min",
            width=7,
            command=lambda: self.renew_timer(10),
            bg="#d9e2ec",
            fg="#102a43",
            relief="flat"
        )
        self.btn_10.grid(row=0, column=2, padx=3)

        self.btn_20 = tk.Button(
            self.renew_frame,
            text="20 min",
            width=7,
            command=lambda: self.renew_timer(20),
            bg="#d9e2ec",
            fg="#102a43",
            relief="flat"
        )
        self.btn_20.grid(row=0, column=3, padx=3)

        self.note_label = tk.Label(
            self.main_frame,
            text="Write your stuff:",
            bg="#f4f6f8",
            fg="#102a43",
            font=("Segoe UI", 10, "bold")
        )
        self.note_label.pack(anchor="w", padx=12, pady=(8, 4))

        self.textbox = scrolledtext.ScrolledText(
            self.main_frame,
            wrap="word",
            height=8,
            font=("Segoe UI", 10)
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.bottom_frame = tk.Frame(self.main_frame, bg="#f4f6f8")
        self.bottom_frame.pack(pady=(0, 10))

        self.save_button = tk.Button(
            self.bottom_frame,
            text="Save",
            command=self.save_note,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            width=10
        )
        self.save_button.pack(side="left", padx=4)

        self.show_button = tk.Button(
            self.bottom_frame,
            text="Show Front",
            command=self.show_window,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            width=10
        )
        self.show_button.pack(side="left", padx=4)

    def format_time(self, seconds):
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def update_display(self):
        self.time_label.config(text=self.format_time(self.remaining_seconds))

    def start_timer(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        if self.timer_running:
            self.after_id = self.root.after(1000, self.timer_tick)

    def timer_tick(self):
        self.after_id = None

        if not self.timer_running:
            return

        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.update_display()

        if self.remaining_seconds <= 0:
            self.finish_timer()
        else:
            self.after_id = self.root.after(1000, self.timer_tick)

    def finish_timer(self):
        self.remaining_seconds = 0
        self.timer_running = False
        self.timer_finished = True
        self.update_display()
        self.status_label.config(text="Time's up!")
        self.show_window()
        self.play_alarm()

    def toggle_pause(self):
        if self.timer_finished:
            return

        self.timer_running = not self.timer_running
        if self.timer_running:
            self.pause_button.config(text="Pause")
            self.status_label.config(text="Running...")
            self.start_timer()
        else:
            self.pause_button.config(text="Resume")
            self.status_label.config(text="Paused")
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None

    def reset_timer(self, minutes=10, status_text="Running..."):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.total_seconds = minutes * 60
        self.remaining_seconds = self.total_seconds
        self.timer_running = True
        self.timer_finished = False
        self.pause_button.config(text="Pause")
        self.status_label.config(text=status_text)
        self.update_display()
        self.start_timer()

    def renew_timer(self, minutes):
        self.reset_timer(minutes, f"Running... ({minutes} min)")

    def toggle_topmost(self):
        self.is_pinned = not self.is_pinned
        self.root.attributes("-topmost", self.is_pinned)
        self.pin_button.config(text=f"Top: {'ON' if self.is_pinned else 'OFF'}")

    def start_drag(self, event):
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def do_drag(self, event):
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def play_alarm(self):
        if self.alarm_playing:
            return
        self.alarm_playing = True
        threading.Thread(target=self._alarm_worker, daemon=True).start()

    def _alarm_worker(self):
        try:
            if winsound:
                melody_1 = [
                    (523, 110),
                    (659, 110),
                    (784, 150),
                    (1047, 220),
                ]

                melody_2 = [
                    (659, 100),
                    (784, 120),
                    (988, 140),
                    (1319, 240),
                ]

                for freq, dur in melody_1:
                    winsound.Beep(freq, dur)
                    time.sleep(0.03)

                time.sleep(0.12)

                for freq, dur in melody_2:
                    winsound.Beep(freq, dur)
                    time.sleep(0.03)

                time.sleep(0.12)

                winsound.PlaySound(
                    "SystemExclamation",
                    winsound.SND_ALIAS | winsound.SND_ASYNC
                )
            else:
                self.root.after(0, self.root.bell)
        except Exception as e:
            self.log_error(f"Alarm sound failed: {e}")
            self.root.after(0, self.root.bell)
        finally:
            self.alarm_playing = False

    def save_note(self):
        try:
            text = self.textbox.get("1.0", "end-1c")
            with open(self.note_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.status_label.config(text="Saved")
        except Exception as e:
            self.status_label.config(text=f"Save failed: {e}")
            self.log_error(f"Save failed: {e}")

    def save_note_shortcut(self, event):
        self.save_note()
        return "break"

    def load_note(self):
        if os.path.exists(self.note_file):
            try:
                with open(self.note_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.textbox.delete("1.0", tk.END)
                self.textbox.insert("1.0", content)
            except Exception as e:
                self.log_error(f"Load note failed: {e}")

    def show_window(self):
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.attributes("-topmost", True)
            try:
                self.root.focus_force()
            except Exception:
                pass

            def restore_topmost():
                self.root.attributes("-topmost", self.is_pinned)

            self.root.after(1200, restore_topmost)
        except Exception as e:
            self.log_error(f"Show window failed: {e}")

    def hide_to_tray(self):
        try:
            self.root.withdraw()
            self.status_label.config(text="Hidden to tray")
        except Exception as e:
            self.log_error(f"Hide to tray failed: {e}")

    def create_tray_image(self):
        image = Image.new("RGB", (64, 64), "#2f6f91")
        draw = ImageDraw.Draw(image)
        draw.ellipse((8, 8, 56, 56), fill="#d9e2ec", outline="#102a43", width=3)
        draw.line((32, 18, 32, 32), fill="#102a43", width=3)
        draw.line((32, 32, 42, 40), fill="#102a43", width=3)
        return image

    def start_tray_icon(self):
        try:
            menu = pystray.Menu(
                item("Show Timer", lambda icon, menu_item: self.ui_queue.put(("show",))),
                item("Hide Timer", lambda icon, menu_item: self.ui_queue.put(("hide",))),
                pystray.Menu.SEPARATOR,
                item("Pause / Resume", lambda icon, menu_item: self.ui_queue.put(("toggle_pause",))),
                item("Reset 10 min", lambda icon, menu_item: self.ui_queue.put(("reset", 10))),
                item("Renew 5 min", lambda icon, menu_item: self.ui_queue.put(("reset", 5))),
                item("Renew 10 min", lambda icon, menu_item: self.ui_queue.put(("reset", 10))),
                item("Renew 20 min", lambda icon, menu_item: self.ui_queue.put(("reset", 20))),
                pystray.Menu.SEPARATOR,
                item("Test Alarm", lambda icon, menu_item: self.ui_queue.put(("test_alarm",))),
                pystray.Menu.SEPARATOR,
                item("Exit", lambda icon, menu_item: self.ui_queue.put(("exit",)))
            )

            self.tray_icon = pystray.Icon(
                "floating_timer",
                self.create_tray_image(),
                "Floating Timer",
                menu
            )

            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            self.log_error(f"Tray icon startup failed: {e}\n{traceback.format_exc()}")

    def process_ui_queue(self):
        try:
            while True:
                action = self.ui_queue.get_nowait()

                if not action:
                    continue

                command = action[0]

                if command == "show":
                    self.show_window()

                elif command == "hide":
                    self.hide_to_tray()

                elif command == "toggle_pause":
                    self.toggle_pause()

                elif command == "reset":
                    minutes = action[1]
                    status = "Running..." if minutes == 10 else f"Running... ({minutes} min)"
                    self.reset_timer(minutes, status)
                    self.show_window()

                elif command == "trigger":
                    reason = action[1]
                    self.handle_trigger_on_ui(reason)

                elif command == "test_alarm":
                    self.play_alarm()

                elif command == "exit":
                    self.exit_app()
                    return
        except queue.Empty:
            pass
        finally:
            if not self.stop_event.is_set():
                self.root.after(200, self.process_ui_queue)

    def handle_trigger_on_ui(self, reason):
        self.show_window()
        if RESTART_TIMER_ON_TRIGGER:
            self.reset_timer(DEFAULT_MINUTES, f"Triggered by: {reason}")
        else:
            self.status_label.config(text=f"Triggered by: {reason}")

    def maybe_trigger_popup(self, reason):
        now = time.time()
        if now - self.last_trigger_ts < TRIGGER_COOLDOWN_SECONDS:
            return

        self.last_trigger_ts = now
        self.ui_queue.put(("trigger", reason))

    def power_watcher_loop(self):
        while not self.stop_event.is_set():
            try:
                battery = psutil.sensors_battery()
                if battery is not None:
                    plugged = battery.power_plugged
                    if self.last_power_plugged is None:
                        self.last_power_plugged = plugged
                    else:
                        if plugged and not self.last_power_plugged:
                            self.maybe_trigger_popup("connected to charging power")
                        self.last_power_plugged = plugged
            except Exception as e:
                self.log_error(f"Power watcher failed: {e}")

            self.stop_event.wait(POWER_CHECK_INTERVAL)

    def start_background_watchers(self):
        threading.Thread(target=self.power_watcher_loop, daemon=True).start()

    def install_startup(self):
        if platform.system() != "Windows":
            return

        try:
            startup_dir = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            os.makedirs(startup_dir, exist_ok=True)

            launcher_path = os.path.join(startup_dir, "FloatingTimerAutoStart.cmd")

            if getattr(sys, "frozen", False):
                target = os.path.abspath(sys.executable)
                cmd_content = (
                    "@echo off\n"
                    f'cd /d "{os.path.dirname(target)}"\n'
                    f'start "" "{target}"\n'
                )
            else:
                python_exe = os.path.abspath(sys.executable)

                if python_exe.lower().endswith("python.exe"):
                    pythonw_candidate = python_exe[:-10] + "pythonw.exe"
                    if os.path.exists(pythonw_candidate):
                        python_exe = pythonw_candidate

                script_path = os.path.abspath(sys.argv[0])
                cmd_content = (
                    "@echo off\n"
                    f'cd /d "{os.path.dirname(script_path)}"\n'
                    f'start "" "{python_exe}" "{script_path}"\n'
                )

            with open(launcher_path, "w", encoding="utf-8") as f:
                f.write(cmd_content)

        except Exception as e:
            self.log_error(f"Startup install failed: {e}\n{traceback.format_exc()}")

    def exit_app(self):
        try:
            self.stop_event.set()

            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None

            self.save_note()

            if self.tray_icon is not None:
                try:
                    self.tray_icon.stop()
                except Exception as e:
                    self.log_error(f"Tray icon stop failed: {e}")

            self.root.destroy()
        except Exception as e:
            self.log_error(f"Exit failed: {e}\n{traceback.format_exc()}")
            try:
                self.root.destroy()
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = FloatingTimerApp(root)
    root.mainloop()