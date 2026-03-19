import tkinter as tk
from tkinter import messagebox
import winsound
import os
from datetime import datetime

DOCS_PATH = os.path.join(os.path.expanduser("~"), "Documents", "FloatingTimer")
LOG_FILE = os.path.join(DOCS_PATH, "log.txt")
CONFIG_FILE = os.path.join(DOCS_PATH, "config.txt")

os.makedirs(DOCS_PATH, exist_ok=True)

def load_last_duration():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return int(f.read().strip())
        except:
            return 600
    return 600

def save_duration(seconds):
    with open(CONFIG_FILE, "w") as f:
        f.write(str(seconds))

def write_log(message):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.now()} - {message}\n")

class FloatingTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Timer")
        self.root.attributes("-topmost", True)

        self.duration = load_last_duration()
        self.remaining = self.duration

        self.label = tk.Label(root, text="", font=("Arial", 24))
        self.label.pack(padx=20, pady=20)

        self.update_timer()

    def update_timer(self):
        mins, secs = divmod(self.remaining, 60)
        self.label.config(text=f"{mins:02}:{secs:02}")

        if self.remaining > 0:
            self.remaining -= 1
            self.root.after(1000, self.update_timer)
        else:
            self.time_up()

    def time_up(self):
        write_log("Timer finished")
        winsound.Beep(1000, 800)

        result = messagebox.askquestion(
            "Time's up!",
            "Renew timer?\nYes = 5 min\nNo = 10 min\nCancel = 20 min"
        )

        if result == "yes":
            self.restart(300)
        elif result == "no":
            self.restart(600)
        else:
            self.restart(1200)

    def restart(self, seconds):
        save_duration(seconds)
        write_log(f"Restarted with {seconds//60} minutes")
        self.remaining = seconds
        self.update_timer()

root = tk.Tk()
app = FloatingTimer(root)
root.mainloop()
