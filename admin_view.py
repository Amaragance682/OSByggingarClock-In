import tkinter as tk
from tkinter import ttk
import os
from datetime import datetime, timedelta
from utils import (
    load_users,
    load_task_config,
    load_employee_logs,
    now_trimmed,
    format_duration,
    get_locations_for_user,
    get_tasks_for_user
)

COMPANY_FOLDER = "Fyrirtaeki"

class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Admin View – Employee Shift Monitor")
        self.geometry("1000x700")
        self.configure(bg="#f4f4f4")

        self.users = load_users()
        self.task_config = load_task_config()

        self.time_range_var = tk.StringVar(value="Today")
        self.location_var = tk.StringVar(value="Any")
        self.company_var = tk.StringVar(value="Any")
        self.task_var = tk.StringVar(value="Any")

        self.create_navigation()
        self.create_shift_viewer()

    def create_navigation(self):
        nav_frame = tk.Frame(self, bg="#d9e6f2")
        nav_frame.pack(fill="x")

        self.nav_buttons = {}

        for name in ["Shift Viewer", "Handle Requests", "Edit Database", "Control Board"]:
            btn = tk.Button(nav_frame, text=name, font=("Helvetica", 12, "bold"), command=lambda n=name: self.switch_page(n))
            btn.pack(side="left", padx=10, pady=5)
            self.nav_buttons[name] = btn

    def switch_page(self, name):
        if name == "Shift Viewer":
            self.show_shift_viewer()
        else:
            self.clear_main_area()
            placeholder = tk.Label(self.main_area, text=f"{name} page coming soon...", font=("Helvetica", 16))
            placeholder.pack(pady=20)

    def clear_main_area(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    def create_shift_viewer(self):
        self.main_area = tk.Frame(self, bg="#f4f4f4")
        self.main_area.pack(fill="both", expand=True)
        self.show_shift_viewer()

    def show_shift_viewer(self):
        self.clear_main_area()

        filter_frame = tk.Frame(self.main_area, bg="#e9f0f8")
        filter_frame.pack(fill="x", pady=10)

        tk.Label(filter_frame, text="Time Range:").pack(side="left", padx=5)
        self.time_range_dropdown = ttk.Combobox(filter_frame, textvariable=self.time_range_var, state="readonly", width=15)
        self.time_range_dropdown['values'] = ["Today", "Last 3 Days", "Last 7 Days", "Last 30 Days"]
        self.time_range_dropdown.pack(side="left", padx=5)
        self.time_range_dropdown.bind("<<ComboboxSelected>>", self.refresh_shifts)

        tk.Label(filter_frame, text="Location:").pack(side="left", padx=5)
        self.location_dropdown = ttk.Combobox(filter_frame, textvariable=self.location_var, state="readonly")
        self.location_dropdown.pack(side="left", padx=5)
        self.location_dropdown.bind("<<ComboboxSelected>>", self.on_location_selected)

        tk.Label(filter_frame, text="Company:").pack(side="left", padx=5)
        self.company_dropdown = ttk.Combobox(filter_frame, textvariable=self.company_var, state="readonly")
        self.company_dropdown.pack(side="left", padx=5)
        self.company_dropdown.bind("<<ComboboxSelected>>", self.on_company_selected)

        tk.Label(filter_frame, text="Task:").pack(side="left", padx=5)
        self.task_dropdown = ttk.Combobox(filter_frame, textvariable=self.task_var, state="readonly", width=40)
        self.task_dropdown.pack(side="left", padx=5)
        self.task_dropdown.bind("<<ComboboxSelected>>", self.refresh_shifts)

        self.shift_canvas = tk.Canvas(self.main_area, bg="#f4f4f4", highlightthickness=0)
        self.shift_scrollbar = tk.Scrollbar(self.main_area, orient="vertical", command=self.shift_canvas.yview)
        self.shift_canvas.configure(yscrollcommand=self.shift_scrollbar.set)
        self.shift_canvas.pack(side="left", fill="both", expand=True)
        self.shift_scrollbar.pack(side="right", fill="y")

        self.shift_frame = tk.Frame(self.shift_canvas, bg="#f4f4f4")
        self.shift_canvas.create_window((0, 0), window=self.shift_frame, anchor="nw")
        self.shift_frame.bind("<Configure>", lambda e: self.shift_canvas.configure(scrollregion=self.shift_canvas.bbox("all")))

        self.refresh_shifts()

    def on_location_selected(self, event=None):
        self.company_var.set("Any")
        self.task_var.set("Any")
        self.refresh_shifts()

    def on_company_selected(self, event=None):
        self.task_var.set("Any")
        self.refresh_shifts()

    def get_company_names(self):
        return [name for name in os.listdir(COMPANY_FOLDER)
                if os.path.isdir(os.path.join(COMPANY_FOLDER, name))]

    def refresh_shifts(self, event=None):
        for widget in self.shift_frame.winfo_children():
            widget.destroy()

        company = self.company_var.get()
        location = self.location_var.get()
        task_filter = self.task_var.get()
        time_range = self.time_range_var.get()

        today = datetime.now().date()
        if time_range == "Today":
            start_date = today
        elif time_range == "Last 3 Days":
            start_date = today - timedelta(days=2)
        elif time_range == "Last 7 Days":
            start_date = today - timedelta(days=6)
        elif time_range == "Last 30 Days":
            start_date = today - timedelta(days=29)
        else:
            start_date = today

        users = [u for u in self.users if (company == "Any" or u["company"] == company)]

        active, finished = [], []
        used_locations = set()
        used_tasks = set()
        used_companies = set()

        for user in users:
            logs = load_employee_logs(user)
            for log in logs:
                start_dt = datetime.fromisoformat(log["clock_in"]).date()
                if not (start_date <= start_dt <= today):
                    continue
                used_locations.add(log.get("location"))
                used_tasks.add(log.get("task"))
                used_companies.add(user["company"])

                if location != "Any" and log.get("location") != location:
                    continue
                if task_filter != "Any" and log.get("task") != task_filter:
                    continue

                end = log.get("clock_out")
                duration = format_duration(log["clock_in"], now_trimmed(), ongoing=True) if end is None else format_duration(log["clock_in"], end)
                shift_data = (user["name"], user["id"], log["task"], log["location"], log["clock_in"], end, duration)
                (active if end is None else finished).append(shift_data)

        filtered_locations = set()
        filtered_companies = set()
        filtered_tasks = set()

        for loc, comps in self.task_config.items():
            if location != "Any" and loc != location:
                continue
            for comp, tasks in comps.items():
                if company != "Any" and comp != company:
                    continue
                filtered_locations.add(loc)
                filtered_companies.add(comp)
                filtered_tasks.update(tasks)

        self.location_dropdown['values'] = ["Any"] + sorted({loc for loc, comps in self.task_config.items()})
        if location != "Any":
            self.company_dropdown['values'] = ["Any"] + sorted({comp for comp in self.task_config.get(location, {})})
        else:
            self.company_dropdown['values'] = ["Any"] + sorted({comp for comps in self.task_config.values() for comp in comps})

        if location != "Any" and company != "Any":
            self.task_dropdown['values'] = ["Any"] + sorted(self.task_config.get(location, {}).get(company, []))
        else:
            self.task_dropdown['values'] = ["Any"] + sorted(filtered_tasks)

        self.display_shifts(active, finished)

    def display_shifts(self, active, finished):
        container = tk.Frame(self.shift_frame, bg="#e0e0e0", bd=2, relief="groove")
        container.pack(padx=15, pady=10, fill="both", expand=True)

        active_frame = tk.Frame(container, bg="#e0e0e0")
        finished_frame = tk.Frame(container, bg="#e0e0e0")
        active_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        finished_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        if active:
            tk.Label(active_frame, text="Currently Working", font=("Helvetica", 14, "bold"), bg="#e0e0e0", fg="#f49301").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)
            for idx, info in enumerate(active):
                row = (idx // 2) + 1
                col = idx % 2
                self.make_card(info, True, active_frame).grid(row=row, column=col, padx=10, pady=5, sticky="nsew")

        if finished:
            tk.Label(finished_frame, text="Finished Shifts", font=("Helvetica", 14, "bold"), bg="#e0e0e0", fg="#2e7730").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=10)
            for idx, info in enumerate(finished):
                row = (idx // 2) + 1
                col = idx % 2
                self.make_card(info, False, finished_frame).grid(row=row, column=col, padx=10, pady=5, sticky="nsew")

    def make_card(self, info, active=True, parent=None):
        name, uid, task, location, clock_in, clock_out, duration = info
        icon = "⏳" if active else "✅"
        title = f"{icon} {name} "

        frame = tk.LabelFrame(parent, text=title, font=("Helvetica", 12, "bold"), bg="white", padx=10, pady=5)

        tk.Label(frame, text=f"Task: {task}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Location: {location}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Clock-in: {clock_in[11:16]}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")

        if clock_out:
            tk.Label(frame, text=f"Clock-out: {clock_out[11:16]}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")

        tk.Label(frame, text=f"{duration}", font=("Helvetica", 11, "italic"), bg="white", fg="gray").pack(anchor="w")

        return frame

if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
