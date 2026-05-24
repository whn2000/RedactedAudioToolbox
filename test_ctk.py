import customtkinter as ctk
import tkinter as tk
try:
    root = ctk.CTk()
    textbox = ctk.CTkTextbox(root)
    textbox.insert(tk.END, "hello")
    textbox.see(tk.END)
    print("CTkTextbox has see method.")
except Exception as e:
    print(f"CTkTextbox error: {e}")
