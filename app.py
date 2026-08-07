import tkinter as tk
import time
import random

# Window setup
root = tk.Tk()
root.title("Mausa Ji Quotes")
root.geometry("700x450")
root.configure(bg="#0f0c20")
root.resizable(False, False)

# Main Canvas for graphics
canvas = tk.Canvas(root, width=700, height=450, bg="#0f0c20", highlightthickness=0)
canvas.pack(fill="both", expand=True)

# Background animated stars
stars = []
for _ in range(60):
    x = random.randint(10, 690)
    y = random.randint(10, 440)
    r = random.randint(1, 3)
    star = canvas.create_oval(x - r, y - r, x + r, y + r, fill="#4a4e69", outline="")
    stars.append((star, r))

# Neon Glowing Border Box
canvas.create_rectangle(30, 30, 670, 420, outline="#e0a96d", width=2)
canvas.create_rectangle(35, 35, 665, 415, outline="#ffd700", width=3)
canvas.create_rectangle(40, 40, 660, 410, outline="#e0a96d", width=2)

# Text elements
quote_text = "MONEY IS EVERYTHING,\nIF U HARD WORKING, U DESERVE."
author_text = "— BY MAUSA JI"

# Text placement
quote_id = canvas.create_text(
    350, 180, text="", font=("Helvetica", 22, "bold"), fill="#ffd700", justify="center"
)
author_id = canvas.create_text(
    350, 320, text="", font=("Courier", 18, "bold"), fill="#00ffff", justify="center"
)


# Typing Animation Function
def type_writer(text, text_id, delay=0.06, current_index=0):
    if current_index <= len(text):
        canvas.itemconfig(text_id, text=text[:current_index])
        root.after(int(delay * 1000), type_writer, text, text_id, delay, current_index + 1)
    elif text_id == quote_id:
        # Quote type hone ke baad author name start hoga
        root.after(300, type_writer, author_text, author_id, 0.08, 0)


# Star twinkling animation effect
def animate_stars():
    for star, r in stars:
        color = random.choice(["#ffffff", "#ffd700", "#00ffff", "#4a4e69", "#ff007f"])
        canvas.itemconfig(star, fill=color)
    root.after(300, animate_stars)


# Start Animations
animate_stars()
root.after(500, type_writer, quote_text, quote_id)

root.mainloop()
