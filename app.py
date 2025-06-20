import tkinter as tk
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

users = load_users()

class ShiftClockApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg="#e6f0fa")  # light blueish background
        self.title("Shift Clock System")
        self.geometry("500x800")

        self.user = None

        self.login_frame = LoginFrame(self)
        self.task_frame = TaskFrame(self)

        self.login_frame.pack()

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


class TaskFrame(tk.Frame):
    def __init__(self, master):

        super().__init__(master)

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


        # Location label and dropdown
        self.location_label = tk.Label(self, text="Select Location", font=("Helvetica", 14))
        self.location_label.pack(pady=(10, 0))

        self.location_var = tk.StringVar()
        self.location_dropdown = ttk.Combobox(self, textvariable=self.location_var, state="readonly", font=("Helvetica", 12))
        self.location_dropdown.pack(pady=5)
        self.location_dropdown.bind("<<ComboboxSelected>>", self.update_task_dropdown)

        # Task label and dropdown
        self.task_label = tk.Label(self, text="Select Task", font=("Helvetica", 14))
        self.task_label.pack(pady=(10, 0))

        self.task_dropdown = ttk.Combobox(self, textvariable=self.task_var, state="disabled", font=("Helvetica", 12))
        self.task_dropdown.pack(pady=5)

        # Status + buttons
        self.status_label = tk.Label(self, text="", fg="blue", font=("Helvetica", 12))
        self.status_label.pack(pady=10)

        self.clock_button = tk.Button(self, text="Clock In", font=("Helvetica", 14), command=self.clock_toggle)
        self.clock_button.pack(pady=5)

        self.bottom_bar = tk.Frame(self, bg="#f0f0f0")
        self.bottom_bar.pack(fill="x", side="bottom", pady=(10, 5), padx=10)

        self.logout_btn = tk.Button(self.bottom_bar, text="Log Out", font=("Helvetica", 10), command=self.master.log_out_without_clocking_out)
        self.logout_btn.pack(side="right")


    def reset(self):
        user = self.master.user

        # working company
        self.company_label.config(text=f"Company: {user['company']}")

        # welcome message for current user
        self.welcome_label.config(text=f"Welcome {user['name']}")

        locations = get_locations_for_user(user, self.task_config)

        self.location_var.set("")
        self.task_var.set("")
        self.location_dropdown["values"] = locations
        self.task_dropdown.set("")
        self.task_dropdown["values"] = []

        self.update_ui()

    def update_ui(self):
        if is_clocked_in(self.master.user):
            self.clock_button.config(text="Clock Out")
            self.status_label.config(text="Currently clocked in.")
        else:
            self.clock_button.config(text="Clock In")
            self.status_label.config(text="Not clocked in.")

    def clock_toggle(self):
        user = self.master.user
        logs = load_employee_logs(user)

        if is_clocked_in(user):
            self.master.clock_out_and_return()
        else:
            task = self.task_var.get()
            location = self.location_var.get()
            if not self.location_var.get() or not self.task_var.get():
                messagebox.showerror("Missing Info", "Please select a location and task.")
                return
            task = task.strip()
            location = location.strip()
            logs.append(create_shift_entry(task, location))
            save_employee_logs(user, logs)
            messagebox.showinfo("Clocked In", f"Now working on '{task}' at '{location}'")
            self.update_ui()

    def update_task_dropdown(self, *args):
        user = self.master.user
        selected_location = self.location_var.get()
        tasks = get_tasks_for_user(user, selected_location, self.task_config)

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
