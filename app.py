import tkinter as tk
from test import DateAndTime
from tktimepicker import SpinTimePickerOld, constants
import os
from test import DateEntry
import json
from datetime import datetime
from tkinter import messagebox, ttk
from PIL import Image, ImageTk
from utils import (
    load_users,
    get_user_by_pin,
    load_employee_logs,
    save_employee_logs,
    create_shift_entry,
    close_last_shift,
    is_clocked_in,
    format_time,
    format_duration,
    load_task_config,
    get_locations_for_user,
    get_tasks_for_user,
)

# !!!CHANGE THIS TO CURRENT LOCATION OF THE LAPTOP!!!
# ==================================================#
LOCATION = "Reykjavik"
# ==================================================#

users = load_users()

class ShiftClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.request_frame = RequestFormFrame(self)
        self.configure(bg="#e6f0fa")  # light blueish background
        self.title("Shift Clock System")
        self.geometry("500x800")

        self.user = None

        self.login_frame = LoginFrame(self)
        self.task_frame = TaskFrame(self)

        self.login_frame.pack()
    
    def show_request_form(self):
        self.task_frame.pack_forget()
        self.request_frame.pack()
        self.request_frame.reset()

    def back_to_task_view(self):
        self.request_frame.pack_forget()
        self.task_frame.pack()

    def switch_to_task(self, user):
        self.user = user
        self.login_frame.pack_forget()
        self.task_frame.pack()
        self.task_frame.reset()

    def clock_out_and_return(self):
        logs = load_employee_logs(self.user)
        closed = close_last_shift(logs)
        save_employee_logs(self.user, logs)
        msg = format_duration(closed["clock_in"], closed["clock_out"]) if closed else "Not clocked in."
        messagebox.showinfo("Clocked Out", msg)
        self.task_frame.pack_forget()
        self.login_frame.pack()

    def log_out_without_clocking_out(self):
        self.task_frame.pack_forget()
        self.login_frame.pack()


class LoginFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        try:
            image = Image.open("logo.png")
            image = image.resize((500,300))  
            self.photo = ImageTk.PhotoImage(image)
            self.image_label = tk.Label(self, image=self.photo)
            self.image_label.pack(pady=10)
        except Exception as e:
            print(f"Error loading image: {e}")

        tk.Label(self, text="Enter PIN", font=("Helvetica", 16)).pack(pady=20)

        self.pin_var = tk.StringVar()
        self.entry = tk.Entry(self, textvariable=self.pin_var, font=("Helvetica", 14), show="*", justify="center")
        self.entry.pack(pady=10)
        self.entry.focus()
        self.entry.bind("<Return>", self.check_pin)

        tk.Button(self, text="Login", font=("Helvetica", 14), command=self.check_pin).pack(pady=10)

    def check_pin(self, event=None):
        pin = self.pin_var.get()
        user = get_user_by_pin(pin, users)
        if user:
            self.pin_var.set("")
            self.master.switch_to_task(user)
        else:
            messagebox.showerror("Error", "Invalid PIN")

class RequestFormFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        
        self.task_config = load_task_config()

        self.reason_text = tk.Text(self, height=5, width=40)
        self.reason_text.pack(pady=10)

        #self.start_entry = tk.Entry(self)
        #self.start_entry.insert(0, "2025-06-18 09:00")  # friendlier format
        #self.start_entry.pack(pady=5)

        self.start_entry = DateAndTime(self)
        self.start_entry.pack()

        self.end_entry = DateAndTime(self)
        self.end_entry.pack()

        # Dropdowns
        self.task_var = tk.StringVar()

        self.task_dropdown = ttk.Combobox(self, textvariable=self.task_var, state="disabled", font=("Helvetica", 12))

        self.task_dropdown.pack(pady=5)

        tk.Button(self, text="Submit Request", command=self.submit_request).pack(pady=10)
        tk.Button(self, text="Back", command=self.master.back_to_task_view).pack()

    def update_task_dropdown(self, event=None):
        user = self.master.user
        tasks = get_tasks_for_user(user, LOCATION, self.task_config)

        self.task_var.set("")
        self.task_dropdown.set("")
        self.task_dropdown["values"] = tasks

        if tasks:
            self.task_dropdown.config(state="readonly")
        else:
            self.task_dropdown.config(state="disabled")
            

    # LOADS TASKS, RESETS DROPDOWNS, CLEARS REASON TEXT, START AND END ENTRIES AND SHIFT EDIT REQUEST SCREEN
    def reset(self):
        user = self.master.user
        tasks = get_tasks_for_user(user, LOCATION, self.task_config)

        self.task_dropdown["values"] = tasks
        self.task_var.set("")
        self.task_dropdown.set("")

        if tasks:
            self.task_dropdown.config(state="readonly")
        else:
            self.task_dropdown.config(state="disabled")

    def submit_request(self):
        user = self.master.user
        try:
            requested_start = datetime.strptime(self.start_entry.get_iso(), "%Y-%m-%d %H:%M").isoformat()
            requested_end = datetime.strptime(self.end_entry.get_iso(), "%Y-%m-%d %H:%M").isoformat()
        except ValueError:
            messagebox.showerror("Invalid Time Format", "Please use YYYY-MM-DD HH:MM format for both start and end.")
            return
        
        data = {
            "task": self.task_var.get(),
            "location": LOCATION,
            "company": user["company"],
            "requested_start": requested_start,
            "requested_end": requested_end,
            "reason": self.reason_text.get("1.0", "end").strip(),
            "status": "pending"
        }

        # Save under 'requests' folder
        path = os.path.join("requests", user["company"], f"{user['id']}_requests.json")
        folder = os.path.dirname(path)
        if not os.path.exists(folder):
            os.makedirs(folder)
        
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                requests = json.load(f)
        else:
            requests = []
        
        requests.append(data)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(requests, f, indent=4)
        
        messagebox.showinfo("Request Submitted", "Your request has been sent.")
        self.master.back_to_task_view()




class TaskFrame(tk.Frame):
    def __init__(self, master):

        super().__init__(master)


        # clock buttons
        self.clock_in_img = ImageTk.PhotoImage(Image.open("clockIn.png").resize((120, 120)))
        self.clock_out_img = ImageTk.PhotoImage(Image.open("stopButton.jpg").resize((120, 120)))

        # Container box
        self.container = tk.Frame(self, bg="#f0f0f0", bd=0, relief="flat", padx=20, pady=20)
        self.container.pack(expand=True, pady=20)
        
        # Load task config
        self.task_config = load_task_config()
        self.task_var = tk.StringVar()

        try:
            image = Image.open("logo.png")
            image = image.resize((500,300))  # Adjust size as needed
            self.photo = ImageTk.PhotoImage(image)
            self.image_label = tk.Label(self.container, image=self.photo)  # ✅ this is correct
            self.image_label.pack(pady=10)
        except Exception as e:
            print(f"Error loading image: {e}")
            

        self.company_label = tk.Label(self, text="", font=("Helvetica", 16, "italic"))
        self.company_label.pack(pady=(0, 10))

        self.welcome_label = tk.Label(self, text="", font=("Helvetica", 12, "italic"))
        self.welcome_label.pack(pady=(0, 10))

        self.main_frame = tk.Frame(self)
        self.main_frame.pack(expand=True)

        # Task controls
        self.task_controls_frame = tk.Frame(self.main_frame)
        self.task_label = tk.Label(self.task_controls_frame, text="Select Task", font=("Helvetica", 14))
        self.task_label.pack(pady=(10, 0))
        self.task_dropdown = ttk.Combobox(self.task_controls_frame, textvariable=self.task_var, state="disabled", font=("Helvetica", 12))
        self.task_dropdown.pack(pady=5)

        # Status
        self.status_label = tk.Label(self.main_frame, text="", fg="blue", font=("Helvetica", 12))

        # Clock button
        self.clock_button = tk.Button(self.main_frame, image=self.clock_in_img, command=self.clock_toggle, bd=0)

        # Request button
        self.request_button = tk.Button(self.main_frame, text="Request Shift Edit", font=("Helvetica", 12), command=self.master.show_request_form)
        
        self.logout_button = tk.Button(self, text="Log Out", font=("Helvetica", 12), command=self.master.log_out_without_clocking_out)
        self.logout_button.pack(side="bottom", pady=10)

    # Prepares the task selection screen after login. Sets welcome text, task options, and updates UI (clocked-in status).
    def reset(self):
        user = self.master.user

        # Show company and hardcoded location
        self.company_label.config(text=f"Company: {user['company']} – Location: {LOCATION}")

        # Welcome message
        self.welcome_label.config(text=f"Welcome {user['name']}")

        # Reset task selection
        self.task_var.set("")
        self.task_dropdown.set("")
        self.task_dropdown["values"] = []

        # Update status (clocked in or not)
        self.update_ui()

        # Preload tasks for this location
        self.update_task_dropdown()

    def update_ui(self):
        # Clear everything from main_frame
        for widget in self.main_frame.winfo_children():
            widget.pack_forget()

        user = self.master.user
        clocked_in = is_clocked_in(user)

        if not clocked_in:
            self.task_controls_frame.pack(pady=10)
            print("User is not clocked in, showing task selection.")
        else:
            print("User is clocked in.")

        # ✅ Update status text and clock button label
        if clocked_in:
            self.clock_button.config(image=self.clock_out_img)
        else:
            self.clock_button.config(image=self.clock_in_img)

        # Repack elements
        self.status_label.pack(pady=10)
        self.clock_button.pack(pady=5)
        self.request_button.pack(pady=5)

    def clock_toggle(self):
        user = self.master.user
        logs = load_employee_logs(user)

        if is_clocked_in(user):
            self.master.clock_out_and_return()
        else:
            task = self.task_var.get()
            location = LOCATION
            if not self.task_var.get():
                messagebox.showerror("Missing Info", "Please select a task.")
                return
            task = task.strip()
            location = location.strip()
            logs.append(create_shift_entry(task, location))
            save_employee_logs(user, logs)
            messagebox.showinfo("Clocked In", f"Now working on '{task}' at '{location}'")
            self.master.log_out_without_clocking_out()  # Auto logout after clock-in

    def update_task_dropdown(self, *args):
        user = self.master.user
        tasks = get_tasks_for_user(user, LOCATION, self.task_config)

        self.task_var.set("")
        self.task_dropdown.set("")
        self.task_dropdown["values"] = tasks

        if tasks:
            self.task_dropdown["values"] = tasks
            self.task_dropdown.set("")
            self.task_dropdown.config(state="readonly")
        else:
            self.task_dropdown.set("")
            self.task_dropdown["values"] = []
            self.task_dropdown.config(state="disabled")


# Run the app
if __name__ == "__main__":
    app = ShiftClockApp()
    app.mainloop()
