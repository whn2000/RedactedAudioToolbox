import sys
import tkinter as tk
import customtkinter as ctk

from i18n import _, set_language, CURRENT_LANG, subscribe_lang_change
from dependency_manager import check_and_install_dependencies
from elitetmhelper2 import AppGUI as RedactedFinderGUI
from flac_downsampler import FlacDownsamplerGUI
from lossless_checker import LosslessCheckerGUI
from main import MainApp

print("Starting test...")
root = ctk.CTk()
root.withdraw()
print("Dependencies check...")
# bypass dependencies check for test
root.deiconify()
print("Init MainApp...")
app = MainApp(root)
print("MainApp initialized. Scheduling destroy...")
root.after(3000, root.destroy)
print("Starting mainloop...")
root.mainloop()
print("Test completed successfully.")
