import tkinter as tk
from lib.dateandtime import DateAndTime
import json
from tkinter import ttk, messagebox
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
REQUESTS_FOLDER = "requests"

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

    def save_status_change(self, filepath, employee, req_obj, new_status):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                requests = json.load(f)

            # Update the matching request
            for r in requests:
                if r == req_obj:
                    r["status"] = new_status
                    break

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(requests, f, indent=2)

            tk.messagebox.showinfo("Saved", f"Status for {employee}'s request updated to '{new_status}'.")
            self.show_request_page()

        except Exception as e:
            tk.messagebox.showerror("Error", f"Could not save status:\n{e}")

    def format_time_readable(self, iso_str):
        try:
            return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "Invalid or Missing Time"
    
    def switch_page(self, name):
        if name == "Shift Viewer":
            self.show_shift_viewer()
        elif name == "Handle Requests":
            self.show_handle_requests()
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

    def show_handle_requests(self):
        self.clear_main_area()

        request_canvas = tk.Canvas(self.main_area, bg="#f4f4f4", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.main_area, orient="vertical", command=request_canvas.yview)
        request_canvas.configure(yscrollcommand=scrollbar.set)

        request_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        request_frame = tk.Frame(request_canvas, bg="#f4f4f4")
        request_canvas.create_window((0, 0), window=request_frame, anchor="nw")

        # Set scrollregion whenever the frame size changes
        request_frame.bind("<Configure>", lambda e: request_canvas.configure(scrollregion=request_canvas.bbox("all")))

        for i in range(5):
            request_frame.grid_columnconfigure(i, weight=1, uniform="requests")

        current_index = 0  # total cards placed

        for company in os.listdir(REQUESTS_FOLDER):
            company_path = os.path.join(REQUESTS_FOLDER, company)
            if not os.path.isdir(company_path):
                continue

            for filename in os.listdir(company_path):
                if filename.endswith("_requests.json"):
                    employee_name = filename.replace("_requests.json", "")
                    filepath = os.path.join(company_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            requests = json.load(f)
                        except json.JSONDecodeError:
                            continue

                        for req in requests:
                            col = current_index % 5
                            row = current_index // 5
                            card = self.create_request_card(request_frame, employee_name, req, company, filepath)
                            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                            current_index += 1
 
        # After all widgets are added, update scrollregion:
        request_frame.update_idletasks()
        request_canvas.config(scrollregion=request_canvas.bbox("all"))


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

    def create_request_card(self, parent, employee, req, company, filepath):
        frame = tk.LabelFrame(parent, text=f"📝 Request from {employee}", bg="white", font=("Helvetica", 12, "bold"), padx=10, pady=5)
        finalize_btn = tk.Button(frame, text="Finalize", command=lambda: self.finalize_request(req, employee, company, filepath))
        finalize_btn.pack(pady=5)

        # Status management
        def update_status(event):
            new_status = status_var.get().lower()
            req["status"] = new_status
            update_request_file()
            update_status_color()

        def update_request_file():
            with open(filepath, 'r', encoding='utf-8') as f:
                all_requests = json.load(f)

            for r in all_requests:
                if r.get("requested_start") == req.get("requested_start") and r.get("requested_end") == req.get("requested_end"):
                    r.update(req)  # Update with modified fields
                    break

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(all_requests, f, indent=4)

        def update_status_color():
            status_color = {
                "pending": "#ffa500",
                "approved": "#28a745",
                "rejected": "#dc3545"
            }.get(req.get("status", "pending").lower(), "gray")
            status_label.config(fg=status_color)

        def edit_request():
            edit_win = tk.Toplevel(self)
            edit_win.title("Edit Request")
            edit_win.geometry("400x350")

            tk.Label(edit_win, text="Location:").pack()
            location_var = tk.StringVar(value=req.get("location", ""))
            location_dropdown = ttk.Combobox(edit_win, textvariable=location_var, state="readonly")
            location_dropdown['values'] = sorted(list(self.task_config.keys()))
            location_dropdown.pack()

            tk.Label(edit_win, text="Task:").pack()
            task_var = tk.StringVar(value=req.get("task", ""))
            task_dropdown = ttk.Combobox(edit_win, textvariable=task_var, state="readonly")
            task_dropdown.pack()

            def update_tasks(*args):
                loc = location_var.get()
                task_list = self.task_config.get(loc, {}).get(company, [])
                task_dropdown['values'] = sorted(task_list)
                if task_var.get() not in task_list:
                    task_var.set("")  # Clear invalid selection

            # Bind location changes to update tasks
            location_var.trace_add("write", update_tasks)
            update_tasks()  # Initial load based on current location

            # Remaining fields
            def make_field(label, key, entry):
                tk.Label(edit_win, text=label).pack()
                entry.insert(0, req.get(key, ""))
                entry.pack()
                return entry

            start_entry = make_field("Start Time", "requested_start", DateAndTime(edit_win))
            end_entry = make_field("End Time", "requested_end", DateAndTime(edit_win))
            reason_entry = make_field("Reason", "reason", tk.Entry(edit_win))

            def save_changes():
                print(end_entry.get())
                req["location"] = location_var.get()
                req["task"] = task_var.get()
                req["requested_start"] = start_entry.get()
                req["requested_end"] = end_entry.get()
                req["reason"] = reason_entry.get()

                update_request_file()
                messagebox.showinfo("Updated", "Request updated successfully.")
                edit_win.destroy()
                self.show_handle_requests()

            tk.Button(edit_win, text="Save", command=save_changes).pack(pady=10)

        # Status widgets
        status_label = tk.Label(frame, text=f"Status:", font=("Helvetica", 11, "bold"), bg="white", anchor="w")
        status_label.pack(anchor="w")
        status_var = tk.StringVar(value=req.get("status", "pending").capitalize())
        status_dropdown = ttk.Combobox(frame, textvariable=status_var, state="readonly", values=["Pending", "Approved", "Rejected"])
        status_dropdown.pack(anchor="w")
        status_dropdown.bind("<<ComboboxSelected>>", update_status)
        update_status_color()

        # Other fields
        tk.Label(frame, text=f"Reason: {req.get('reason', 'N/A')}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Company: {req.get('company', 'N/A')}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Location: {req.get('location', 'N/A')}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Task: {req.get('task', 'N/A')}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"Start: {self.format_time_readable(req.get('requested_start'))}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")
        tk.Label(frame, text=f"End: {self.format_time_readable(req.get('requested_end'))}", font=("Helvetica", 11), bg="white", anchor="w").pack(anchor="w")

        # Buttons
        btn_frame = tk.Frame(frame, bg="white")
        btn_frame.pack(pady=5, anchor="w")

        tk.Button(btn_frame, text="Edit", command=edit_request).pack(side="left", padx=5)

        return frame
            
    def finalize_request(self, req, employee, company, filepath):

        def parse_dt(s):
            try:
                return datetime.fromisoformat(s)
            except:
                return None
    

        if req["status"].lower() != "approved":
            messagebox.showwarning("Not Approved", "Only approved requests can be finalized.")
            return

        log_path = os.path.join("Fyrirtaeki", company, f"{employee}.json")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

        new_start = parse_dt(req["requested_start"])
        new_end = parse_dt(req["requested_end"])
        if not new_start or not new_end:
            messagebox.showerror("Error", "Invalid date format in request.")
            return

        new_entry = {
            "task": req["task"],
            "location": req["location"],
            "clock_in": req["requested_start"],
            "clock_out": req["requested_end"]
        }

        try:
            logs = []
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)

            filtered_logs = []
            conflicts = []

            for log in logs:
                old_start = parse_dt(log.get("clock_in"))
                old_end = parse_dt(log.get("clock_out"))
                if not old_start or not old_end:
                    filtered_logs.append(log)
                    continue

                # ❗ Check for overlap
                if old_start < new_end and old_end > new_start:
                    conflicts.append(log)
                else:
                    filtered_logs.append(log)

            if conflicts:
                print(f"[INFO] Found {len(conflicts)} conflicting shift(s). Replacing with request.")
                # Optionally log the removed ones
                for c in conflicts:
                    print(f"[REMOVED] {c['clock_in']} to {c['clock_out']}")

            # ✅ Add new entry
            filtered_logs.append(new_entry)

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(filtered_logs, f, indent=4, ensure_ascii=False)

        except Exception as e:
            messagebox.showerror("File Error", f"Could not process {log_path}:\n{e}")
            return

        # 🧹 Remove request
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                all_requests = json.load(f)
            all_requests = [r for r in all_requests if not (
                r.get("requested_start") == req.get("requested_start") and
                r.get("requested_end") == req.get("requested_end")
            )]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(all_requests, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("File Error", f"Could not update request file:\n{e}")

        messagebox.showinfo("Success", f"Finalized request and replaced {len(conflicts)} conflicting shift(s).")
        self.show_handle_requests()

if __name__ == "__main__":
    app = AdminApp()
    app.mainloop()
