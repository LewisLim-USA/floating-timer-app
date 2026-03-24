import os
import sys
import platform
import tkinter as tk
from tkinter import scrolledtext

if platform.system() == "Windows":
    try:
        import winsound
    except ImportError:
        winsound = None
else:
    winsound = None


class FloatingTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Floating Timer")
        self.root.geometry("420x360")
        self.root.minsize(320, 260)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#f4f6f8")

        self.total_seconds = 10 * 60
        self.remaining_seconds = self.total_seconds
        self.timer_running = True
        self.timer_finished = False
        self.after_id = None
        self.beep_count = 0

        self.drag_offset_x = 0
        self.drag_offset_y = 0

        self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.note_file = os.path.join(self.script_dir, "floating_timer_note.txt")

        self.install_startup()

        self.build_ui()
        self.load_note()
        self.start_timer()

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
            text=self.format_time(self.remaining_seconds),
            bg="#f4f6f8",
            fg="#102a43",
            font=("Segoe UI", 28, "bold")
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
            width=9,
            command=self.toggle_pause,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.pause_button.grid(row=0, column=0, padx=4, pady=4)

        self.reset_button = tk.Button(
            self.button_frame,
            text="Reset",
            width=9,
            command=self.reset_timer,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat"
        )
        self.reset_button.grid(row=0, column=1, padx=4, pady=4)

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
            height=7,
            font=("Segoe UI", 10)
        )
        self.textbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.save_button = tk.Button(
            self.main_frame,
            text="Save",
            command=self.save_note,
            bg="#9fb3c8",
            fg="#102a43",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            width=10
        )
        self.save_button.pack(pady=(0, 10))

        self.root.bind("<Control-s>", self.save_note_shortcut)

    def format_time(self, seconds):
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def update_display(self):
        self.time_label.config(text=self.format_time(self.remaining_seconds))

    def start_timer(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)

        if self.timer_running and self.remaining_seconds > 0:
            self.update_display()
            self.remaining_seconds -= 1
            self.after_id = self.root.after(1000, self.start_timer)
        elif self.remaining_seconds <= 0:
            self.remaining_seconds = 0
            self.update_display()
            self.timer_running = False
            self.timer_finished = True
            self.status_label.config(text="Time's up!")
            self.play_alarm()

    def toggle_pause(self):
        if self.timer_finished:
            return

        self.timer_running = not self.timer_running
        if self.timer_running:
            self.status_label.config(text="Running...")
            self.pause_button.config(text="Pause")
            self.start_timer()
        else:
            self.status_label.config(text="Paused")
            self.pause_button.config(text="Resume")
            if self.after_id:
                self.root.after_cancel(self.after_id)
                self.after_id = None

    def reset_timer(self):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.total_seconds = 10 * 60
        self.remaining_seconds = self.total_seconds
        self.timer_running = True
        self.timer_finished = False
        self.pause_button.config(text="Pause")
        self.status_label.config(text="Running...")
        self.update_display()
        self.start_timer()

    def renew_timer(self, minutes):
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.total_seconds = minutes * 60
        self.remaining_seconds = self.total_seconds
        self.timer_running = True
        self.timer_finished = False
        self.pause_button.config(text="Pause")
        self.status_label.config(text=f"Running... ({minutes} min)")
        self.update_display()
        self.start_timer()

    def toggle_topmost(self):
        current = self.root.attributes("-topmost")
        new_state = not current
        self.root.attributes("-topmost", new_state)
        self.pin_button.config(text=f"Top: {'ON' if new_state else 'OFF'}")

    def start_drag(self, event):
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def do_drag(self, event):
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    def play_alarm(self):
        self.root.bell()
        self.beep_count = 0
        self.do_beep()

    def do_beep(self):
        if self.beep_count >= 3:
            return

        self.beep_count += 1
        try:
            if winsound:
                winsound.Beep(1200, 300)
            else:
                self.root.bell()
        except Exception:
            self.root.bell()

        if self.beep_count < 3:
            self.root.after(180, self.do_beep)

    def save_note(self):
        try:
            text = self.textbox.get("1.0", "end-1c")
            with open(self.note_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.status_label.config(text="Saved")
        except Exception as e:
            self.status_label.config(text=f"Save failed: {e}")

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
            except Exception:
                pass

    def install_startup(self):
        if platform.system() != "Windows":
            return

        try:
            startup_dir = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            launcher_path = os.path.join(startup_dir, "FloatingTimerAutoStart.cmd")

            if getattr(sys, "frozen", False):
                target_exe = os.path.abspath(sys.executable)
                cmd_content = f'@echo off\nstart "" "{target_exe}"\n'
            else:
                python_exe = sys.executable
                if python_exe.lower().endswith("python.exe"):
                    pythonw_exe = python_exe[:-10] + "pythonw.exe"
                    if os.path.exists(pythonw_exe):
                        python_exe = pythonw_exe

                script_path = os.path.abspath(sys.argv[0])
                cmd_content = f'@echo off\nstart "" "{python_exe}" "{script_path}"\n'

            with open(launcher_path, "w", encoding="utf-8") as f:
                f.write(cmd_content)

        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = FloatingTimerApp(root)
    root.mainloop()