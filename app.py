import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from utils import load_users, load_logs, save_logs, calc_duration, format_time, format_duration, now_trimmed
from datetime import datetime

users = load_users()
logs = load_logs()

user_map = {f"{u['name']} ({u['id']})": u['id'] for u in users}
user_names = list(user_map.keys())




def is_clocked_in(user_id):
    for log in reversed(logs):
        if log["user_id"] == user_id and log["clock_out"] is None:
            return True
    return False

def clock_in(user_id):
    if is_clocked_in(user_id):
        return "Already clocked in."
    logs.append({"user_id": user_id, "clock_in": now_trimmed(), "clock_out": None})
    save_logs(logs)
    return "Clocked in successfully."

def clock_out(user_id):
    for log in reversed(logs):
        if log["user_id"] == user_id and log["clock_out"] is None:
            log["clock_out"] = now_trimmed()
            save_logs(logs)
            return format_duration(log["clock_in"], log["clock_out"])
    return "You are not clocked in."

def update_ui(*args):
    selected_user = user_var.get()
    if selected_user not in user_map:
        action_btn.config(state="disabled", text="Clock In/Out")
        status_label.config(text="")
        return

    uid = user_map[selected_user]

    # Show whether they're clocked in and at what time
    if is_clocked_in(uid):
        action_btn.config(text="Clock Out", state="normal", command=lambda: handle_action(uid, "out"))
        user_logs = [log for log in logs if log["user_id"] == uid and log["clock_out"] is None]
        if user_logs:
            latest = user_logs[-1]
            clock_in_time = format_time(latest["clock_in"])
            status_label.config(text=f"Clocked in at {clock_in_time}")
    else:
        action_btn.config(text="Clock In", state="normal", command=lambda: handle_action(uid, "in"))
        status_label.config(text="Ready to clock in.")

def handle_action(uid, action):
    if action == "in":
        msg = clock_in(uid)
    else:
        msg = clock_out(uid)
    messagebox.showinfo("Success", msg)
    reset_ui()

def reset_ui():
    user_var.set("")
    action_btn.config(text="Clock In/Out", state="disabled")
    status_label.config(text="")

# GUI setup
root = tk.Tk()

try:
    image = Image.open("logo.png")  # or "your_image.jpg"
    image = image.resize((300, 100))  # Adjust size as needed
    photo = ImageTk.PhotoImage(image)

    image_label = tk.Label(root, image=photo)
    image_label.image = photo  # Prevent garbage collection
    image_label.pack(pady=10)
except Exception as e:
    print(f"Error loading image: {e}")

root.title("Shift Clock System")
root.geometry("500x300")  # Wider and taller

# Font styling
font_large = ("Helvetica", 16)
font_medium = ("Helvetica", 14)

# Widgets
tk.Label(root, text="Select Your Name", font=font_large).pack(pady=15)

user_var = tk.StringVar(root)
user_var.trace("w", update_ui)

user_dropdown = tk.OptionMenu(root, user_var, *user_names)
user_dropdown.config(font=font_medium, width=25)
user_dropdown.pack(pady=10)

action_btn = tk.Button(root, text="Clock In/Out", font=font_medium, state="disabled", width=20, height=2)
action_btn.pack(pady=20)

status_label = tk.Label(root, text="", fg="blue", font=font_medium)
status_label.pack()



root.mainloop()
