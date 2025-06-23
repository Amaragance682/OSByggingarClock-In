import tkinter as tk
from tkinter import ttk
import os
from datetime import datetime
from utils import (
    load_users,
    load_employee_logs,
    now_trimmed,
    format_duration,
)

COMPANY_FOLDER = "Fyrirtaeki"

class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin View – Employee Shift Monitor")
        self.geometry("800x600")
        self.configure(bg="#f4f4f4")

        self.users = load_users()
        self.company_var = tk.StringVar()

        self.create_widgets()

    def create_widgets(self):
        title = tk.Label(self, text="Admin Shift Monitor", font=("Helvetica", 18, "bold"), bg="#f4f4f4")
        title.pack(pady=10)

        # Company dropdown
        company_frame = tk.Frame(self, bg="#f4f4f4")
        company_frame.pack()

        tk.Label(company_frame, text="Select Company:", bg="#f4f4f4", font=("Helvetica", 12)).pack(side=tk.LEFT)
        self.company_dropdown = ttk.Combobox(company_frame, textvariable=self.company_var, state="readonly", font=("Helvetica", 12))
        self.company_dropdown.pack(side=tk.LEFT, padx=10)

        self.company_dropdown["values"] = self.get_company_names()
        self.company_dropdown.bind("<<ComboboxSelected>>", self.refresh_display)

        # Scrollable canvas
        self.canvas = tk.Canvas(self, bg="#f4f4f4", highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Outer scrollable frame
        self.scroll_frame = tk.Frame(self.canvas, bg="#f4f4f4")
        self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # 🔧 Add horizontal layout: two columns inside scroll_frame
        self.left_frame = tk.Frame(self.scroll_frame, bg="#f4f4f4")   # For Currently Working
        self.right_frame = tk.Frame(self.scroll_frame, bg="#f4f4f4")  # For Finished Today

        self.left_frame.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=10)

    def get_company_names(self):
        return [
            name for name in os.listdir(COMPANY_FOLDER)
            if os.path.isdir(os.path.join(COMPANY_FOLDER, name))
        ]

    def refresh_display(self, *args):
        for widget in self.left_frame.winfo_children():
            widget.destroy()
        for widget in self.right_frame.winfo_children():
            widget.destroy()

        company = self.company_var.get()
        if not company:
            return

        today = datetime.now().date()
        users = [u for u in self.users if u["company"] == company]

        active = []
        finished = []

        for user in users:
            logs = load_employee_logs(user)
            for log in logs:
                start_dt = datetime.fromisoformat(log["clock_in"])
                if start_dt.date() != today:
                    continue

                end = log.get("clock_out")
                task = log.get("task", "N/A")
                location = log.get("location", "N/A")

                if end is None:
                    duration = format_duration(log["clock_in"], now_trimmed(), ongoing=True)
                    active.append((user["name"], user["id"], task, location, log["clock_in"], None, duration))
                else:
                    duration = format_duration(log["clock_in"], end)
                    finished.append((user["name"], user["id"], task, location, log["clock_in"], end, duration))

        if active:
            tk.Label(self.left_frame, text="⏳ Currently Working", font=("Helvetica", 14, "bold"), bg="#f4f4f4", fg="#f49301").pack(anchor="w", padx=10, pady=5)
            for info in active:
                self.make_card(info, active=True, parent=self.left_frame)

        if finished:
            tk.Label(self.right_frame, text="✅ Finished Shifts Today", font=("Helvetica", 14, "bold"), bg="#f4f4f4", fg="#00fb04").pack(anchor="w", padx=10, pady=10)
            for info in finished:
                self.make_card(info, active=False, parent=self.right_frame)

    def make_card(self, info, active=True, parent=None):
        name, uid, task, location, clock_in, clock_out, duration = info
        icon = "⏳" if active else "✅"
        title = f"{icon} {name} "

        frame = tk.LabelFrame(parent or self.scroll_frame, text=title, font=("Helvetica", 12, "bold"), bg="white", padx=10, pady=5)
        frame.pack(fill="x", padx=15, pady=5)

        tk.Label(frame, text=f"Task: {task}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Location: {location}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Clock-in: {clock_in[11:16]}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")

        if clock_out:
            tk.Label(frame, text=f"Clock-out: {clock_out[11:16]}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")

        tk.Label(frame, text=f"{duration}", font=("Helvetica", 11, "italic"), bg="white", fg="gray").pack(anchor="w")

if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
