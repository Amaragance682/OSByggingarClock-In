import tkinter as tk
from datetime import datetime
from tkinter import ttk
from tkcalendar import Calendar
from datetime import date
from tktimepicker import SpinTimePickerOld, constants

class DateEntry(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.is_expanded = False

        self.date_var = tk.StringVar(value=date.today())

        self.expand_button = tk.Entry(self, textvariable=self.date_var)
        self.expand_button.pack()
        self.expand_button.bind("<ButtonPress-1>", self._toggle_expanded)

        self.popup = tk.Toplevel(self)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.popup.bind("<FocusOut>", self._handle_lost_focus)

        self.floating_entry = Calendar(self.popup, textvariable=self.date_var, date_pattern="y-mm-dd")
        self.floating_entry.pack()

    def _handle_lost_focus(self, event):
        focused_widget = self.focus_get()
        if focused_widget and str(self.popup) in str(focused_widget):
            return
        self._collapse_calendar()

    def _show_calendar(self, event=None):
        self.popup.geometry(f"+{self.winfo_rootx()}+{self.winfo_rooty() + self.expand_button.winfo_height()}")
        self.popup.deiconify()
        self.is_expanded = True
        self.floating_entry.focus_set()

    def _collapse_calendar(self, event=None):
        self.popup.withdraw()
        self.is_expanded = False

    def _toggle_expanded(self, event=None):
        if self.is_expanded:
            self._collapse_calendar()
        else:
            self._show_calendar()

    def get_date(self):
        return self.date_var.get()

    def set_date(self, date):
        self.floating_entry.selection_set(date)

class DateAndTime(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.container = tk.Frame(self)
        self.container.pack()
        self.date = DateEntry(self.container)
        self.date.pack(side="left")
        self.time = SpinTimePickerOld(self.container)
        self.time.addAll(constants.HOURS24)
        self.time.pack(side="right")

    def get(self):
        hours = self.time.hours24()
        if len(str(hours)) == 1:
            hours = f"0{hours}"
        minutes = self.time.minutes()
        if len(str(minutes)) == 1:
            minutes = f"0{minutes}"
        s = f"{hours}:{minutes}"
        return f"{self.date.get_date()}T{s}"

    def insert(self, _, iso):
        dt = datetime.fromisoformat(iso)
        self.date.set_date(dt)
        self.time._24HrsTime.delete(0, "end")
        self.time._24HrsTime.insert(0, f"{dt.hour:02}")
        self.time._minutes.delete(0, "end")
        self.time._minutes.insert(0, f"{dt.minute:02}")

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("300x200")

    cont = tk.Frame(root)
    cont.pack()

    dateandtime = DateAndTime(cont)
    dateandtime.pack()
    dateandtime.insert(0, "2024-08-12T16:30")

    button = tk.Button(cont, text="get time", command=lambda: print(dateandtime.get()))
    button.pack()

    root.mainloop()
