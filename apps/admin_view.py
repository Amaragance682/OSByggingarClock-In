import uuid
import tkinter as tk
from lib.dateandtime import DateAndTime
from collections import defaultdict
import json
from tkinter import ttk, messagebox, simpledialog
import os
import sys
from datetime import datetime, timedelta
import shutil
from pathlib import Path



from lib.utils import (
    get_user_by_id,
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
REQUESTS_FOLDER = resource_path("Database/requests")
APP_BG = "#f4f4f4"

def _parse_iso(s: str):
    """Return datetime from ISO-ish string, or None if missing/invalid."""
    try:
        if isinstance(s, str) and s.strip():
            return datetime.fromisoformat(s)
    except Exception:
        pass
    return None

def _parse_hhmm(s: str):
    """Return (hour, minute) from 'HH:MM' or raise ValueError."""
    if not isinstance(s, str) or ":" not in s:
        raise ValueError("Bad time")
    hh, mm = s.strip().split(":", 1)
    h, m = int(hh), int(mm)
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("Hour 0–23 and minute 0–59 required")
    return h, m


class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()

 
        screen_width = self.winfo_screenwidth() - 60
        screen_height = self.winfo_screenheight() - 100
        self.geometry(f"{screen_width}x{screen_height}+0+0")
                
        self.title("Admin View – Employee Shift Monitor")
        self.configure(bg=APP_BG)
        self._build_styles()

        self.users = load_users()
        self.task_config = load_task_config()

        self.time_range_var = tk.StringVar(value="Today")
        self.location_var = tk.StringVar(value="Any")
        self.company_var = tk.StringVar(value="Any")
        self.task_var = tk.StringVar(value="Any")
        self.user_var = tk.StringVar(value="Any")


        self.create_navigation()
        self.create_shift_viewer()

    def _all_companies(self):
        # union of companies across all locations (from task_config + users)
        from_cfg = {c for locmap in self.task_config.values() for c in locmap.keys()}
        from_users = {u.get("company") for u in self.users}
        return sorted({c for c in (from_cfg | from_users) if c})

    def _sync_company_globally(self, company: str):
        """Ensure `company` exists (as empty task list) at every location."""
        for loc in self.task_config.keys():
            self.task_config.setdefault(loc, {}).setdefault(company, [])

    def _sync_all_companies_to_location(self, location: str) -> None:
        """Ensure every known company exists at `location`."""
        # create the location mapping if missing
        locmap = self.task_config.setdefault(location, {})
        # union of companies from config and users.json
        companies = {u.get("company") for u in self.users}
        companies |= {c for locmap2 in self.task_config.values() for c in locmap2.keys()}
        companies.discard(None)
        for comp in companies:
            locmap.setdefault(comp, [])

    def _sync_company_to_all_locations(self, company: str) -> None:
        """Ensure `company` exists at every location."""
        if not company:
            return
        for loc in list(self.task_config.keys()):
            self.task_config.setdefault(loc, {}).setdefault(company, [])

    def _company_data_dirs(self, company: str):
        """
        Return a list of directories on disk that store this company's logs.
        Supports both:
        Database/Fyrirtaeki/<company>/
        Database/Fyrirtaeki/<location>/<company>/
        """
        root = Path(COMPANY_FOLDER)
        paths = []

        # Flat layout
        d = root / company
        if d.is_dir():
            paths.append(d)

        # Location/company layout
        for loc in root.iterdir():
            if loc.is_dir():
                dd = loc / company
                if dd.is_dir():
                    paths.append(dd)

        return paths

    def _merge_company_dirs(self, src: Path, dst: Path):
        """Move files from src to dst; keep existing dst files; then remove src."""
        dst.mkdir(parents=True, exist_ok=True)
        for p in src.iterdir():
            target = dst / p.name
            if target.exists():
                # keep existing; optionally you could de-dup/merge JSON here
                continue
            shutil.move(str(p), str(target))
        shutil.rmtree(src, ignore_errors=True)

    def _rename_company_on_disk(self, old: str, new: str):
        """Rename company folders (both layouts) and requests folder, merging if needed."""
        root = Path(COMPANY_FOLDER)

        # Flat
        src = root / old
        if src.is_dir():
            dst = root / new
            if dst.exists():
                self._merge_company_dirs(src, dst)
            else:
                src.rename(dst)

        # Per-location
        for loc in root.iterdir():
            if not loc.is_dir():
                continue
            src = loc / old
            if src.is_dir():
                dst = loc / new
                if dst.exists():
                    self._merge_company_dirs(src, dst)
                else:
                    src.rename(dst)

        # requests/<company>
        rold = Path(REQUESTS_FOLDER) / old
        if rold.is_dir():
            rnew = Path(REQUESTS_FOLDER) / new
            if rnew.exists():
                self._merge_company_dirs(rold, rnew)
            else:
                rold.rename(rnew)

    def _delete_company_on_disk(self, company: str, *, archive: bool = False):
        """
        Delete or archive all folders for this company (both layouts),
        and remove requests/<company>.
        """
        dirs = self._company_data_dirs(company)
        if archive:
            ar = Path(resource_path("Database/_archive/Fyrirtaeki"))
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            for d in dirs:
                dest = ar / d.relative_to(Path(COMPANY_FOLDER))
                dest = dest.with_name(f"{dest.name}-{ts}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(d), str(dest))
        else:
            for d in dirs:
                shutil.rmtree(d, ignore_errors=True)

        # requests/<company>
        req_dir = Path(REQUESTS_FOLDER) / company
        if req_dir.is_dir():
            shutil.rmtree(req_dir, ignore_errors=True)


    def locations_for_company(self, company: str):
        """Every location where this company exists in task_config."""
        return [loc for loc, cmap in self.task_config.items() if company in cmap]

    def _select_location_in_listbox(self, loc: str):
        """Visually select a location in the Locations listbox if present."""
        if not hasattr(self, "loc_lb") or not self.loc_lb.winfo_exists():
            return
        try:
            items = list(self.loc_lb.get(0, "end"))
            idx = items.index(loc)
        except ValueError:
            return
        self.loc_lb.selection_clear(0, "end")
        self.loc_lb.selection_set(idx)
        self.loc_lb.see(idx)

    def _all_companies(self):
        """All real companies (no 'Any', no blanks)."""
        self.task_config = load_task_config()
        from_cfg   = {c for locmap in self.task_config.values() for c in locmap.keys()}
        from_users = {u.get("company") for u in self.users}
        bad = {"", None, "Any", "any", "ANY"}
        return sorted(c for c in (from_cfg | from_users) if c not in bad)


    def create_navigation(self):
        # Destroy old bar if it exists
        if hasattr(self, "_nav_bar") and self._nav_bar.winfo_exists():
            self._nav_bar.destroy()

        # Header container
        self._nav_bar = ttk.Frame(self, style="NavBar.TFrame")
        self._nav_bar.pack(fill="x")

        # Left/Right zones
        left  = ttk.Frame(self._nav_bar, style="NavBar.TFrame"); left.pack(side="left", padx=6, pady=6)
        right = ttk.Frame(self._nav_bar, style="NavBar.TFrame"); right.pack(side="right", padx=6, pady=6)

        # Subtle bottom hairline
        tk.Frame(self._nav_bar, height=1, bg=self.BORDER).pack(fill="x", side="bottom")

        # Holders so we can show/hide the active underline
        self._nav_buttons   = {}   # name -> ttk.Button
        self._nav_underbars = {}   # name -> tk.Frame (2px accent)

        for name in ["Shift Viewer", "Handle Requests", "Edit Database", "Control Board"]:
            holder = tk.Frame(left, bg=self.NAV_BG)
            holder.pack(side="left", padx=4)

            btn = ttk.Button(
                holder,
                text=name,
                style="Nav.TButton",
                command=lambda n=name: self.switch_page(n)
            )
            btn.pack(side="top")

            # Accent underline (hidden by default)
            under = tk.Frame(holder, height=2, bg=self.ACCENT)
            # don't pack yet; shown by _set_active_nav

            self._nav_buttons[name]   = btn
            self._nav_underbars[name] = under

        # Optional right-side content (e.g. company name, clock, etc.)
        # ttk.Label(right, text="Admin", background=self.NAV_BG, foreground=self.MUTED).pack()

        # Set initial active tab visually
        self._set_active_nav("Shift Viewer")


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
        # update active nav styling
        if hasattr(self, "_set_active_nav"):
            self._set_active_nav(name)

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

    def _set_active_nav(self, active_name):
        # Toggle button styles and underline bars
        for name, btn in self._nav_buttons.items():
            is_active = (name == active_name)
            btn.configure(style="Nav.Active.TButton" if is_active else "Nav.TButton")

            under = self._nav_underbars[name]
            # show active underline; hide others
            if is_active and not under.winfo_ismapped():
                under.pack(fill="x", side="top")  # appears right under the button
            elif not is_active and under.winfo_ismapped():
                under.pack_forget()

    def clear_main_area(self):
        # cancel control board timer if set
        if hasattr(self, "_cb_after_id") and self._cb_after_id:
            try: self.after_cancel(self._cb_after_id)
            except: pass
            self._cb_after_id = None
        for widget in self.main_area.winfo_children():
            widget.destroy()


    def create_shift_viewer(self):
        self.main_area = tk.Frame(self, bg="#f4f4f4")
        self.main_area.pack(fill="both", expand=True)
        self.show_shift_viewer()

    def show_shift_viewer(self):
        self.clear_main_area()

        left, right = self._toolbar(self.main_area)
        # Time Range
        self.time_range_dropdown = self._chip_combobox(
            left, "Time Range",
            textvariable=self.time_range_var, state="readonly",
            width=16, style="Filter.TCombobox",
            values=["Today","Last 3 Days","Last 7 Days","Last 30 Days",
                    "Last 3 Months","Last Year","All Time"]
        )
        self.time_range_dropdown.bind("<<ComboboxSelected>>", self.refresh_shifts)

        # Location
        self.location_dropdown = self._chip_combobox(
            left, "Location",
            textvariable=self.location_var, state="readonly",
            width=18, style="Filter.TCombobox"
        )
        self.location_dropdown.bind("<<ComboboxSelected>>", self.on_filter_loc_selected)

        # Company
        self.company_dropdown = self._chip_combobox(
            left, "Company",
            textvariable=self.company_var, state="readonly",
            width=18, style="Filter.TCombobox"
        )
        self.company_dropdown.bind("<<ComboboxSelected>>", self.on_filter_comp_selected)

        # User
        self.user_dropdown = self._chip_combobox(
            left, "User",
            textvariable=self.user_var, state="readonly",
            width=18, style="Filter.TCombobox",
            values=["Any"]
        )
        self.user_dropdown.bind("<<ComboboxSelected>>", self.refresh_shifts)

        # Task
        self.task_dropdown = self._chip_combobox(
            left, "Task",
            textvariable=self.task_var, state="readonly",
            width=30, style="Filter.TCombobox"
        )
        self.task_dropdown.bind("<<ComboboxSelected>>", self.refresh_shifts)


        # Action (right side)
        tk.Button(
            right, text="Add Shift",
            font=("Helvetica", 11, "bold"),
            bg=self.ACCENT, fg="white",
            activebackground="#2157b2", activeforeground="white",
            relief="flat", padx=14, pady=6,
            command=self.add_shift
        ).pack(padx=6)


        self.shift_canvas = tk.Canvas(self.main_area, bg="#f4f4f4", highlightthickness=0)
        self.shift_scrollbar = tk.Scrollbar(self.main_area, orient="vertical", command=self.shift_canvas.yview)
        self.shift_canvas.configure(yscrollcommand=self.shift_scrollbar.set)
        self.shift_canvas.pack(side="left", fill="both", expand=True)
        self.shift_scrollbar.pack(side="right", fill="y")

        self.shift_frame = tk.Frame(self.shift_canvas, bg="#f4f4f4")
        self.shift_canvas.create_window((0, 0), window=self.shift_frame, anchor="nw")
        self.shift_frame.bind("<Configure>", lambda e: self.shift_canvas.configure(scrollregion=self.shift_canvas.bbox("all")))

        self.refresh_shifts()


    def add_shift(self):
        win = tk.Toplevel(self)
        win.title("Add Shift")
        win.geometry("400x250")

        # 1) USER
        tk.Label(win, text="User:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        user_var = tk.StringVar()
        user_names = sorted(u["name"] for u in self.users)
        user_cb  = ttk.Combobox(win, textvariable=user_var, values=user_names, state="readonly")
        user_cb.grid( row=0, column=1, sticky="w", padx=5, pady=5)

        # 2) LOCATION
        tk.Label(win, text="Location:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        loc_var = tk.StringVar()
        loc_cb  = ttk.Combobox(win, textvariable=loc_var, state="readonly")
        loc_cb.grid( row=1, column=1, sticky="w", padx=5, pady=5)

        # 3) TASK
        tk.Label(win, text="Task:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        task_var = tk.StringVar()
        task_cb  = ttk.Combobox(win, textvariable=task_var, state="readonly")
        task_cb.grid( row=2, column=1, sticky="w", padx=5, pady=5)

        # 4) CLOCK‑IN / OUT / LUNCH...
        today_str = datetime.now().strftime("%Y-%m-%d")

        tk.Label(win, text="Date (YYYY-MM-DD):").grid(row=3, column=0, sticky="e", padx=5)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(win, textvariable=date_var, width=12, justify="center") \
            .grid(row=3, column=1, sticky="w", padx=5)

        tk.Label(win, text="Clock-in (HH:MM):").grid(row=4, column=0, sticky="e", padx=5)
        in_time_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        tk.Entry(win, textvariable=in_time_var, width=8, justify="center") \
            .grid(row=4, column=1, sticky="w", padx=5)

        tk.Label(win, text="Clock-out (HH:MM):").grid(row=5, column=0, sticky="e", padx=5)
        out_time_var = tk.StringVar(value=datetime.now().strftime("%H:%M"))
        tk.Entry(win, textvariable=out_time_var, width=8, justify="center") \
            .grid(row=5, column=1, sticky="w", padx=5)

        # move Lunch to row 6 (not 5!)
        tk.Label(win, text="Lunch (min):").grid(row=6, column=0, sticky="e", padx=5)
        lunch_var = tk.StringVar(value="0")
        tk.Entry(win, textvariable=lunch_var, width=5) \
            .grid(row=6, column=1, sticky="w", padx=5)

        # move Commute to row 7
        tk.Label(win, text="Commute (min):").grid(row=7, column=0, sticky="e", padx=5, pady=(0,5))
        commute_var = tk.StringVar(value="0")
        tk.Entry(win, textvariable=commute_var, width=5) \
            .grid(row=7, column=1, sticky="w", padx=5, pady=(0,5))

        # Buttons on row 8
        btnf = tk.Frame(win)
        btnf.grid(row=8, column=0, columnspan=2, pady=10)


        # —–––––––––––––––––––––––––––––––––––––––––––
        # When the user changes, we repopulate Location & Task
        def on_user_change(*_):
            name = user_var.get()
            user = next(u for u in self.users if u["name"]==name)

            # all locations where that company has tasks
            locs = sorted(self.task_config.keys())
            loc_cb["values"] = locs

            # also pre‑select first location
            if locs:
                loc_var.set(locs[0])
                on_loc_change()

        def on_loc_change(*_):
            name = user_var.get()
            user = next(u for u in self.users if u["name"]==name)
            company = user["company"]
            loc = loc_var.get()

            # pull tasks for that location+company
            raw = self.task_config.get(loc, {}).get(company, [])
            names = [t["name"] if isinstance(t, dict) else t for t in raw]
            task_cb["values"] = sorted(names)
            if names:
                task_var.set(names[0])

        user_cb.bind("<<ComboboxSelected>>", on_user_change)
        loc_cb .bind("<<ComboboxSelected>>", on_loc_change)

        # OK / Cancel
        btnf = tk.Frame(win); btnf.grid(row=8, column=0, columnspan=2, pady=10)
        tk.Button(
            btnf, text="OK",
            command=lambda: self._save_new_shift(
                win, user_var, loc_var, task_var,
                date_var, in_time_var, out_time_var, lunch_var, commute_var
            )
        ).pack(side="left", padx=5)
        tk.Button(btnf, text="Cancel", command=win.destroy).pack(side="left")

    def _save_new_shift(self, win, user_var, loc_var, task_var, date_var, in_time_var, out_time_var, lunch_var, commute_var):

        user = next((u for u in self.users if u["name"] == user_var.get()), None)
        if not user:
            return messagebox.showerror("Error", "Please choose a user.")

        # date
        try:
            base_date = datetime.fromisoformat(date_var.get()).date()
        except Exception:
            return messagebox.showerror("Error", "Date must be YYYY-MM-DD.")

        # times + minutes
        try:
            ih, im = _parse_hhmm(in_time_var.get())
            oh, om = _parse_hhmm(out_time_var.get())  # required now
            lm = int(lunch_var.get()); cm = int(commute_var.get())
            if lm < 0 or cm < 0:
                raise ValueError
        except Exception:
            return messagebox.showerror(
                "Error",
                "Use HH:MM for times and non-negative integers for Lunch/Commute."
            )

        # build datetimes
        clock_in_dt = datetime.combine(base_date, datetime.min.time()).replace(hour=ih, minute=im)
        clock_out_dt = datetime.combine(base_date, datetime.min.time()).replace(hour=oh, minute=om)
        if clock_out_dt < clock_in_dt:
            clock_out_dt += timedelta(days=1)  # overnight

        entry = {
            "id": str(uuid.uuid4()),
            "clock_in":        clock_in_dt.strftime("%Y-%m-%d %H:%M"),
            "clock_out":       clock_out_dt.strftime("%Y-%m-%d %H:%M"),
            "task":            task_var.get(),
            "location":        loc_var.get(),
            "lunch_minutes":   lm,
            "commute_minutes": cm,
        }

        logs = load_employee_logs(user)
        logs.append(entry)
        save_employee_logs(user, logs)
        win.destroy()
        self.refresh_shifts()


    def on_loc_selected(self, evt=None):
        sel = self.loc_lb.curselection()
        self.current_loc = self.loc_lb.get(sel) if sel else None

        # do not auto-select a company
        self.current_comp = None

        self.refresh_companies()
        self.refresh_tasks()

        comp = self.current_comp or "—"
        self.breadcrumb_var.set(f"{self.current_loc or '—'}  ▸  {comp}")


    def on_comp_selected(self, evt=None):
        lb = evt.widget if evt else getattr(self, "comp_lb", None)
        if not lb or not lb.winfo_exists():
            return
        try:
            sel = lb.curselection()
            self.current_comp = lb.get(sel) if sel else None
        except tk.TclError:
            self.current_comp = None
            return

        # If company isn’t at current location, jump to a location that has it.
        if self.current_comp:
            locs = self.locations_for_company(self.current_comp)
            if locs:
                if getattr(self, "current_loc", None) not in locs:
                    self.current_loc = locs[0]
                    self._select_location_in_listbox(self.current_loc)

        self.refresh_tasks()
        self.breadcrumb_var.set(f"{getattr(self, 'current_loc', None) or '—'}  ▸  {self.current_comp or '—'}")




    def get_company_names(self):
        return [name for name in os.listdir(COMPANY_FOLDER)
                if os.path.isdir(os.path.join(COMPANY_FOLDER, name))]

    def on_filter_loc_selected(self, _evt=None):
        self.refresh_shifts()

    def on_filter_comp_selected(self, _evt=None):
        self.refresh_shifts()



    def refresh_shifts(self, event=None):
        # 1) clear existing cards
        for w in self.shift_frame.winfo_children():
            w.destroy()

        # 2) grab filter settings
        loc_filter   = self.location_var.get()
        comp_filter  = self.company_var.get()
        user_filter  = self.user_var.get()
        task_filter  = self.task_var.get()
        time_range   = self.time_range_var.get()

        # 3) compute date window (open-ended into the future)
        today = datetime.now().date()
        if time_range == "Today":
            start_date = today
        elif time_range == "Last 3 Days":
            start_date = today - timedelta(days=2)
        elif time_range == "Last 7 Days":
            start_date = today - timedelta(days=6)
        elif time_range == "Last 30 Days":
            start_date = today - timedelta(days=29)
        elif time_range == "Last 3 Months":
            start_date = today - timedelta(days=90)
        elif time_range == "Last Year":
            start_date = today - timedelta(days=365)
        elif time_range == "All Time":
            from datetime import date
            start_date = date.min
        else:
            start_date = today

        window_start = datetime.combine(start_date, datetime.min.time())
        # 👇 open the end of the window so future shifts are included
        window_end   = datetime.max

        # 4) dropdowns
        cfg = self.task_config
        all_locs = sorted(cfg.keys())
        self.location_dropdown['values'] = ["Any"] + all_locs

        if loc_filter != "Any":
            comps = sorted(cfg.get(loc_filter, {}).keys())
        else:
            comps = sorted({c for sub in cfg.values() for c in sub.keys()})
        self.company_dropdown['values'] = ["Any"] + comps

        tasks_set = set()
        if loc_filter!="Any" and comp_filter!="Any":
            raw = cfg.get(loc_filter, {}).get(comp_filter, [])
            tasks_set = {t["name"] if isinstance(t, dict) else t for t in raw}
        elif loc_filter!="Any":
            for raw in cfg.get(loc_filter, {}).values():
                tasks_set |= {t["name"] if isinstance(t, dict) else t for t in raw}
        elif comp_filter!="Any":
            for locmap in cfg.values():
                raw = locmap.get(comp_filter, [])
                tasks_set |= {t["name"] if isinstance(t, dict) else t for t in raw}
        else:
            for locmap in cfg.values():
                for raw in locmap.values():
                    tasks_set |= {t["name"] if isinstance(t, dict) else t for t in raw}
        self.task_dropdown['values'] = ["Any"] + sorted(tasks_set)

        # Users dropdown (respect Company and optional Location)
        if comp_filter != "Any":
            candidate_users = [u for u in self.users if u["company"] == comp_filter]
        else:
            candidate_users = list(self.users)
        if loc_filter != "Any":
            companies_at_loc = set(cfg.get(loc_filter, {}).keys())
            candidate_users = [u for u in candidate_users if u["company"] in companies_at_loc]
        user_names = sorted({u["name"] for u in candidate_users})
        self.user_dropdown['values'] = ["Any"] + user_names
        if self.user_var.get() not in (["Any"] + user_names):
            self.user_var.set("Any")

        # 5) build lists; now we also collect SCHEDULED shifts (start > now)
        now_dt = datetime.now()
        users = [
            u for u in self.users
            if (comp_filter == "Any" or u["company"] == comp_filter)
            and (user_filter  == "Any" or u["name"]    == user_filter)
        ]

        active, finished, scheduled = [], [], []
        for u in users:
            for log in load_employee_logs(u):
                s = _parse_iso(log.get("clock_in"))
                e = _parse_iso(log.get("clock_out")) or now_dt
                if not s:
                    continue

                # location / task filters
                if loc_filter != "Any" and log.get("location") != loc_filter:
                    continue
                if task_filter != "Any" and log.get("task") != task_filter:
                    continue

                # keep only shifts whose interval overlaps the window
                if e < window_start or s > window_end:
                    continue

                end = log.get("clock_out")
                commute_raw = log.get("commute_minutes", log.get("commute", 0))
                rec = {
                    "name":            u["name"],
                    "uid":             u["id"],
                    "task":            log["task"],
                    "location":        log["location"],
                    "clock_in":        log["clock_in"],
                    "clock_out":       end,
                    "lunch_minutes":   log.get("lunch_minutes", u.get("lunch_minutes", 0)),
                    "commute_minutes": int(commute_raw or 0),
                }

                if s > now_dt:
                    scheduled.append(rec)      # starts in the future
                elif end is None:
                    active.append(rec)         # open shift
                else:
                    finished.append(rec)       # ended in the past

        def mark_conflict_groups(recs):
            buckets = defaultdict(list)
            for r in recs:
                s = _parse_iso(r.get("clock_in"))
                if not s:
                    continue
                day = s.strftime("%Y-%m-%d")
                buckets[(r["uid"], day)].append(r)

            for group in buckets.values():
                intervals = []
                now_dt = datetime.now()
                for r in group:
                    s = _parse_iso(r.get("clock_in"))
                    e = _parse_iso(r.get("clock_out"))
                    if not s:
                        continue
                    if e is None:
                        e = now_dt
                    if e < s:
                        continue
                    intervals.append((r, s, e))

                n = len(intervals)
                if n <= 1:
                    continue

                parent = list(range(n))
                def find(i):
                    while parent[i] != i:
                        parent[i] = parent[parent[i]]
                        i = parent[i]
                    return i
                def union(i, j):
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[rj] = ri

                for i in range(n):
                    _, s1, e1 = intervals[i]
                    for j in range(i+1, n):
                        _, s2, e2 = intervals[j]
                        if s2 < e1 and s1 < e2:
                            union(i, j)

                comps = defaultdict(list)
                for i in range(n):
                    comps[find(i)].append(i)

                group_id = 1
                for idxs in comps.values():
                    if len(idxs) > 1:
                        for idx in idxs:
                            rec = intervals[idx][0]
                            rec["conflict_group"] = group_id
                        group_id += 1

        # mark conflicts in all three buckets
        mark_conflict_groups(active)
        mark_conflict_groups(finished)
        mark_conflict_groups(scheduled)

        # Optional commute zero-out for 2nd+ finished shift same day
        finished.sort(key=lambda info: info["clock_in"])
        seen = set()
        for rec in finished:
            day_key = (rec["uid"], rec["clock_in"][:10])
            if day_key in seen:
                rec["commute_minutes"] = 0
            else:
                seen.add(day_key)

        # render (now passes the 'scheduled' list too)
        self.display_shifts(active, finished, scheduled)




    def show_handle_requests(self):
        self.clear_main_area()

        ttk.Label(self.main_area,
                text="Shift Edit Requests",
                style="Heading.TLabel").pack(anchor="w", padx=12, pady=(12, 4))

        # If you don't already have these:
        self.req_company_var = getattr(self, "req_company_var", tk.StringVar(value="Any"))
        self.req_status_var  = getattr(self, "req_status_var",  tk.StringVar(value="Any"))

        # Toolbar
        left, right = self._toolbar(self.main_area)

        req_company_cb = self._chip_combobox(
            left, "Company",
            textvariable=self.req_company_var, state="readonly",
            width=28, style="Filter.TCombobox",
            values=(["Any"] + sorted(os.listdir(REQUESTS_FOLDER))
                    if os.path.isdir(REQUESTS_FOLDER) else ["Any"])
        )
        req_company_cb.bind("<<ComboboxSelected>>", lambda e: self.show_handle_requests())

        req_status_cb = self._chip_combobox(
            left, "Status",
            textvariable=self.req_status_var, state="readonly",
            width=18, style="Filter.TCombobox",
            values=["Any","Pending","Approved","Rejected"]
        )
        req_status_cb.bind("<<ComboboxSelected>>", lambda e: self.show_handle_requests())

        # ── Scrollable area ─────────────────────────────────────────────
        canvas = tk.Canvas(self.main_area, bg=APP_BG, highlightthickness=0)
        vbar   = tk.Scrollbar(self.main_area, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        grid_frame = tk.Frame(canvas, bg=APP_BG)
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        grid_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # 3 cards per row
        for c in range(3):
            grid_frame.grid_columnconfigure(c, weight=1, uniform="reqcol")

        # ── Build cards ─────────────────────────────────────────────────
        current_index = 0
        company_filter = self.req_company_var.get()
        status_filter  = self.req_status_var.get().lower()

        if not os.path.isdir(REQUESTS_FOLDER):
            tk.Label(grid_frame, text="No requests folder found.",
                    font=("Helvetica", 13, "italic"), fg="gray50", bg=APP_BG).grid(padx=20, pady=20)
            return

        for company in sorted(os.listdir(REQUESTS_FOLDER)):
            company_path = os.path.join(REQUESTS_FOLDER, company)
            if not os.path.isdir(company_path):
                continue
            if company_filter != "Any" and company != company_filter:
                continue

            for filename in sorted(os.listdir(company_path)):
                if not filename.endswith("_requests.json"):
                    continue

                employee_id = filename.replace("_requests.json", "")
                user = get_user_by_id(employee_id, self.users)
                if user is None:
                    employee_name = employee_id
                else:
                    employee_name = (user["name"], user["id"])
                filepath = os.path.join(company_path, filename)

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        requests = json.load(f)
                except json.JSONDecodeError:
                    continue

                for req in requests:
                    # apply status filter
                    st = str(req.get("status", "pending")).lower()
                    if status_filter != "any" and st != status_filter:
                        continue

                    col = current_index % 3
                    row = current_index // 3
                    card = self.create_request_card(grid_frame, employee_name, req, company, filepath)
                    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
                    current_index += 1

        if current_index == 0:
            tk.Label(grid_frame, text="No requests match your filters.",
                    font=("Helvetica", 13, "italic"), fg="gray50", bg=APP_BG).grid(padx=20, pady=20)


    def show_control_board(self):
        self.clear_main_area()
        self._cb_after_id = None  # initialize

        self.cb_canvas = tk.Canvas(self.main_area, bg=self.APP_BG, highlightthickness=0)
        self.cb_vbar   = tk.Scrollbar(self.main_area, orient="vertical", command=self.cb_canvas.yview)
        self.cb_canvas.configure(yscrollcommand=self.cb_vbar.set)
        self.cb_canvas.pack(side="left", fill="both", expand=True)
        self.cb_vbar.pack(side="right", fill="y")

        self.cb_cards_frame = tk.Frame(self.cb_canvas, bg=self.APP_BG)
        self.cb_canvas.create_window((0, 0), window=self.cb_cards_frame, anchor="nw")
        self.cb_cards_frame.bind("<Configure>",
            lambda e: self.cb_canvas.configure(scrollregion=self.cb_canvas.bbox("all")))

        self.refresh_control_board()




    def refresh_control_board(self):
        # If the control-board UI isn’t on screen anymore, bail out safely
        if not hasattr(self, "cb_cards_frame") or not self.cb_cards_frame.winfo_exists():
            return

        # If there is a pending timer, cancel it before rebuilding
        if hasattr(self, "_cb_after_id") and self._cb_after_id:
            try: self.after_cancel(self._cb_after_id)
            except: pass
            self._cb_after_id = None

        for w in self.cb_cards_frame.winfo_children():
            w.destroy()

        # bigger cards, two per row
        per_row = 2
        for c in range(per_row):
            self.cb_cards_frame.grid_columnconfigure(c, weight=1, uniform="cbcol", minsize=650)

        # ALWAYS show all locations
        locations = sorted(self.task_config.keys())

        cards = [self._build_location_metrics(loc) for loc in locations]

        if not cards:
            tk.Label(self.cb_cards_frame, text="Engir starfsmenn skráðir í dag.",
                    font=("Helvetica", 14, "italic"), fg="gray50", bg=self.APP_BG) \
            .grid(sticky="n", padx=20, pady=20)
            return

        for i, m in enumerate(cards):
            r, c = divmod(i, per_row)
            card_outer = self._location_card(self.cb_cards_frame, **m, _wide=True)
            card_outer.grid(row=r, column=c, padx=14, pady=14, sticky="nsew")
            self.cb_cards_frame.grid_rowconfigure(r, weight=1, minsize=350)

        # auto-refresh
        self.after(30_000, self.refresh_control_board)



    def _sort_treeview(self, tv: ttk.Treeview, col_index: int, numeric: bool=False, reverse: bool=False):
        def key(row):
            v = tv.item(row, "values")[col_index]
            if numeric:
                try:
                    return int(v)
                except Exception:
                    return -10**9
            return str(v).lower()
        rows = list(tv.get_children(""))
        rows.sort(key=key, reverse=reverse)
        for i, r in enumerate(rows):
            tv.move(r, "", i)
        # toggle on next click
        tv.heading(tv["columns"][col_index], command=lambda: self._sort_treeview(tv, col_index, numeric, not reverse))



    def _build_location_metrics(self, location: str):
        """
        Return metrics for a location:
        - company_rows: list of (company, active_now, worked_today)
        - total_on_site, total_worked_today
        Always returns a dict (zeros ok).
        """
        if location not in self.task_config:
            return {
                "location": location,
                "company_rows": [],
                "total_on_site": 0,
                "total_worked_today": 0,
            }

        start_today = datetime.combine(datetime.now().date(), datetime.min.time())
        end_today   = start_today + timedelta(days=1)
        now_dt      = datetime.now()

        active_now_by_company  = defaultdict(set)  # company -> {uid}
        worked_today_by_company= defaultdict(set)  # company -> {uid}
        on_site_now_ids        = set()
        worked_today_ids       = set()

        for u in self.users:
            company = u.get("company", "Óskilgreint")
            try:
                logs = load_employee_logs(u)
            except Exception:
                continue

            for log in logs:
                if log.get("location") != location:
                    continue

                s = _parse_iso(log.get("clock_in"))
                e = _parse_iso(log.get("clock_out"))
                if not s:
                    continue

                # active now?
                if e is None:
                    on_site_now_ids.add(u["id"])
                    active_now_by_company[company].add(u["id"])

                # overlaps today?
                e2 = e or now_dt
                if s < end_today and e2 > start_today:
                    worked_today_ids.add(u["id"])
                    worked_today_by_company[company].add(u["id"])

        # build sorted rows (active desc, then name)
        company_rows = []
        all_companies = set(active_now_by_company.keys()) | set(worked_today_by_company.keys())
        for comp in all_companies:
            company_rows.append((
                comp,
                len(active_now_by_company.get(comp, set())),
                len(worked_today_by_company.get(comp, set())),
            ))
        company_rows.sort(key=lambda r: (-r[1], r[0]))

        return {
            "location": location,
            "company_rows": company_rows,
            "total_on_site": len(on_site_now_ids),
            "total_worked_today": len(worked_today_ids),
        }


    

    def _location_card(self, parent, *, location, company_rows, total_on_site, total_worked_today, _wide=True):
        # palette
        APP_BG    = self.APP_BG
        CARD_BG   = "#ffffff"
        BORDER    = self.BORDER
        HEADER_BG = "#e9f0f8"
        TEXT      = self.TEXT
        MUTED     = self.MUTED
        ROW_ALT   = "#fafafa"
        HOVER_BG  = "#eef3fb"

        # sizing / typography
        pad        = 16 if _wide else 12
        hdr_font   = ("Helvetica", 15, "bold") if _wide else ("Helvetica", 13, "bold")
        label_b    = ("Helvetica", 11, "bold") if _wide else ("Helvetica", 10, "bold")
        label_n    = ("Helvetica", 11)         if _wide else ("Helvetica", 10)
        pill_title = ("Helvetica", 11, "bold") if _wide else ("Helvetica", 10, "bold")
        pill_value = ("Helvetica", 26, "bold") if _wide else ("Helvetica", 22, "bold")

        outer = tk.Frame(parent, bg=APP_BG)

        # let the card size itself (no fixed width/height, no pack_propagate(False))
        card = tk.Frame(
            outer, bg=CARD_BG, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER
        )
        card.pack(fill="both", expand=True, padx=8, pady=8)

        # Header
        hdr = tk.Frame(card, bg=HEADER_BG); hdr.pack(fill="x")
        tk.Label(hdr, text=location, font=hdr_font, bg=HEADER_BG, fg=TEXT, pady=10)\
            .pack(side="left", padx=pad)
        tk.Frame(card, height=2, bg=self.ACCENT).pack(fill="x")

        body = tk.Frame(card, bg=CARD_BG); body.pack(fill="both", expand=True, padx=pad, pady=pad)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)

        # ---------- Left: simple table (auto height, no scrollbar) ----------
        left = tk.Frame(body, bg=CARD_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, pad))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=0)

        # table header (plain text, not clickable)
        th = tk.Frame(left, bg="#f7f7fb", highlightthickness=1, highlightbackground=BORDER)
        th.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        tk.Label(th, text="Fyrirtæki",   font=label_b, bg="#f7f7fb", fg=TEXT, padx=10, pady=8).pack(side="left")
        tk.Label(th, text="Á stað / Í dag", font=label_b, bg="#f7f7fb", fg=TEXT, padx=10, pady=8).pack(side="right")

        # rows
        if not company_rows:
            row = tk.Frame(left, bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
            row.grid(row=1, column=0, columnspan=2, sticky="ew")
            tk.Label(row, text="— enginn skráður núna —", font=label_n, bg=CARD_BG, fg=MUTED, padx=10, pady=8)\
            .pack(anchor="w")
        else:
            for i, (comp, active_cnt, today_cnt) in enumerate(company_rows, start=1):
                bg = CARD_BG if i % 2 else ROW_ALT
                row = tk.Frame(left, bg=bg, highlightthickness=1, highlightbackground=BORDER)
                row.grid(row=i, column=0, columnspan=2, sticky="ew")
                # hover
                def _mk_hover(r=row, base=bg):
                    r.bind("<Enter>", lambda _e, rr=r: rr.configure(bg=HOVER_BG))
                    r.bind("<Leave>", lambda _e, rr=r, bb=base: rr.configure(bg=bb))
                _mk_hover()

                # company name (clickable)
                name_lbl = tk.Label(row, text=comp, font=label_n, bg=bg, fg=TEXT, padx=10, pady=8, anchor="w")
                name_lbl.pack(side="left", fill="x", expand=True)

                # counts “A / D”
                cnt_lbl = tk.Label(row, text=f"{active_cnt} / {today_cnt}", font=label_b, bg=bg, fg=TEXT, padx=10, pady=8)
                cnt_lbl.pack(side="right")

                # open detail on double click or Enter
                def _open(_=None, L=location, C=comp):
                    self._open_company_detail(L, C)
                for w in (row, name_lbl, cnt_lbl):
                    w.bind("<Double-1>", _open)
                    w.bind("<Return>", _open)
                    w.configure(cursor="hand2")

        # ---------- Right: stat pills ----------
        right = tk.Frame(body, bg=CARD_BG)
        right.grid(row=0, column=1, sticky="n")

        def stat_pill(title, value):
            wrap = tk.Frame(right, bg="#eef3fb", highlightthickness=1, highlightbackground=BORDER)
            wrap.pack(fill="x", pady=8)
            tk.Label(wrap, text=title, font=pill_title, bg="#eef3fb", fg=MUTED, padx=12, pady=8, anchor="w").pack(fill="x")
            tk.Label(wrap, text=str(value), font=pill_value, bg="#eef3fb", fg=TEXT, pady=10).pack()

        stat_pill("Fjöldi manns á stað:", total_on_site)
        stat_pill("Fjöldi manns búin að vinna hér í dag:", total_worked_today)

        return outer





    def _open_company_detail(self, location: str, company: str):
        """
        Popup with two tables:
        - Currently Working now at (location, company)
        - Worked here today (finished or active earlier)
        """
        start_today = datetime.combine(datetime.now().date(), datetime.min.time())
        end_today   = start_today + timedelta(days=1)
        now_dt      = datetime.now()

        active_rows   = []  # (name, task, start_str, duration_str)
        today_rows    = []  # (name, task, start_str, end_str, total_str)

        for u in self.users:
            if u.get("company") != company:
                continue
            try:
                logs = load_employee_logs(u)
            except Exception:
                continue

            # track if this user already counted in 'today_rows'
            added_today = False
            for log in logs:
                if log.get("location") != location:
                    continue

                s = _parse_iso(log.get("clock_in"))
                e = _parse_iso(log.get("clock_out"))
                if not s:
                    continue
                task = log.get("task","")

                # Active now?
                if e is None:
                    dur = now_dt - s
                    hrs = int(dur.total_seconds() // 3600)
                    mins = int((dur.total_seconds() % 3600) // 60)
                    active_rows.append((
                        u["name"],
                        task,
                        s.strftime("%H:%M"),
                        f"{hrs}h {mins}m"
                    ))

                # Overlaps today?
                e2 = e or now_dt
                if s < end_today and e2 > start_today and not added_today:
                    total = e2 - s
                    # subtract lunch/commute only if finished (to match your finished card logic)
                    lunch_m   = int(log.get("lunch_minutes", u.get("lunch_minutes", 0)) or 0)
                    commute_m = int(log.get("commute_minutes", u.get("commute_minutes", 0)) or 0)
                    if e is not None:
                        total = total + timedelta(minutes=commute_m) - timedelta(minutes=lunch_m)
                        if total.total_seconds() < 0:
                            total = timedelta(0)
                    th = int(total.total_seconds() // 3600)
                    tm = int((total.total_seconds() % 3600) // 60)
                    today_rows.append((
                        u["name"], task,
                        s.strftime("%H:%M"),
                        (e.strftime("%H:%M") if e else "—"),
                        f"{th}h {tm}m"
                    ))
                    added_today = True

        # sort nicely
        active_rows.sort(key=lambda r: (r[0], r[2]))
        today_rows.sort(key=lambda r: (r[0], r[2]))

        # ── UI ───────────────────────────────────────────
        win = tk.Toplevel(self)
        win.title(f"{location} — {company}")
        win.geometry("760x520")
        win.configure(bg=self.APP_BG)

        # header
        ttk.Label(win, text=f"{location} — {company}", style="Heading.TLabel") \
            .pack(anchor="w", padx=12, pady=(12, 6))

        container = tk.Frame(win, bg=self.APP_BG); container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure(0, weight=1)

        # helper to build a Treeview card
        def make_table(parent, title, columns, rows):
            outer, body = self._section_card(parent, title, fill_y=False)
            outer.grid(sticky="ew", padx=6, pady=6)
            body.grid_columnconfigure(0, weight=1)

            tv = ttk.Treeview(body, columns=columns, show="headings", height=8)
            tv.grid(row=0, column=0, sticky="nsew")
            sb = ttk.Scrollbar(body, orient="vertical", command=tv.yview)
            sb.grid(row=0, column=1, sticky="ns")
            tv.configure(yscrollcommand=sb.set)

            # column headings & widths
            for col, width in columns:
                tv.heading(col, text=col)
                tv.column(col, width=width, anchor="center")

            for row in rows:
                tv.insert("", "end", values=row)

            return tv

        # Active now
        make_table(
            container,
            f"Fólk á vakt núna ({len(active_rows)})",
            [("Nafn", 200), ("Verk", 220), ("Frá", 80), ("Tími", 90)],
            active_rows
        )

        # Worked today
        make_table(
            container,
            f"Vinna í dag ({len(today_rows)})",
            [("Nafn", 200), ("Verk", 220), ("Byrjaði", 80), ("Endaði", 80), ("Samtals", 90)],
            today_rows
        )

        # Close button
        tk.Button(win, text="Close", command=win.destroy).pack(pady=6)


    def _hover_highlight(self, widget, base_bg, hover_bg="#eef3fb"):
        widget.bind("<Enter>", lambda _e: widget.configure(bg=hover_bg))
        widget.bind("<Leave>", lambda _e: widget.configure(bg=base_bg))


    def _company_card(self, parent, company, names):
        # colors
        APP_BG     = self["bg"] if self["bg"] else "#f4f4f4"
        CARD_BG    = "#ffffff"
        BORDER     = "#d6dbe3"
        HEADER_BG  = "#e9f0f8"
        TEXT       = "#2e2e2e"
        SUBTLE_ROW = "#fafafa"

        # outer matches app bg (no white strip)
        outer = tk.Frame(parent, bg=APP_BG)

        # inner card
        card = tk.Frame(
            outer, bg=CARD_BG, bd=0,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER
        )
        card.pack(fill="both", expand=True)

        # header bar
        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill="x")
        tk.Label(
            header, text=f"{company}  —  {len(names)}",
            font=("Helvetica", 12, "bold"), bg=HEADER_BG, fg=TEXT, pady=6
        ).pack(padx=8)

        # body
        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=10, pady=8)

        # employee rows
        for i, name in enumerate(names):
            row_bg = CARD_BG if i % 2 == 0 else SUBTLE_ROW
            row = tk.Frame(body, bg=row_bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="•", font=("Helvetica", 14), bg=row_bg, fg=TEXT).pack(side="left")
            tk.Label(row, text=name, font=("Helvetica", 11), bg=row_bg, fg=TEXT).pack(side="left", padx=4)

        return outer

    def _chip_combobox(self, parent, label_text, **cb_kwargs):
        """Create a pill + ttk.Combobox that actually lives inside the pill.
        Returns the Combobox so you can bind to it."""
        chip = tk.Frame(
            parent,
            bg=self.PILL_BG,
            highlightthickness=1,
            highlightbackground=self.BORDER,
            highlightcolor=self.BORDER,
        )
        ttk.Label(chip, text=label_text, style="FilterLabel.TLabel") \
            .pack(side="left", padx=(10, 6), pady=6)
        cb = ttk.Combobox(chip, **cb_kwargs)
        cb.pack(side="left", padx=(0, 10), pady=6)
        chip.pack(side="left", padx=6, pady=2)
        return cb

    def display_shifts(self, active, finished, scheduled=None):
        scheduled = scheduled or []

        # Clear existing
        for w in self.shift_frame.winfo_children():
            w.destroy()

        APP_BG = self["bg"] if self["bg"] else "#f4f4f4"
        wrapper = tk.Frame(self.shift_frame, bg=APP_BG)
        wrapper.pack(fill="x", expand=True, padx=10, pady=8)

        COLS = 3

        # ── Currently Working
        outer_a, body_a = self._section_card(wrapper, "Currently Working",
                                            accent="#f49301", fill_y=False)
        outer_a.pack(fill="x", expand=False, padx=6, pady=6)
        if active:
            for c in range(COLS): body_a.grid_columnconfigure(c, weight=1, uniform="actcol")
            for i, info in enumerate(active):
                r, c = divmod(i, COLS)
                self._shift_card(body_a, info, active=True).grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        else:
            tk.Label(body_a, text="No one is currently working.",
                    font=("Helvetica", 11, "italic"), fg="gray50", bg="#ffffff").pack(anchor="w", padx=10, pady=8)

        # ── Scheduled (future)  ← NEW
        outer_s, body_s = self._section_card(wrapper, "Scheduled Shifts",
                                            accent="#2563eb", fill_y=False)
        outer_s.pack(fill="x", expand=False, padx=6, pady=6)
        if scheduled:
            for c in range(COLS): body_s.grid_columnconfigure(c, weight=1, uniform="schcol")
            for i, info in enumerate(scheduled):
                r, c = divmod(i, COLS)
                self._shift_card(body_s, info, active=False).grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        else:
            tk.Label(body_s, text="No scheduled shifts in range.",
                    font=("Helvetica", 11, "italic"), fg="gray50", bg="#ffffff").pack(anchor="w", padx=10, pady=8)

        # ── Finished
        outer_f, body_f = self._section_card(wrapper, "Finished Shifts",
                                            accent="#2e7730", fill_y=False)
        outer_f.pack(fill="x", expand=False, padx=6, pady=6)
        if finished:
            for c in range(COLS): body_f.grid_columnconfigure(c, weight=1, uniform="fincol")
            for i, info in enumerate(finished):
                r, c = divmod(i, COLS)
                self._shift_card(body_f, info, active=False).grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
        else:
            tk.Label(body_f, text="No finished shifts in range.",
                    font=("Helvetica", 11, "italic"), fg="gray50", bg="#ffffff").pack(anchor="w", padx=10, pady=8)


    def _section_card(self, parent, title, accent="#3b82f6", fill_y=True):
        APP_BG   = self["bg"] if self["bg"] else "#f4f4f4"
        CARD_BG  = "#ffffff"
        BORDER   = "#d6dbe3"
        HEADER_BG= "#e9f0f8"
        TEXT     = "#2e2e2e"

        outer = tk.Frame(parent, bg=APP_BG)

        card = tk.Frame(outer, bg=CARD_BG, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        # ↓ only fill vertically when asked
        if fill_y:
            card.pack(fill="both", expand=True)
        else:
            card.pack(fill="x", expand=False)

        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill="x")
        tk.Label(header, text=title, font=("Helvetica", 13, "bold"),
                bg=HEADER_BG, fg=TEXT, pady=8).pack(side="left", padx=10)

        tk.Frame(card, height=2, bg=accent).pack(fill="x")

        body = tk.Frame(card, bg=CARD_BG)
        if fill_y:
            body.pack(fill="both", expand=True, padx=12, pady=10)
        else:
            body.pack(fill="x", expand=False, padx=12, pady=10)

        return outer, body



    def _shift_card(self, parent, info, active=True):
        """
        Pretty card for a single shift.
        """
        BORDER   = "#d6dbe3"
        CARD_BG  = "#ffffff"
        ROW_ALT  = "#fafafa"
        TEXT     = "#2e2e2e"
        SUBTEXT  = "#6b7280"

        name      = info["name"]
        uid       = info["uid"]
        task      = info["task"]
        location  = info["location"]
        clock_in  = info["clock_in"]
        clock_out = info["clock_out"]

        start_dt  = datetime.fromisoformat(clock_in)
        end_dt    = datetime.now() if active else (datetime.fromisoformat(clock_out) if clock_out else None)
        lunch_m   = int(info.get("lunch_minutes", 0) or 0)
        commute_m = int(info.get("commute_minutes", 0) or 0)

        # status chip (ACTIVE / SCHEDULED / FINISHED)
        now_dt = datetime.now()
        is_scheduled = (not active) and (start_dt > now_dt)
        if active:
            status_text, status_bg, status_fg = "ACTIVE", "#fde68a", "#92400e"
        elif is_scheduled:
            status_text, status_bg, status_fg = "SCHEDULED", "#dbeafe", "#1e40af"   # blue
        else:
            status_text, status_bg, status_fg = "FINISHED", "#d1fae5", "#065f46"

        # compute totals for finished & scheduled
        summary_text = ""
        if end_dt:
            secs = (end_dt - start_dt).total_seconds()
            if not active:
                secs = secs + (commute_m * 60) - (lunch_m * 60)
                secs = max(0, secs)
            hrs  = int(secs // 3600); mins = int((secs % 3600) // 60)
            if active:
                summary_text = f"On since {start_dt.strftime('%H:%M')}  ·  {hrs}h {mins}m"
            else:
                summary_text = f"{start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}  ·  total {hrs}h {mins}m"

        # card
        card = tk.Frame(parent, bg=CARD_BG, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        # header row
        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.pack(fill="x", padx=10, pady=(8, 4))

        status_text = "ACTIVE" if active else "FINISHED"
        status_bg   = "#fde68a" if active else "#d1fae5"
        status_fg   = "#92400e" if active else "#065f46"

        # name + status
        tk.Label(hdr, text=name, font=("Helvetica", 12, "bold"),
                bg=CARD_BG, fg=TEXT).pack(side="left")
        tk.Label(hdr, text=status_text, font=("Helvetica", 9, "bold"),
                bg=status_bg, fg=status_fg, padx=8, pady=2).pack(side="right")

        # info rows
        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=10, pady=(0,6))

        # line 1: task + location
        row1 = tk.Frame(body, bg=CARD_BG); row1.pack(fill="x")
        tk.Label(row1, text=f"🏷  {task}", bg=CARD_BG, fg=TEXT,
                font=("Helvetica", 10)).pack(side="left")
        tk.Label(row1, text=f"📍  {location}", bg=CARD_BG, fg=TEXT,
                font=("Helvetica", 10)).pack(side="right")

        # line 2: date + times
        row2 = tk.Frame(body, bg=ROW_ALT); row2.pack(fill="x", pady=6)
        tk.Label(row2, text=start_dt.strftime("%A, %Y-%m-%d"),
                bg=ROW_ALT, fg=SUBTEXT, font=("Helvetica", 10, "italic")).pack(side="left", padx=6, pady=4)
        tk.Label(row2, text=summary_text, bg=ROW_ALT, fg=SUBTEXT,
                font=("Helvetica", 10)).pack(side="right", padx=6)

        # line 3 (finished only): lunch/commute chips + conflict badge if any
        if not active and clock_out:
            row3 = tk.Frame(body, bg=CARD_BG); row3.pack(fill="x", pady=(2,0))
            chip = lambda txt: tk.Label(row3, text=txt, bg="#f3f4f6", fg="#374151",
                                        font=("Helvetica", 9), padx=8, pady=2)
            chip(f"Lunch {lunch_m}m").pack(side="left", padx=(0,6))
            chip(f"Commute {commute_m}m").pack(side="left")
            grp = info.get("conflict_group")
            if grp is not None:
                tk.Label(row3, text=f"⚠ conflict {grp}", bg="#fee2e2", fg="#991b1b",
                        font=("Helvetica", 9, "bold"), padx=6, pady=2).pack(side="right")

        # buttons
        btns = tk.Frame(card, bg=CARD_BG); btns.pack(fill="x", padx=8, pady=8)
        style_btn = dict(font=("Helvetica", 10), padx=10, pady=2)
        if active:
            tk.Button(btns, text="End Shift",
                    command=lambda: self.end_shift(uid, clock_in), **style_btn).pack(side="left")
        else:
            tk.Button(btns, text="Edit",
                    command=lambda: self.edit_shift(uid, clock_in), **style_btn).pack(side="left")
        tk.Button(btns, text="Delete",
                command=lambda: self.delete_shift(uid, clock_in), **style_btn).pack(side="left", padx=(6,0))

        return card


    
    
    def edit_shift(self, user_id, clock_in_time):
        user = next((u for u in self.users if u["id"] == user_id), None)
        if not user:
            return messagebox.showerror("Error", "User not found.")

        logs = load_employee_logs(user)
        target = next((log for log in logs if log["clock_in"] == clock_in_time), None)
        if not target:
            return messagebox.showerror("Error", "Shift not found.")

        # Hard block: only finished shifts are editable
        if not target.get("clock_out"):
            return messagebox.showwarning(
                "Editing blocked",
                "You can only edit finished shifts.\nEnd the shift first."
            )

        start_dt = _parse_iso(target.get("clock_in"))
        end_dt   = _parse_iso(target.get("clock_out"))
        if not start_dt or not end_dt:
            return messagebox.showerror("Error", "Shift has invalid timestamps.")

        win = tk.Toplevel(self)
        win.title("Edit Finished Shift")
        win.geometry("360x420")

        # ─ Location
        tk.Label(win, text="Location").pack(pady=(6,0))
        loc_var = tk.StringVar(value=target.get("location", ""))
        ttk.Combobox(win, textvariable=loc_var,
                    values=sorted(self.task_config.keys()),
                    state="readonly").pack(padx=8)

        # ─ Task (depends on location + user's company)
        tk.Label(win, text="Task").pack(pady=(6,0))
        task_var = tk.StringVar(value=target.get("task",""))
        task_cb = ttk.Combobox(win, textvariable=task_var, state="readonly")
        task_cb.pack(padx=8)

        def _refresh_tasks(*_):
            loc = loc_var.get()
            comp = user["company"]
            items = self.task_config.get(loc, {}).get(comp, [])
            names = [t["name"] if isinstance(t, dict) else t for t in items]
            task_cb["values"] = sorted(names)
            if task_var.get() not in names:
                task_var.set(names[0] if names else "")
        loc_var.trace_add("write", _refresh_tasks)
        _refresh_tasks()

        # ─ Date (read-only)
        tk.Label(win, text="Date").pack(pady=(8,0))
        date_label = tk.Label(win, text=start_dt.strftime("%Y-%m-%d"))
        date_label.pack()

        # ─ Time inputs (HH:MM only)
        tk.Label(win, text="Clock-in time (HH:MM)").pack(pady=(8,0))
        in_time_var = tk.StringVar(value=start_dt.strftime("%H:%M"))
        tk.Entry(win, textvariable=in_time_var, width=8, justify="center").pack()

        tk.Label(win, text="Clock-out time (HH:MM)").pack(pady=(8,0))
        out_time_var = tk.StringVar(value=end_dt.strftime("%H:%M"))
        tk.Entry(win, textvariable=out_time_var, width=8, justify="center").pack()

        # ─ Lunch / Commute (mins)
        tk.Label(win, text="Lunch (min):").pack(pady=(10,0))
        lunch_var = tk.StringVar(value=str(target.get("lunch_minutes", user.get("lunch_minutes", 0))))
        tk.Entry(win, textvariable=lunch_var, width=6).pack()

        tk.Label(win, text="Commute (min):").pack(pady=(10,0))
        commute_var = tk.StringVar(value=str(target.get("commute_minutes", user.get("commute_minutes", 0))))
        tk.Entry(win, textvariable=commute_var, width=6).pack()

        def save_changes():
            try:
                ih, im = _parse_hhmm(in_time_var.get())
                oh, om = _parse_hhmm(out_time_var.get())
                lm = int(lunch_var.get());  cm = int(commute_var.get())
                if lm < 0 or cm < 0:
                    raise ValueError
            except Exception:
                return messagebox.showerror("Error", "Use HH:MM for times and non-negative integers for minutes.")

            # Rebuild datetimes from the *start day*, not the stale end day.
            start_date = start_dt.date()
            new_in_dt  = datetime.combine(start_date, datetime.min.time()).replace(hour=ih, minute=im)
            new_out_dt = datetime.combine(start_date, datetime.min.time()).replace(hour=oh, minute=om)

            # Smart overnight rule: if out <= in, it ends next day.
            if new_out_dt <= new_in_dt:
                new_out_dt += timedelta(days=1)

            # Optional guard-rail against zombie shifts (tweak hours to taste)
            MAX_SHIFT_HOURS = 20
            if (new_out_dt - new_in_dt) > timedelta(hours=MAX_SHIFT_HOURS):
                # Choose one behavior:
                # 1) clamp silently:
                # new_out_dt = new_in_dt + timedelta(hours=MAX_SHIFT_HOURS)
                # 2) or block with an error:
                return messagebox.showerror(
                    "Too long",
                    f"Edited shift would be {(new_out_dt - new_in_dt).seconds//3600}h. "
                    f"Please keep it under {MAX_SHIFT_HOURS} hours."
                )

            # Apply & save
            target["location"]        = loc_var.get()
            target["task"]            = task_var.get()
            target["clock_in"]        = new_in_dt.strftime("%Y-%m-%d %H:%M")
            target["clock_out"]       = new_out_dt.strftime("%Y-%m-%d %H:%M")
            target["lunch_minutes"]   = lm
            target["commute_minutes"] = cm
            target.pop("commute", None)

            save_employee_logs(user, logs)
            messagebox.showinfo("Saved", "Shift updated.")
            win.destroy()
            self.refresh_shifts()


        tk.Button(win, text="Save", width=12, height=2, bg="#b7f7b0", activebackground="#a3e6a1", command=save_changes).pack(pady=12)



    def end_shift(self, user_id, clock_in_time):
        user = next(u for u in self.users if u["id"] == user_id)
        logs = load_employee_logs(user)
        for log in logs:
            if log["clock_in"] == clock_in_time and not log.get("clock_out"):
                # Ask directly for lunch minutes (0 = no lunch)
                lunch_mins = simpledialog.askinteger(
                    "Lunch Duration",
                    f"Enter lunch duration in minutes (default {user.get('lunch_minutes',0)}):",
                    initialvalue=user.get("lunch_minutes", 0),
                    minvalue=0
                ) or 0

                log["lunch_minutes"] = lunch_mins
                log["clock_out"]     = now_trimmed()
                break

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
        """
        Sleek card for a single request, with status chip, tidy details, and actions.
        """
        # ── palette
        APP_BG     = self["bg"] if self["bg"] else "#f4f4f4"
        CARD_BG    = "#ffffff"
        BORDER     = "#d6dbe3"
        HEADER_BG  = "#e9f0f8"
        TEXT       = "#1f2937"
        MUTED      = "#6b7280"
        CHIP_BG    = {"pending": "#fde68a", "approved": "#d1fae5", "rejected": "#fee2e2"}
        CHIP_FG    = {"pending": "#92400e", "approved": "#065f46", "rejected": "#991b1b"}

        employee, employee_id = employee

        # helpers for file update
        orig_start = req.get("requested_start")
        orig_end   = req.get("requested_end")

        def update_request_file():
            with open(filepath, 'r', encoding='utf-8') as f:
                all_requests = json.load(f)
            for r in all_requests:
                if r.get("requested_start") == orig_start and r.get("requested_end") == orig_end:
                    r.update(req)
                    break
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(all_requests, f, indent=4)

        # header/status helpers
        def status_colors(st):
            st = (st or "pending").lower()
            return CHIP_BG.get(st, "#e5e7eb"), CHIP_FG.get(st, "#374151"), st

        # ── outer & card
        outer = tk.Frame(parent, bg=APP_BG)
        card  = tk.Frame(outer, bg=CARD_BG, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="both", expand=True)

        # header
        header = tk.Frame(card, bg=HEADER_BG)
        header.pack(fill="x")
        tk.Label(header, text=f"📝 {employee}", font=("Helvetica", 12, "bold"),
                bg=HEADER_BG, fg=TEXT, pady=8).pack(side="left", padx=10)

        chip_bg, chip_fg, curr_status = status_colors(req.get("status"))
        status_chip = tk.Label(header, text=curr_status.upper(), font=("Helvetica", 9, "bold"),
                            bg=chip_bg, fg=chip_fg, padx=8, pady=2)
        status_chip.pack(side="right", padx=10)

        # thin accent
        tk.Frame(card, height=2, bg="#3b82f6").pack(fill="x")

        # body
        body = tk.Frame(card, bg=CARD_BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # small util to make one line
        def line(label, value, italic=False):
            row = tk.Frame(body, bg=CARD_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{label}:", bg=CARD_BG, fg=MUTED,
                    font=("Helvetica", 10, "italic" if italic else "normal")).pack(side="left")
            tk.Label(row, text=value, bg=CARD_BG, fg=TEXT,
                    font=("Helvetica", 10, "italic" if italic else "normal")).pack(side="left", padx=(6,0))

        # fields
        line("Company",  company)
        line("Location", req.get("location", "N/A"))
        line("Task",     req.get("task", "N/A"))
        line("Start",    self.format_time_readable(req.get("requested_start")), italic=True)
        line("End",      self.format_time_readable(req.get("requested_end")),   italic=True)

        # chips row (commute/lunch)
        chips = tk.Frame(body, bg=CARD_BG); chips.pack(fill="x", pady=(6,2))
        def chip(txt):
            tk.Label(chips, text=txt, bg="#f3f4f6", fg="#374151",
                    font=("Helvetica", 9), padx=8, pady=2).pack(side="left", padx=(0,6))
        chip(f"Commute {req.get('commute_minutes', 0)}m")
        chip(f"Lunch {req.get('lunch_minutes', 0)}m")

        # reason (wrap)
        if req.get("reason"):
            reason = tk.Label(body, text=f"“{req['reason']}”", bg=CARD_BG, fg=MUTED,
                            font=("Helvetica", 10, "italic"), justify="left", wraplength=380)
            reason.pack(fill="x", pady=(4, 2))

        # actions row
        actions = tk.Frame(card, bg=CARD_BG); actions.pack(fill="x", padx=10, pady=10)

        # status dropdown
        tk.Label(actions, text="Set status:", bg=CARD_BG).pack(side="left", padx=(0,6))
        status_var = tk.StringVar(value=curr_status.capitalize())
        status_dd  = ttk.Combobox(actions, textvariable=status_var,
                                values=["Pending", "Approved", "Rejected"], state="readonly", width=12)
        status_dd.pack(side="left")

        # finalize/remove button (label depends on status)
        def refresh_status_ui():
            bg, fg, st = status_colors(status_var.get())
            status_chip.config(text=st.upper(), bg=bg, fg=fg)
            finalize_btn.config(text=("Finalize" if st == "approved" else "Remove" if st == "rejected" else "Finalize"))

        def on_status_change(_=None):
            req["status"] = status_var.get().lower()
            update_request_file()
            refresh_status_ui()

        status_dd.bind("<<ComboboxSelected>>", on_status_change)

        # Edit dialog (same logic you had)
        def edit_request():
            original_start = req["requested_start"]
            original_end   = req["requested_end"]
            edit_win = tk.Toplevel(self)
            edit_win.title("Edit Request")
            edit_win.geometry("400x470")

            tk.Label(edit_win, text="Location:").pack()
            location_var = tk.StringVar(value=req.get("location", ""))
            location_dropdown = ttk.Combobox(edit_win, textvariable=location_var, state="readonly")
            location_dropdown['values'] = sorted(self.task_config.keys())
            location_dropdown.pack()

            tk.Label(edit_win, text="Task:").pack()
            task_var = tk.StringVar(value=req.get("task", ""))
            task_dropdown = ttk.Combobox(edit_win, textvariable=task_var, state="readonly")
            task_dropdown.pack()

            tk.Label(edit_win, text="Start Time").pack()
            start_entry = DateAndTime(edit_win); start_entry.insert(0, req["requested_start"]); start_entry.pack()

            tk.Label(edit_win, text="End Time").pack()
            end_entry = DateAndTime(edit_win); end_entry.insert(0, req["requested_end"]); end_entry.pack()

            tk.Label(edit_win, text="Reason:").pack()
            reason_entry = tk.Entry(edit_win); reason_entry.insert(0, req.get("reason","")); reason_entry.pack(pady=(0,10))

            tk.Label(edit_win, text="Commute both ways (min):").pack()
            commute_var = tk.StringVar(value=str(req.get("commute_minutes", 0)))
            tk.Entry(edit_win, textvariable=commute_var).pack(pady=(0,8))

            tk.Label(edit_win, text="Lunch (min):").pack()
            lunch_var = tk.StringVar(value=str(req.get("lunch_minutes", 0)))
            tk.Entry(edit_win, textvariable=lunch_var).pack(pady=(0,12))

            def save_changes():
                try:
                    req["commute_minutes"] = int(commute_var.get())
                    req["lunch_minutes"]   = int(lunch_var.get())
                except ValueError:
                    return messagebox.showerror("Error", "Commute and Lunch must be integers.")

                req["location"]        = location_var.get()
                req["task"]            = task_var.get()
                req["requested_start"] = start_entry.get()
                req["requested_end"]   = end_entry.get()
                req["reason"]          = reason_entry.get()

                update_request_file()
                messagebox.showinfo("Updated", "Request updated successfully.")
                edit_win.destroy()
                # redraw the whole page to reflect changes
                self.show_handle_requests()

            tk.Button(edit_win, text="Save", command=save_changes).pack(pady=10)

        # finalize/remove behavior
        def handle_finalize():
            st = status_var.get().lower()
            if st == "approved":
                self.finalize_request(req, employee_id, company, filepath)
            elif st == "rejected":
                if messagebox.askyesno("Confirm Removal",
                                    f"Are you sure you want to delete the request from {employee}?"):
                    self.remove_request(req, filepath)
                    self.show_handle_requests()
            else:
                messagebox.showwarning("Pending", "Please approve or reject the request first.")

        finalize_btn = tk.Button(actions, text=("Finalize" if curr_status == "approved" else
                                                "Remove"   if curr_status == "rejected" else "Finalize"),
                                command=handle_finalize, font=("Helvetica", 10), padx=10, pady=2)
        finalize_btn.pack(side="right")

        tk.Button(actions, text="Edit", command=edit_request,
                font=("Helvetica", 10), padx=10, pady=2).pack(side="right", padx=(0,8))

        return outer

            
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
        # Prefer location/company layout if it exists or location is provided
        base_dir_direct = Path(COMPANY_FOLDER) / company
        base_dir_loc    = Path(COMPANY_FOLDER) / req.get("location", "") / company
        if base_dir_loc.exists() or (req.get("location") and not base_dir_direct.exists()):
            base_dir = base_dir_loc
        else:
            base_dir = base_dir_direct
        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(base_dir / f"{employee}.json")


        new_start = parse_dt(req["requested_start"])
        new_end = parse_dt(req["requested_end"])
        if not new_start or not new_end:
            messagebox.showerror("Error", "Invalid date format in request.")
            return

        new_entry = {
            "id": str(uuid.uuid4()),
            "task": req["task"],
            "location": req["location"],
            "clock_in": req["requested_start"],
            "clock_out": req["requested_end"],
            "lunch_minutes": req["lunch_minutes"],
            "commute_minutes": req["commute_minutes"]
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
            all_requests = [
                r for r in all_requests
                if r.get("requested_start") != req.get("requested_start") or r.get("requested_end") != req.get("requested_end")
            ]
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
        self.users = load_users()

        # ─────────────── left: listbox ───────────────
        listbox = tk.Listbox(parent, width=30)
        for u in self.users:
            listbox.insert("end", f"{u['id']}: {u['name']}")
        listbox.grid(row=0, column=0, rowspan=6, sticky="ns", padx=5, pady=5)

        # ─────────────── right: form ───────────────
        # ID
        id_var = str(uuid.uuid4())

        # Name
        tk.Label(parent, text="Name").grid(row=1, column=1, sticky="w")
        name_var = tk.StringVar()
        tk.Entry(parent, textvariable=name_var).grid(row=1, column=2, sticky="ew")

        # Company
        tk.Label(parent, text="Company").grid(row=2, column=1, sticky="w")
        comp_var = tk.StringVar()
        comp_choices = sorted({u["company"] for u in self.users} | set(self.get_company_names()))
        ttk.Combobox(parent, textvariable=comp_var, values=comp_choices, state="readonly")\
        .grid(row=2, column=2, sticky="ew")

        # PIN
        tk.Label(parent, text="PIN").grid(row=3, column=1, sticky="w")
        pin_var = tk.StringVar()
        tk.Entry(parent, textvariable=pin_var).grid(row=3, column=2, sticky="ew")

        # Commute (min)
        tk.Label(parent, text="Commute (min)").grid(row=4, column=1, sticky="w")
        commute_var = tk.StringVar()
        tk.Entry(parent, textvariable=commute_var).grid(row=4, column=2, sticky="ew")

        # Lunch (min)
        tk.Label(parent, text="Lunch (min)").grid(row=5, column=1, sticky="w")
        lunch_var = tk.StringVar()
        tk.Entry(parent, textvariable=lunch_var).grid(row=5, column=2, sticky="ew")

        # ─────────────── button bar ───────────────
        btn_frame = tk.Frame(parent)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=10)

        def on_select(evt):
            idx = listbox.curselection()[0]
            user = self.users[idx]
            id_var = user["id"]
            name_var.set(user["name"])
            comp_var.set(user["company"])
            pin_var.set(user["pin"])
            commute_var.set(str(user.get("commute_minutes", 0)))
            lunch_var.set(str(user.get("lunch_minutes", 0)))

        listbox.bind("<<ListboxSelect>>", on_select)

        def save_user():
            # basic presence check
            if not (name_var.get() and comp_var.get() and pin_var.get()
                    and commute_var.get() and lunch_var.get()):
                return messagebox.showerror("Error", "All fields required.")

            # numeric validation
            try:
                cm = int(commute_var.get())
                lm = int(lunch_var.get())
                if cm < 0 or lm < 0:
                    raise ValueError
            except ValueError:
                return messagebox.showerror("Error", "Commute and Lunch must be non-negative integers.")

            new = {
                "id":               id_var,
                "name":             name_var.get(),
                "company":          comp_var.get(),
                "pin":              pin_var.get(),
                "commute_minutes":  cm,
                "lunch_minutes":    lm,
                # lunch_taken is per-shift; default to False
                "lunch_taken":      False
            }

            # replace or append
            for i,u in enumerate(self.users):
                if u["id"] == new["id"]:
                    self.users[i] = new
                    break
            else:
                self.users.append(new)

            save_users(self.users)
            messagebox.showinfo("Saved", f"User {new['id']} saved.")
            self.show_edit_database()

        def delete_user():
            uid = id_var
            self.users = [u for u in self.users if u["id"] != uid]
            save_users(self.users)
            messagebox.showinfo("Deleted", f"User {uid} removed.")
            self.show_edit_database()

        tk.Button(btn_frame, text="Save User",   command=save_user).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Delete User", command=delete_user).pack(side="left", padx=5)


    def _build_styles(self):
        """Light modern styling for headings and filter widgets."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        self.APP_BG   = self["bg"] if self["bg"] else "#f4f4f4"
        self.PILL_BG  = "#eef3fb"
        self.BORDER   = "#d6dbe3"
        self.TEXT     = "#1f2937"
        self.MUTED    = "#556987"
        self.ACCENT   = "#2d6cdf"
        self.NAV_BG   = "#e9f0f8"   # header background
        self.NAV_TEXT = self.TEXT

        # Header frame style
        style.configure("NavBar.TFrame", background=self.NAV_BG)

        # Base nav button
        style.configure(
            "Nav.TButton",
            font=("Helvetica", 11, "bold"),
            padding=(14, 8),
            relief="flat",
            borderwidth=0
        )
        # Hover/pressed feedback
        style.map(
            "Nav.TButton",
            foreground=[("active", self.NAV_TEXT)],
        )

        # Active tab: accent text (underline handled in layout)
        style.configure(
            "Nav.Active.TButton",
            font=("Helvetica", 11, "bold"),
            padding=(14, 8),
            relief="flat",
            borderwidth=0,
            foreground=self.ACCENT
        )

        style.configure("Heading.TLabel",
            font=("Helvetica", 16, "bold"),
            foreground=self.TEXT,
            background=self.APP_BG,
        )
        style.configure("FilterLabel.TLabel",
            font=("Helvetica", 9, "bold"),
            foreground=self.MUTED,
            background=self.PILL_BG,
        )
        # ttk on Windows ignores some bg props, but padding/relief still help
        style.configure("Filter.TCombobox",
            padding=6,
            relief="flat",
        )
        style.map("Filter.TCombobox",
            foreground=[("disabled", "#9aa5b1")],
        )
        # Treeview styling for dashboard tables
        style.configure("Dashboard.Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            rowheight=28,
            font=("Helvetica", 10),
            borderwidth=0
        )
        style.configure("Dashboard.Treeview.Heading",
            font=("Helvetica", 10, "bold"),
        )
        style.map("Dashboard.Treeview",
            background=[("selected", "#e5f0ff")],
            foreground=[("selected", "#0f172a")],
        )
        style.layout("Dashboard.Treeview", style.layout("Treeview"))  # keep default layout
        style.layout("Dashboard.Treeview.Heading", style.layout("Treeview.Heading"))


        # Cards toolbars / search / tiny buttons
        style.configure("CardToolbar.TFrame", background="#ffffff")

        style.configure("Search.TEntry", padding=6, relief="flat")

        style.configure("Ghost.TButton",
            padding=(10, 4),
            font=("Helvetica", 10),
            relief="flat",
            borderwidth=0,
        )
        style.map("Ghost.TButton",
            background=[("active", "#f3f4f6")],
        )

    def _searchbar(self, parent, var, on_change):
        """Tiny search row with a magnifying-glass + Entry. Calls on_change on every keystroke."""
        row = ttk.Frame(parent, style="CardToolbar.TFrame")
        row.pack(fill="x")
        tk.Label(row, text="🔎", bg="#ffffff").pack(side="left", padx=(2, 6))
        ent = ttk.Entry(row, textvariable=var, style="Search.TEntry")
        ent.pack(side="left", fill="x", expand=True)
        ent.bind("<KeyRelease>", on_change)

    def _crud_bar(self, parent, add, edit, delete):
        """Minimal Add/Edit/Delete row."""
        bar = ttk.Frame(parent, style="CardToolbar.TFrame")
        bar.pack(fill="x", pady=(4, 0))
        ttk.Button(bar, text="➕ Add",  style="Ghost.TButton", command=add).pack(side="left", padx=4)
        ttk.Button(bar, text="✏️ Edit", style="Ghost.TButton", command=edit).pack(side="left", padx=4)
        ttk.Button(bar, text="🗑 Delete", style="Ghost.TButton", command=delete).pack(side="left", padx=4)


    def _toolbar(self, parent):
        """
        A horizontal bar with left area for chips and right area for action buttons.
        Returns (left_frame, right_frame).
        """
        bar = tk.Frame(parent, bg=self.APP_BG)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        left = tk.Frame(bar, bg=self.APP_BG)
        left.pack(side="left", fill="x", expand=True)
        right = tk.Frame(bar, bg=self.APP_BG)
        right.pack(side="right")
        return left, right
    
    def on_user_company_selected(self, event=None):
        comp = self.user_company_var.get()
        self.user_lb.delete(0, "end")
        self._user_list_ids = []

        for u in self.users:
            if comp == "Any" or u.get("company") == comp:
                self.user_lb.insert("end", u["name"])
                self._user_list_ids.append(u["id"])

        # correct attribute name:
        if hasattr(self, "add_user_btn"):
            self.add_user_btn.configure(state=("disabled" if comp == "Any" else "normal"))



    def _scrolled_listbox(self, parent, *, height=12):
        """Compact listbox + vertical scrollbar that doesn't grow vertically."""
        wrap = tk.Frame(parent, bg="#ffffff")
        wrap.pack(fill="x", padx=2, pady=(4, 6))  # no expand, only width
        lb = tk.Listbox(wrap, exportselection=False, height=height)
        lb.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=lb.yview)
        sb.pack(side="right", fill="y")
        lb.configure(yscrollcommand=sb.set)
        return lb


    def build_hierarchical_db_tab(self, parent):
        self.users = load_users()
        self.task_config = load_task_config()

        self._user_list_ids = []   # listbox index -> user id

        # Title + breadcrumb
        ttk.Label(parent, text="Database Manager", style="Heading.TLabel") \
            .pack(anchor="w", padx=12, pady=(12, 6))
        self.breadcrumb_var = tk.StringVar(value="— Configure Locations, Companies, Tasks and Users here —")
        ttk.Label(parent, textvariable=self.breadcrumb_var, style="FilterLabel.TLabel") \
            .pack(anchor="w", padx=12, pady=(0, 6))

        # Compact grid: horizontal only, anchored to top
        grid = tk.Frame(parent, bg=self.APP_BG)
        grid.pack(fill="x", anchor="n", padx=10, pady=10)       # <- no vertical expand
        for i in range(4):
            grid.grid_columnconfigure(i, weight=1, uniform="col")
        grid.grid_rowconfigure(0, weight=0)                     # <- don't stretch vertically

        # ── Locations ──────────────────────────────────────────────────────
        outer_l, body_l = self._section_card(grid, "Locations")
        outer_l.grid(row=0, column=0, sticky="new", padx=6, pady=6)   # <- only N/E/W
        self.loc_query = tk.StringVar()
        self._searchbar(body_l, self.loc_query, lambda *_: self.refresh_locations())
        self.loc_lb = self._scrolled_listbox(body_l, height=12)       # <- compact with scrollbar
        self.loc_lb.bind("<<ListboxSelect>>", self.on_loc_selected)
        self._crud_bar(body_l, add=self.add_location, edit=self.edit_location, delete=self.delete_location)

        # ── Companies ─────────────────────────────────────────────────────
        outer_c, body_c = self._section_card(grid, "Companies")
        outer_c.grid(row=0, column=1, sticky="new", padx=6, pady=6)
        self.comp_query = tk.StringVar()
        self._searchbar(body_c, self.comp_query, lambda *_: self.refresh_companies())
        self.comp_lb = self._scrolled_listbox(body_c, height=12)
        self.comp_lb.bind("<<ListboxSelect>>", self.on_comp_selected)
        self._crud_bar(body_c, add=self.add_company, edit=self.edit_company, delete=self.delete_company)

        # ── Tasks ──────────────────────────────────────────────────────────
        outer_t, body_t = self._section_card(grid, "Tasks")
        outer_t.grid(row=0, column=2, sticky="new", padx=6, pady=6)
        self.task_query = tk.StringVar()
        self._searchbar(body_t, self.task_query, lambda *_: self.refresh_tasks())
        self.task_lb = self._scrolled_listbox(body_t, height=12)
        self._crud_bar(body_t, add=self.add_task, edit=self.edit_task, delete=self.delete_task)

        # ── Users ──────────────────────────────────────────────────────────
        outer_u, body_u = self._section_card(grid, "Users")
        outer_u.grid(row=0, column=3, sticky="new", padx=6, pady=6)

        top = ttk.Frame(body_u, style="CardToolbar.TFrame")
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Company (or Any)", style="FilterLabel.TLabel") \
            .pack(side="left", padx=(0, 6))

        self.user_company_var = tk.StringVar(value="Any")
        self.user_company_combo = ttk.Combobox(
            top, textvariable=self.user_company_var, state="readonly", width=28
        )
        self.user_company_combo.pack(side="left", fill="x", expand=True)

        # Populate: 'Any' (filter only) + all real companies
        self.user_company_combo["values"] = ["Any"] + self._all_companies()
        self.user_company_combo.bind("<<ComboboxSelected>>", self.on_user_company_selected)

        # Users list + buttons
        self.user_lb = self._scrolled_listbox(body_u, height=12)

        btnf = ttk.Frame(body_u, style="CardToolbar.TFrame")
        btnf.pack(fill="x")
        self.add_user_btn = ttk.Button(btnf, text="Add User",
                                    style="Ghost.TButton", command=self.add_user)
        self.add_user_btn.pack(side="left", padx=4)
        ttk.Button(btnf, text="Edit User",   style="Ghost.TButton",
                command=self.edit_user).pack(side="left", padx=4)
        ttk.Button(btnf, text="Delete User", style="Ghost.TButton",
                command=self.delete_user).pack(side="left", padx=4)

        # Initial load
        self.refresh_locations()
        self.refresh_companies()  # <-- populate Companies list immediately (global)

        # After self.refresh_locations(); self.refresh_companies()
        all_comps = self._all_companies()
        self.user_company_combo["values"] = ["Any"] + all_comps
        self.user_company_var.set("Any")
        self.on_user_company_selected()




    # ────────────────────────────────────────────────────────────────────
    # Location‐level CRUD
    # ────────────────────────────────────────────────────────────────────

    def refresh_locations(self):
        self.task_config = load_task_config()
        q = (self.loc_query.get().lower() if hasattr(self, "loc_query") else "")
        self.loc_lb.delete(0, "end")
        for loc in sorted(self.task_config):
            if q and q not in loc.lower():
                continue
            self.loc_lb.insert("end", loc)
        # Clear downstream lists
        if hasattr(self, "comp_lb"): self.comp_lb.delete(0, "end")
        if hasattr(self, "task_lb"): self.task_lb.delete(0, "end")

    def add_location(self):
        """Popup to create a new location."""
        def on_ok():
            new_loc = entry.get().strip()
            if not new_loc:
                return messagebox.showerror("Error", "Name cannot be empty.")
            if new_loc in self.task_config:
                return messagebox.showerror("Error", "That location already exists.")

            # Create + seed with all companies (safe even if none yet)
            self.task_config.setdefault(new_loc, {})
            self._sync_all_companies_to_location(new_loc)

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

            # ⬇️ rename + seed companies at the new location + save
            self.task_config[new] = self.task_config.pop(old)
            self._sync_all_companies_to_location(new)
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

    # ────────────────────────────────────────────────────────────────────
    # Company‐level CRUD (must come after the location methods)
    # ────────────────────────────────────────────────────────────────────

    def refresh_companies(self):
        self.task_config = load_task_config()
        if hasattr(self, "comp_lb"): self.comp_lb.delete(0, "end")
        if hasattr(self, "task_lb"): self.task_lb.delete(0, "end")

        q = (self.comp_query.get().lower() if hasattr(self, "comp_query") else "")
        for comp in self._all_companies():
            if q and q not in comp.lower():
                continue
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
                return messagebox.showerror("Error", "Name cannot be empty.")
            if new in self.task_config[loc]:
                return messagebox.showerror("Error", "That company already exists here.")

            # Add at the current location
            self.task_config.setdefault(loc, {}).setdefault(new, [])

            # And mirror to every other location
            self._sync_company_to_all_locations(new)

            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_companies()



        dlg = tk.Toplevel(self)
        dlg.title(f"Add Company in '{loc}'")
        tk.Label(dlg, text="Company Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.pack(padx=10, pady=5)
        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def edit_company(self):
        comp_sel = self.comp_lb.curselection()
        if not comp_sel:
            messagebox.showerror("Error", "Select a company first.")
            return
        old = self.comp_lb.get(comp_sel)

        dlg = tk.Toplevel(self)
        dlg.title(f"Rename Company '{old}'")
        tk.Label(dlg, text="New Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.insert(0, old); entry.pack(padx=10, pady=5)

        def on_ok():
            new = entry.get().strip()
            if not new or new == old:
                dlg.destroy(); return

            # Rename across ALL locations in task_config, merging if 'new' exists
            for loc, cmap in self.task_config.items():
                if old in cmap:
                    if new in cmap:
                        existing = {(t["name"] if isinstance(t, dict) else t) for t in cmap[new]}
                        for t in cmap[old]:
                            nm = (t["name"] if isinstance(t, dict) else t)
                            if nm not in existing:
                                cmap[new].append(t)
                        del cmap[old]
                    else:
                        cmap[new] = cmap.pop(old)

            save_task_config(self.task_config)

            # Update users.json
            changed = False
            for u in self.users:
                if u.get("company") == old:
                    u["company"] = new
                    changed = True
            if changed:
                save_users(self.users)

            # Rename folders on disk (logs + requests)
            self._rename_company_on_disk(old, new)

            dlg.destroy()
            self.refresh_companies()
            self.user_company_combo["values"] = ["Any"] + self._all_companies()
            if self.user_company_var.get() == old:
                self.user_company_var.set(new)
            self.on_user_company_selected()

            self.current_comp = new
            locs = self.locations_for_company(new)
            if locs:
                self.current_loc = locs[0]
                self._select_location_in_listbox(self.current_loc)
            self.refresh_tasks()

        tk.Button(dlg, text="OK", command=on_ok).pack(pady=10)

    def delete_company(self):
        comp_sel = self.comp_lb.curselection()
        if not comp_sel:
            return messagebox.showerror("Error", "Select a company to delete.")
        comp = self.comp_lb.get(comp_sel)

        if not messagebox.askyesno("Confirm",
                                f"Delete company '{comp}' from ALL locations and remove its data on disk?"):
            return

        # Remove from task_config across all locations
        changed_cfg = False
        for _, cmap in self.task_config.items():
            if comp in cmap:
                del cmap[comp]
                changed_cfg = True
        if changed_cfg:
            save_task_config(self.task_config)

        # Optionally unassign users
        had_users = any(u.get("company") == comp for u in self.users)
        if had_users and messagebox.askyesno("Also unassign users?",
                                            f"Unassign all users in '{comp}' so the company disappears everywhere?"):
            for u in self.users:
                if u.get("company") == comp:
                    u["company"] = "Unassigned"
            save_users(self.users)

        # Remove folders on disk (logs + requests)
        self._delete_company_on_disk(comp, archive=False)  # set True to archive instead

        # UI refresh
        self.refresh_companies()
        self.user_company_combo["values"] = ["Any"] + self._all_companies()
        if self.user_company_var.get() == comp:
            self.user_company_var.set("Any")
        self.on_user_company_selected()

        if getattr(self, "current_comp", None) == comp:
            self.current_comp = None
        self.refresh_tasks()



    # ────────────────────────────────────────────────────────────────────
    # Task‐level CRUD (replace your existing methods with these)
    # ────────────────────────────────────────────────────────────────────

    def refresh_tasks(self):
        self.task_lb.delete(0, "end")
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        if not (loc and comp):
            return  # show nothing until both are selected

        lst = self.task_config.get(loc, {}).get(comp, [])
        q = (self.task_query.get().lower() if hasattr(self, "task_query") else "")
        for item in lst:
            name = item["name"] if isinstance(item, dict) else str(item)
            if q and q not in name.lower():
                continue
            mark = " ✓" if isinstance(item, dict) and item.get("completed", False) else ""
            self.task_lb.insert("end", f"{name}{mark}")



    def add_task(self):
        """Popup to create a new task under the selected company."""
        loc  = getattr(self, "current_loc", None)
        comp = getattr(self, "current_comp", None)
        if not (loc and comp):
            messagebox.showerror("Error", "Select a company first.")
            return

        def on_ok():
            new = entry.get().strip()
            if not new:
                return messagebox.showerror("Error", "Task cannot be empty.")

            # Ensure the location/company exist and fetch the list
            lst = self.task_config.setdefault(loc, {}).setdefault(comp, [])

            # Check duplicates (supports both dict and legacy string items)
            existing = { (it["name"] if isinstance(it, dict) else str(it)) for it in lst }
            if new in existing:
                return messagebox.showerror("Error", "That task already exists.")

            # Append new task object
            lst.append({
                "id": str(uuid.uuid4()),
                "name": new,
                "completed": False
            })
            save_task_config(self.task_config)
            dlg.destroy()
            self.refresh_tasks()

        dlg = tk.Toplevel(self)
        dlg.title(f"Add Task in '{comp}' @ '{loc}'")
        tk.Label(dlg, text="Task Name:").pack(padx=10, pady=5)
        entry = tk.Entry(dlg); entry.pack(padx=10, pady=5)
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
                "id": orig["id"],
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

    def add_user(self):
        """Popup to add a new user under the selected company."""
        comp = self.user_company_var.get()
        if not comp or comp == "Any":
            messagebox.showerror(
                "Pick a company",
                "Select a specific company in the 'Company (or Any)' dropdown before adding a user."
            )
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Add user to {comp}")

        id_var = str(uuid.uuid4())

        tk.Label(dlg, text="Name:").grid(row=1, column=0)
        name_var = tk.StringVar()
        tk.Entry(dlg, textvariable=name_var).grid(row=1, column=1)

        tk.Label(dlg, text="PIN:").grid(row=2, column=0)
        pin_var = tk.StringVar()
        tk.Entry(dlg, textvariable=pin_var).grid(row=2, column=1)

        # — New commute field —
        tk.Label(dlg, text="Commute (min):").grid(row=3, column=0)
        commute_var = tk.StringVar(value="25")
        tk.Entry(dlg, textvariable=commute_var).grid(row=3, column=1)

        # — New lunch field —
        tk.Label(dlg, text="Lunch (min):").grid(row=4, column=0)
        lunch_var = tk.StringVar(value="30")   
        tk.Entry(dlg, textvariable=lunch_var).grid(row=4, column=1)

        def on_ok():
            uid     = id_var
            name    = name_var.get().strip()
            pin     = pin_var.get().strip()
            commute = commute_var.get().strip()

            # basic presence check
            if not (name and pin and commute):
                return messagebox.showerror("Error", "All fields required.")

            # numeric check
            try:
                cm = int(commute)
                if cm < 0:
                    raise ValueError
            except ValueError:
                return messagebox.showerror("Error", "Commute must be a non-negative integer.")

            if any(u["id"] == uid for u in self.users):
                return messagebox.showerror("Error", "That ID already exists.")

            new = {
                "id":               uid,
                "name":             name,
                "company":          comp,
                "pin":              pin,
                "commute_minutes":  cm,
                "lunch_minutes":    0,  
            }
            self.users.append(new)
            save_users(self.users)
            dlg.destroy()
            self.on_user_company_selected()

        # finally, add an OK button that calls on_ok:
        tk.Button(dlg, text="OK", command=on_ok) \
            .grid(row=5, column=0, columnspan=2, pady=10)

            



    def edit_user(self):
        """Popup to edit the selected user’s name, PIN, commute—and now default lunch time."""
    def edit_user(self):
        sel = self.user_lb.curselection()
        if not sel:
            return messagebox.showerror("Error", "Select a user first.")
        idx = sel[0]
        if idx >= len(self._user_list_ids):
            return messagebox.showerror("Error", "Invalid selection.")

        uid  = self._user_list_ids[idx]
        user = next((u for u in self.users if u["id"] == uid), None)
        if not user:
            return messagebox.showerror("Error", "User not found.")
        # ... keep the rest of the dialog unchanged


        dlg = tk.Toplevel(self)
        dlg.title(f"Edit user '{user['name']}'")

        # — Name —
        tk.Label(dlg, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        name_var = tk.StringVar(value=user["name"])
        tk.Entry(dlg, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)

        # — PIN —
        tk.Label(dlg, text="PIN:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        pin_var  = tk.StringVar(value=user["pin"])
        tk.Entry(dlg, textvariable=pin_var).grid(row=1, column=1, padx=5, pady=5)

        # — Commute (min) —
        tk.Label(dlg, text="Commute (min):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        commute_var = tk.StringVar(value=str(user.get("commute_minutes", 0)))
        tk.Entry(dlg, textvariable=commute_var).grid(row=2, column=1, padx=5, pady=5)

        # — Lunch (min) —
        tk.Label(dlg, text="Lunch (min):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        lunch_var = tk.StringVar(value=str(user.get("lunch_minutes", 0)))
        tk.Entry(dlg, textvariable=lunch_var).grid(row=3, column=1, padx=5, pady=5)

        def on_ok():
            new_name    = name_var.get().strip()
            new_pin     = pin_var.get().strip()
            new_commute = commute_var.get().strip()
            new_lunch   = lunch_var.get().strip()

            # require all fields
            if not (new_name and new_pin and new_commute and new_lunch):
                return messagebox.showerror("Error", "All fields required.")

            # validate commute and lunch are non-negative integers
            try:
                cm = int(new_commute)
                lm = int(new_lunch)
                if cm < 0 or lm < 0:
                    raise ValueError
            except ValueError:
                return messagebox.showerror("Error", "Commute and Lunch must be non-negative integers.")

            # apply changes
            user["name"]            = new_name
            user["pin"]             = new_pin
            user["commute_minutes"] = cm
            user["lunch_minutes"]   = lm

            save_users(self.users)
            dlg.destroy()
            # refresh list for the current company filter
            self.on_user_company_selected()

        tk.Button(dlg, text="OK", command=on_ok)\
          .grid(row=4, column=0, columnspan=2, pady=10)
        

    def delete_user(self):
        sel = self.user_lb.curselection()
        if not sel:
            return messagebox.showerror("Error", "Select a user first.")
        idx = sel[0]
        if idx >= len(self._user_list_ids):
            return messagebox.showerror("Error", "Invalid selection.")

        uid  = self._user_list_ids[idx]
        user = next((u for u in self.users if u["id"] == uid), None)
        if not user:
            return messagebox.showerror("Error", "User not found.")

        if not messagebox.askyesno(
            "Confirm Deletion",
            f"Delete user '{user['name']}' from {user.get('company','')}?"
        ):
            return

        # remove from users.json
        self.users = [u for u in self.users if u["id"] != uid]
        save_users(self.users)

        # optional: remove this user's logs (both layouts)
        try:
            comp = user.get("company")
            if comp:
                p = Path(COMPANY_FOLDER) / comp / f"{uid}.json"
                if p.exists(): p.unlink()
                for loc_dir in Path(COMPANY_FOLDER).iterdir():
                    if loc_dir.is_dir():
                        p2 = loc_dir / comp / f"{uid}.json"
                        if p2.exists(): p2.unlink()
        except Exception:
            pass

        self.on_user_company_selected()
        messagebox.showinfo("Deleted", f"User '{user['name']}' removed.")



if __name__ == "__main__":
    print("hello from admin_view.py")
    app = AdminApp()
    app.mainloop()
