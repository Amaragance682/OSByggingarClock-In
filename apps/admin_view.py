import tkinter as tk
from lib.dateandtime import DateAndTime
import json
from tkinter import ttk, messagebox
import os
import sys
from datetime import datetime, timedelta


from lib.utils import (
    load_users,
    load_task_config,
    load_employee_logs,
    now_trimmed,
    format_duration,
    save_employee_logs,
    resource_path,
    save_users,
    save_task_config
)

COMPANY_FOLDER = resource_path("Database/Fyrirtaeki")
REQUESTS_FOLDER = resource_path("Database/Requests")

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
        elif name == "Edit Database":
            self.show_edit_database()
        elif name == "Control Board":
            self.show_control_board()
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
            for comp_name, tasks in comps.items():
                if company != "Any" and comp_name != company:
                    continue
                filtered_locations.add(loc)
                filtered_companies.add(comp_name)
                for t in tasks:
                    # handle dicts or legacy strings
                    name = t["name"] if isinstance(t, dict) else t
                    filtered_tasks.add(name)

        self.location_dropdown['values'] = ["Any"] + sorted(filtered_locations)
        self.company_dropdown['values']  = ["Any"] + sorted(filtered_companies)

        if location != "Any" and company != "Any":
            # pull only this location+company
            items = self.task_config[location][company]
            names = [t["name"] if isinstance(t, dict) else t for t in items]
            self.task_dropdown['values'] = ["Any"] + sorted(names)
        else:
            self.task_dropdown['values'] = ["Any"] + sorted(filtered_tasks)

        # finally re‐draw your shift cards
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

    def show_control_board(self):
        self.clear_main_area()

        header = tk.Label(self.main_area, text="Currently Working – Company Overview", font=("Helvetica", 16, "bold"), bg="#f4f4f4", fg="#2e2e2e")
        header.pack(pady=20)

        summary = self.get_currently_working_summary()

        if not summary:
            tk.Label(self.main_area, text="No one is currently working.", font=("Helvetica", 14), bg="#f4f4f4", fg="gray").pack()
            return

        for company, names in sorted(summary.items()):
            row = tk.Frame(self.main_area, bg="#f4f4f4")
            row.pack(anchor="w", padx=30, pady=5)

            # Company + count
            lbl = tk.Label(row,
                text=f"• {company}: {len(names)} people",
                font=("Helvetica", 12, "bold"),
                bg="#f4f4f4",
                fg="#007700"
            )
            lbl.pack(side="left")

            # Dropdown of names
            combo = ttk.Combobox(
                row,
                values=names,
                state="readonly",
                width=30
            )
            combo.set("Show names…")
            combo.pack(side="left", padx=(10,0))


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

    def get_currently_working_summary(self):
        summary = {}
        for user in self.users:
            logs = load_employee_logs(user)
            # if any open shift, include user
            if any(log.get("clock_out") is None for log in logs):
                comp = user.get("company", "Unknown")
                summary.setdefault(comp, []).append(user["name"])
        return summary

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

        btn_frame = tk.Frame(frame, bg="white")
        btn_frame.pack(anchor="w", pady=5)

        tk.Button(btn_frame, text="Edit", command=lambda: self.edit_shift(uid, clock_in)).pack(side="left", padx=5)

        if active:
            tk.Button(btn_frame, text="End Shift", command=lambda: self.end_shift(uid, clock_in)).pack(side="left", padx=5)

        tk.Button(btn_frame, text="Delete", command=lambda: self.delete_shift(uid, clock_in)).pack(side="left", padx=5)

        return frame
    
    def edit_shift(self, user_id, clock_in_time):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return messagebox.showerror("Error", "User not found.")

        logs = load_employee_logs(user)
        target = next((log for log in logs if log["clock_in"] == clock_in_time), None)
        if not target:
            return messagebox.showerror("Error", "Shift not found.")

        win = tk.Toplevel(self)
        win.title("Edit Shift")
        win.geometry("350x400")

        loc_var = tk.StringVar(value=target.get("location", ""))
        task_var = tk.StringVar(value=target.get("task", ""))
        in_var = tk.StringVar(value=target.get("clock_in", ""))
        out_var = tk.StringVar(value=target.get("clock_out", ""))

        tk.Label(win, text="Location").pack()
        loc_dropdown = ttk.Combobox(win, textvariable=loc_var, values=list(self.task_config.keys()))
        loc_dropdown.pack()

        tk.Label(win, text="Task").pack()
        task_dropdown = ttk.Combobox(win, textvariable=task_var)
        task_dropdown.pack()

        def update_tasks(*args):
            loc = loc_var.get()
            company = user["company"]
            tasks = self.task_config.get(loc, {}).get(company, [])
            task_dropdown["values"] = tasks
            if task_var.get() not in tasks:
                task_var.set("")
        loc_var.trace_add("write", update_tasks)
        update_tasks()

        for label, var in [("Clock In (ISO)", in_var), ("Clock Out (ISO)", out_var)]:
            tk.Label(win, text=label).pack()
            tk.Entry(win, textvariable=var).pack()

        def save_changes():
            target["location"] = loc_var.get()
            target["task"] = task_var.get()
            target["clock_in"] = in_var.get()
            target["clock_out"] = out_var.get()
            save_employee_logs(user, logs)
            messagebox.showinfo("Saved", "Shift updated.")
            win.destroy()
            self.refresh_shifts()

        tk.Button(win, text="Save", command=save_changes).pack(pady=10)

    def end_shift(self, user_id, clock_in_time):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return

        logs = load_employee_logs(user)
        for log in logs:
            if log["clock_in"] == clock_in_time and not log.get("clock_out"):
                log["clock_out"] = now_trimmed()
                break
        else:
            return messagebox.showinfo("Notice", "Shift already ended.")

        save_employee_logs(user, logs)
        self.refresh_shifts()

    def delete_shift(self, user_id, clock_in_time):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return

        if not messagebox.askyesno("Confirm", "Are you sure you want to delete this shift?"):
            return

        logs = load_employee_logs(user)
        logs = [log for log in logs if log["clock_in"] != clock_in_time]
        save_employee_logs(user, logs)
        self.refresh_shifts()
    def remove_request(self, req, filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                all_requests = json.load(f)
            all_requests = [
                r for r in all_requests
                if r.get("requested_start") != req.get("requested_start") or r.get("requested_end") != req.get("requested_end")
            ]
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(all_requests, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Deleted", "Request successfully removed.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove request:\n{e}")
            
    def create_request_card(self, parent, employee, req, company, filepath):
        frame = tk.LabelFrame(parent, text=f"📝 Request from {employee}", bg="white", font=("Helvetica", 12, "bold"), padx=10, pady=5)
        orig_start = req.get("requested_start")
        orig_end = req.get("requested_end")
        
        def handle_finalize_click():
            status = req.get("status", "").lower()
            if status == "approved":
                self.finalize_request(req, employee, company, filepath)
            elif status == "rejected":
                confirm = messagebox.askyesno("Confirm Removal", f"Are you sure you want to delete the request from {employee}?")
                if confirm:
                    self.remove_request(req, filepath)
                    self.show_handle_requests()
            else:
                messagebox.showwarning("Pending", "Please approve or reject the request before proceeding.")


        btn_label = "Finalize" if req.get("status", "").lower() == "approved" else "Remove" if req.get("status", "").lower() == "rejected" else "Finalize"
        finalize_btn = tk.Button(frame, text=btn_label, command=handle_finalize_click)

        finalize_btn.pack(pady=5)

        # Status management
        def update_status(event):
            new_status = status_var.get().lower()
            req["status"] = new_status
            update_request_file(orig_start, orig_end)
            update_status_color()
            finalize_btn.config(text="Finalize" if new_status == "approved" else "Remove" if new_status == "rejected" else "Finalize")

        def update_request_file(orig_start, orig_end):
            with open(filepath, 'r', encoding='utf-8') as f:
                all_requests = json.load(f)

            for r in all_requests:
                if r.get("requested_start") == orig_start and r.get("requested_end") == orig_end:
                    r.update(req)
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
            original_start = req.get("requested_start")
            original_end = req.get("requested_end")
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
                req["location"] = location_var.get()
                req["task"] = task_var.get()
                req["requested_start"] = start_entry.get()
                req["requested_end"] = end_entry.get()
                req["reason"] = reason_entry.get()

                update_request_file(original_start, original_end)
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

        log_path = os.path.join(COMPANY_FOLDER, company, f"{employee}.json")
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

        conflicts = []  # <-- Initialize here

        try:
            logs = []
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as f:
                    logs = json.load(f)

            filtered_logs = []

            for log in logs:
                old_start = parse_dt(log.get("clock_in"))
                old_end = parse_dt(log.get("clock_out"))
                if not old_start or not old_end:
                    filtered_logs.append(log)
                    continue

                # Check for overlap
                if old_start < new_end and old_end > new_start:
                    conflicts.append(log)
                else:
                    filtered_logs.append(log)

            if conflicts:
                print(f"[INFO] Found {len(conflicts)} conflicting shift(s). Replacing with request.")
                for c in conflicts:
                    print(f"[REMOVED] {c['clock_in']} to {c['clock_out']}")

            # Add new entry
            filtered_logs.append(new_entry)

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(filtered_logs, f, indent=4, ensure_ascii=False)

        except Exception as e:
            messagebox.showerror("File Error", f"Could not process {log_path}:\n{e}")
            return

        # Remove the request
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

    def show_edit_database(self):
        self.clear_main_area()
        self.build_hierarchical_db_tab(self.main_area)

    def build_users_tab(self, parent):
        # load fresh copy
        self.users = load_users()

        # left: list of users
        listbox = tk.Listbox(parent, width=30)
        for u in self.users:
            listbox.insert("end", f"{u['id']}: {u['name']}")
        listbox.grid(row=0, column=0, rowspan=4, sticky="ns", padx=5, pady=5)

        # right: form fields
        tk.Label(parent, text="ID").grid(row=0, column=1, sticky="w")
        id_var = tk.StringVar()
        tk.Entry(parent, textvariable=id_var).grid(row=0, column=2, sticky="ew")

        tk.Label(parent, text="Name").grid(row=1, column=1, sticky="w")
        name_var = tk.StringVar()
        tk.Entry(parent, textvariable=name_var).grid(row=1, column=2, sticky="ew")

        tk.Label(parent, text="Company").grid(row=2, column=1, sticky="w")
        comp_var = tk.StringVar()
        comp_choices = sorted({u["company"] for u in self.users} | set(self.get_company_names()))
        ttk.Combobox(parent, textvariable=comp_var, values=comp_choices, state="readonly")\
            .grid(row=2, column=2, sticky="ew")

        tk.Label(parent, text="PIN").grid(row=3, column=1, sticky="w")
        pin_var = tk.StringVar()
        tk.Entry(parent, textvariable=pin_var).grid(row=3, column=2, sticky="ew")

        # bottom: Add / Update / Delete
        btn_frame = tk.Frame(parent)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=10)

        def on_select(evt):
            idx = listbox.curselection()[0]
            user = self.users[idx]
            id_var.set(user["id"])
            name_var.set(user["name"])
            comp_var.set(user["company"])
            pin_var.set(user["pin"])
        listbox.bind("<<ListboxSelect>>", on_select)

        def save_user():
            new = {"id": id_var.get(), "name": name_var.get(),
                   "company": comp_var.get(), "pin": pin_var.get()}
            # replace if exists, else append
            for i,u in enumerate(self.users):
                if u["id"] == new["id"]:
                    self.users[i] = new
                    break
            else:
                self.users.append(new)
            save_users(self.users)  # you’ll have to add this in lib.utils
            messagebox.showinfo("Saved", f"User {new['id']} saved.")
            self.show_edit_database()  # refresh entire DB UI

        def delete_user():
            uid = id_var.get()
            self.users = [u for u in self.users if u["id"] != uid]
            save_users(self.users)
            messagebox.showinfo("Deleted", f"User {uid} removed.")
            self.show_edit_database()

        tk.Button(btn_frame, text="Save User",   command=save_user  ).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Delete User", command=delete_user).pack(side="left", padx=5)

    def refresh_locations(self):
        self.task_config = load_task_config()
        self.loc_lb.delete(0, "end")
        for loc in self.task_config:
            self.loc_lb.insert("end", loc)
        # clear downstream lists:
        self.comp_lb.delete(0, "end")
        self.task_lb.delete(0, "end")

    def on_loc_selected(self, evt):
        sel = self.loc_lb.get(self.loc_lb.curselection())
        # populate companies for that loc…
        # clear tasks panel

    def on_user_company_selected(self, event=None):
        """When the user picks a company, reload the user listbox."""
        comp = self.user_company_var.get()
        self.user_lb.delete(0, "end")
        for u in self.users:
            if u["company"] == comp:
                self.user_lb.insert("end", f"{u['id']}: {u['name']}")
        # clear any selection so downstream edits don’t break
        self.current_user = None

    def build_hierarchical_db_tab(self, parent):
        # ─ Layout ─────────────────────────────────────────────────────────────
        left  = tk.Frame(parent); left.grid(row=0, column=0, sticky="ns")
        mid   = tk.Frame(parent); mid .grid(row=0, column=1, sticky="ns")
        right = tk.Frame(parent); right.grid(row=0, column=2, sticky="ns")
        usersc= tk.Frame(parent); usersc.grid(row=0, column=3, sticky="ns", padx=10)

        # ─ Locations ──────────────────────────────────────────────────────────
        tk.Label(left, text="Locations", font=("Helvetica", 12, "bold")).pack(pady=(5,2))
        self.loc_lb = tk.Listbox(left, exportselection=False); self.loc_lb.pack(fill="both", expand=True)
        tk.Button(left,  text="Add Loc",    command=self.add_location).pack(fill="x")
        tk.Button(left,  text="Edit Loc",   command=self.edit_location).pack(fill="x")
        tk.Button(left,  text="Delete Loc", command=self.delete_location).pack(fill="x")
        self.loc_lb.bind("<<ListboxSelect>>", self.on_loc_selected)

        # ─ Companies ─────────────────────────────────────────────────────────
        tk.Label(mid, text="Companies", font=("Helvetica", 12, "bold")).pack(pady=(5,2))
        self.comp_lb = tk.Listbox(mid, exportselection=False); self.comp_lb.pack(fill="both", expand=True)
        tk.Button(mid,  text="Add Comp",    command=self.add_company).pack(fill="x")
        tk.Button(mid,  text="Edit Comp",   command=self.edit_company).pack(fill="x")
        tk.Button(mid,  text="Delete Comp", command=self.delete_company).pack(fill="x")
        self.comp_lb.bind("<<ListboxSelect>>", self.on_comp_selected)

        # ─ Tasks ─────────────────────────────────────────────────────────────
        tk.Label(right, text="Tasks", font=("Helvetica", 12, "bold")).pack(pady=(5,2))
        self.task_lb = tk.Listbox(right, exportselection=False); self.task_lb.pack(fill="both", expand=True)
        tk.Button(right, text="Add Task",    command=self.add_task).pack(fill="x")
        tk.Button(right, text="Edit Task",   command=self.edit_task).pack(fill="x")
        tk.Button(right, text="Delete Task", command=self.delete_task).pack(fill="x")

        # ─ Users Panel ───────────────────────────────────────────────────────
        tk.Label(usersc, text="Users", font=("Helvetica", 14, "bold")).pack(pady=(5,10))

        tk.Label(usersc, text="Filter by Company:").pack(anchor="w", padx=5)
        all_comps = sorted({c for loc in self.task_config for c in self.task_config[loc]})
        self.user_company_var = tk.StringVar()
        self.user_company_combo = ttk.Combobox(
            usersc, textvariable=self.user_company_var,
            values=all_comps, state="readonly"
        )
        self.user_company_combo.pack(fill="x", padx=5)
        self.user_company_combo.bind("<<ComboboxSelected>>", self.on_user_company_selected)

        tk.Label(usersc, text="Employee List:").pack(anchor="w", padx=5, pady=(10,0))
        self.user_lb = tk.Listbox(usersc, exportselection=False, height=12)
        self.user_lb.pack(fill="both", expand=True, padx=5, pady=(2,10))

        # ─ Create / Edit / Delete Buttons ───────────────────────────────────
        btnf = tk.Frame(usersc)
        btnf.pack(fill="x", padx=5, pady=(0,10))
        tk.Button(btnf, text="Add User",  command=self.add_user).pack(side="left",  expand=True)
        tk.Button(btnf, text="Edit User", command=self.edit_user).pack(side="left",  expand=True)
        tk.Button(btnf, text="Delete User", command=self.delete_user).pack(side="left", expand=True)

        # finally, populate the first list
        self.refresh_locations()


    # ────────────────────────────────────────────────────────────────────
    # Location‐level CRUD
    # ────────────────────────────────────────────────────────────────────

    def refresh_locations(self):
        """Reload the listbox of locations from disk."""
        self.task_config = load_task_config()
        self.loc_lb.delete(0, "end")
        for loc in sorted(self.task_config):
            self.loc_lb.insert("end", loc)
        # clear downstream panels
        self.comp_lb.delete(0, "end")
        self.task_lb.delete(0, "end")

    def add_location(self):
        """Popup to create a new location."""
        def on_ok():
            new_loc = entry.get().strip()
            if not new_loc:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            if new_loc in self.task_config:
                messagebox.showerror("Error", "That location already exists.")
                return
            self.task_config[new_loc] = {}
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_locations()

        dlg = tk.Toplevel(self)
        dlg.title("Add Location")
        tk.Label(dlg, text="Location Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg)
        entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def edit_location(self):
        """Rename the selected location."""
        sel = self.loc_lb.curselection()
        if not sel:
            messagebox.showerror("Error", "Select a location first.")
            return
        old = self.loc_lb.get(sel)
        def on_ok():
            new = entry.get().strip()
            if not new or new == old:
                dlg.destroy(); return
            if new in self.task_config:
                messagebox.showerror("Error", "That name already exists.")
                return
            # rename key in dict
            self.task_config[new] = self.task_config.pop(old)
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_locations()

        dlg = tk.Toplevel(self)
        dlg.title(f"Rename '{old}'")
        tk.Label(dlg, text="New Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.insert(0, old); entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def delete_location(self):
        """Delete the selected location (and all its companies/tasks)."""
        sel = self.loc_lb.curselection()
        if not sel:
            messagebox.showerror("Error", "Select a location first.")
            return
        loc = self.loc_lb.get(sel)
        if not messagebox.askyesno("Confirm", f"Remove '{loc}' and all child data?"):
            return
        self.task_config.pop(loc, None)
        save_task_config(self.task_config)
        self.refresh_locations()

    def on_loc_selected(self, evt=None):
        sel = self.loc_lb.curselection()
        if not sel:
            self.current_loc = None
        else:
            self.current_loc = self.loc_lb.get(sel)
        # repopulate companies
        self.refresh_companies()

    # ────────────────────────────────────────────────────────────────────
    # Company‐level CRUD (must come after the location methods)
    # ────────────────────────────────────────────────────────────────────

    def refresh_companies(self):
        """Reload the company listbox for the currently selected location."""
        # reload config in case anything changed
        self.task_config = load_task_config()

        # clear old entries
        self.comp_lb.delete(0, "end")
        self.task_lb.delete(0, "end")  # clear tasks too

        sel = self.loc_lb.curselection()
        if not sel:
            return
        loc = self.loc_lb.get(sel)
        for comp in sorted(self.task_config.get(loc, {})):
            self.comp_lb.insert("end", comp)

    def add_company(self):
        """Popup to create a new company under the selected location."""
        sel = self.loc_lb.curselection()
        if not sel:
            messagebox.showerror("Error", "Select a location first.")
            return
        loc = self.loc_lb.get(sel)

        def on_ok():
            new = entry.get().strip()
            if not new:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            if new in self.task_config[loc]:
                messagebox.showerror("Error", "That company already exists here.")
                return
            # create company → empty task list
            self.task_config[loc][new] = []
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_companies()

        dlg = tk.Toplevel(self)
        dlg.title(f"Add Company in '{loc}'")
        tk.Label(dlg, text="Company Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def edit_company(self):
        """Rename the selected company within the current location."""
        loc_sel = self.loc_lb.curselection()
        comp_sel = self.comp_lb.curselection()
        if not loc_sel or not comp_sel:
            messagebox.showerror("Error", "Select a company first.")
            return
        loc  = self.loc_lb.get(loc_sel)
        old  = self.comp_lb.get(comp_sel)

        def on_ok():
            new = entry.get().strip()
            if not new or new == old:
                dlg.destroy()
                return
            if new in self.task_config[loc]:
                messagebox.showerror("Error", "That name already exists here.")
                return
            # rename: move the list of tasks
            self.task_config[loc][new] = self.task_config[loc].pop(old)
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_companies()

        dlg = tk.Toplevel(self)
        dlg.title(f"Rename Company '{old}'")
        tk.Label(dlg, text="New Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.insert(0, old); entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def delete_company(self):
        """Remove the selected company (and its tasks) from the current location."""
        loc_sel  = self.loc_lb.curselection()
        comp_sel = self.comp_lb.curselection()
        if not loc_sel or not comp_sel:
            messagebox.showerror("Error", "Select a company first.")
            return
        loc  = self.loc_lb.get(loc_sel)
        comp = self.comp_lb.get(comp_sel)

        if not messagebox.askyesno("Confirm", f"Delete company '{comp}' and all its tasks?"):
            return

        self.task_config[loc].pop(comp, None)
        save_task_config(self.task_config)
        self.refresh_companies()

    def on_comp_selected(self, evt=None):
        sel = self.comp_lb.curselection()
        if not sel:
            self.current_comp = None
        else:
            self.current_comp = self.comp_lb.get(sel)
        # now we know both loc & comp
        # and we can refresh tasks without touching the loc Listbox again
        self.refresh_tasks()

    # ────────────────────────────────────────────────────────────────────
    # Task‐level CRUD (replace your existing methods with these)
    # ────────────────────────────────────────────────────────────────────

    def refresh_tasks(self):
        """Reload the task list for the currently selected location+company."""
        self.task_lb.delete(0, "end")
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        if not loc or not comp:
            return

        for item in self.task_config[loc][comp]:
            # each task is a dict { "name":…, "completed":… }
            name      = item["name"]
            completed = item.get("completed", False)
            # append a checkmark if it's completed
            display = f"{name}{' ✓' if completed else ''}"
            self.task_lb.insert("end", display)

    def add_task(self):
        """Popup to create a new task under the selected company."""
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        if not loc or not comp:
            messagebox.showerror("Error", "Select a company first.")
            return

        def on_ok():
            new = entry.get().strip()
            if not new:
                messagebox.showerror("Error", "Task cannot be empty.")
                return
            # check existing names
            existing = { itm["name"] for itm in self.task_config[loc][comp] }
            if new in existing:
                messagebox.showerror("Error", "That task already exists.")
                return
            # append new task object
            self.task_config[loc][comp].append({
                "name":      new,
                "completed": False
            })
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_tasks()

        dlg = tk.Toplevel(self)
        dlg.title(f"Add Task in '{comp}' @ '{loc}'")
        tk.Label(dlg, text="Task Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg)
        entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def edit_task(self):
        """Rename and toggle completion on the selected task."""
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        sel  = self.task_lb.curselection()
        if not (loc and comp and sel):
            messagebox.showerror("Error", "Select a task to edit.")
            return

        # strip the checkmark if present
        old_display = self.task_lb.get(sel)
        old_name    = old_display.rstrip(" ✓")

        # find the dict index
        lst = self.task_config[loc][comp]
        for idx, itm in enumerate(lst):
            if itm["name"] == old_name:
                orig = itm
                break
        else:
            messagebox.showerror("Error", "Task not found in config.")
            return

        orig_completed = orig.get("completed", False)

        def on_ok():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            # avoid name collisions
            existing = { itm["name"] for i, itm in enumerate(lst) if i != idx }
            if new_name in existing:
                messagebox.showerror("Error", "That task already exists.")
                return
            # update
            lst[idx] = {
                "name":      new_name,
                "completed": completed_var.get()
            }
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_tasks()

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Task '{old_name}'")

        tk.Label(dlg, text="Task Name:").pack(padx=10, pady=(10, 0))
        name_var = tk.StringVar(value=old_name)
        tk.Entry(dlg, textvariable=name_var).pack(padx=10, pady=5)

        completed_var = tk.BooleanVar(value=orig_completed)
        tk.Checkbutton(dlg, text="Completed", variable=completed_var).pack(pady=(5, 10))

        tk.Button(dlg, text="Save", command=on_ok).pack(pady=10)

    def delete_task(self):
        """Remove the selected task from the current company."""
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        sel  = self.task_lb.curselection()
        if not (loc and comp and sel):
            messagebox.showerror("Error", "Select a task to delete.")
            return

        # strip checkmark
        display   = self.task_lb.get(sel)
        task_name = display.rstrip(" ✓")

        if not messagebox.askyesno("Confirm", f"Delete task '{task_name}'?"):
            return

        lst = self.task_config[loc][comp]
        # remove matching entry
        self.task_config[loc][comp] = [
            itm for itm in lst
            if itm["name"] != task_name
        ]

        save_task_config(self.task_config)
        self.refresh_tasks()

    def on_user_company_selected(self, event=None):
        """Reload the users list when a company is chosen."""
        comp = self.user_company_var.get()
        self.user_lb.delete(0, "end")
        for u in self.users:
            if u["company"] == comp:
                self.user_lb.insert("end", f"{u['id']}: {u['name']}")
        # clear any selected user so edit/delete won't be stale
        self.current_user = None

    def add_user(self):
        """Popup to add a new user under the selected company."""
        comp = self.user_company_var.get()
        if not comp:
            messagebox.showerror("Error", "Please choose a company first.")
            return

        def on_ok():
            uid  = id_var.get().strip()
            name = name_var.get().strip()
            pin  = pin_var.get().strip()
            if not (uid and name and pin):
                messagebox.showerror("Error", "All fields required.")
                return
            if any(u["id"] == uid for u in self.users):
                messagebox.showerror("Error", "That ID already exists.")
                return
            new = {"id":uid, "name":name, "company":comp, "pin":pin}
            self.users.append(new)
            save_users(self.users)
            dlg.destroy()
            self.on_user_company_selected()

        dlg = tk.Toplevel(self)
        dlg.title(f"Add user to {comp}")
        tk.Label(dlg, text="ID:").grid(row=0, column=0);   id_var   = tk.StringVar(); tk.Entry(dlg, textvariable=id_var).grid(row=0,column=1)
        tk.Label(dlg, text="Name:").grid(row=1, column=0); name_var = tk.StringVar(); tk.Entry(dlg, textvariable=name_var).grid(row=1,column=1)
        tk.Label(dlg, text="PIN:").grid(row=2, column=0);  pin_var  = tk.StringVar(); tk.Entry(dlg, textvariable=pin_var).grid(row=2,column=1)
        tk.Button(dlg, text="OK", command=on_ok).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_user(self):
        """Popup to edit the selected user’s name and PIN."""
        sel = self.user_lb.curselection()
        if not sel:
            return messagebox.showerror("Error", "Select a user first.")
        text = self.user_lb.get(sel)
        uid  = text.split(":",1)[0]
        user = next(u for u in self.users if u["id"] == uid)

        def on_ok():
            new_name = name_var.get().strip()
            new_pin  = pin_var.get().strip()
            if not (new_name and new_pin):
                return messagebox.showerror("Error", "All fields required.")
            user["name"] = new_name
            user["pin"]  = new_pin
            save_users(self.users)
            dlg.destroy()
            self.on_user_company_selected()

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit user {uid}")
        tk.Label(dlg, text="Name:").grid(row=0,column=0); name_var = tk.StringVar(value=user["name"]); tk.Entry(dlg, textvariable=name_var).grid(row=0,column=1)
        tk.Label(dlg, text="PIN:").grid(row=1,column=0);  pin_var  = tk.StringVar(value=user["pin"]);  tk.Entry(dlg, textvariable=pin_var).grid(row=1,column=1)
        tk.Button(dlg, text="OK", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

    def delete_user(self):
        """Delete the selected user after confirmation."""
        sel = self.user_lb.curselection()
        if not sel:
            return messagebox.showerror("Error", "Select a user first.")
        text = self.user_lb.get(sel)
        uid  = text.split(":",1)[0]
        if not messagebox.askyesno("Confirm", f"Delete user {uid}?"):
            return
        self.users = [u for u in self.users if u["id"] != uid]
        save_users(self.users)
        self.on_user_company_selected()


if __name__ == "__main__":
    print("hello from admin_view.py")
    app = AdminApp()
    app.mainloop()