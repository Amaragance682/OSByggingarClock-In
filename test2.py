import tkinter as tk
from tkinter import ttk
import time

root = tk.Tk()

class Thing(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        button = tk.Button(root, text="click me", command=self.spawn_toplevel)
        button.pack()

        e = tk.Entry(root)
        e.pack(pady=20)

    def spawn_toplevel(self, event=None):
        self.top = tk.Toplevel(self)
        self.top.focus()

        self.frame = tk.Frame(self.top)
        self.frame.pack()

        self.top.bind("<FocusOut>", self.wait_for_focus)

        self.topb = ttk.Button(self.frame, text="lost focus?")
        self.topb.pack()

    def wait_for_focus(self, event):
        print("in wait for focus")
        focused_widget = root.focus_get()
        if not focused_widget:
            self.top.withdraw()
            return
        parent = focused_widget.winfo_parent()
        if focused_widget and str(self.frame) in str(parent):
            return
        self.top.withdraw()

thing = Thing(root)

root.geometry("300x200")
root.mainloop()
