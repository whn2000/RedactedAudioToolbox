import subprocess
import time
from PIL import ImageGrab

print("Starting main.py")
p = subprocess.Popen(["python", "main.py"])

print("Waiting 3 seconds for window to appear...")
time.sleep(3)

print("Taking screenshot...")
img = ImageGrab.grab()
img.save("screenshot.png")

print("Killing main.py...")
p.kill()
print("Done")
