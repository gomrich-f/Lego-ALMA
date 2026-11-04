import tkinter as tk
from tkinter import ttk


# --------------------------------------------------
# Hauptfenster
# --------------------------------------------------

root = tk.Tk()
root.title("LEGO ALMA Control")
root.geometry("500x550")


# --------------------------------------------------
# Überschrift
# --------------------------------------------------

title = ttk.Label(
    root,
    text="LEGO ALMA Control",
    font=("Arial", 22)
)

title.pack(pady=20)


# --------------------------------------------------
# Hour Angle
# --------------------------------------------------

ttk.Label(
    root,
    text="Hour Angle:"
).pack()

ha = ttk.Combobox(
    root,
    values=[
        "-6 h",
        "-3 h",
        "0 h",
        "+3 h"
    ],
    state="readonly",
    width=25
)

ha.current(2)
ha.pack(pady=5)


# --------------------------------------------------
# Declination
# --------------------------------------------------

ttk.Label(
    root,
    text="Declination:"
).pack()

dec = ttk.Combobox(
    root,
    values=[
        "-80°",
        "-50°",
        "-30°",
        "-10°"
    ],
    state="readonly",
    width=25
)

dec.current(0)
dec.pack(pady=5)


# --------------------------------------------------
# Integration Time
# --------------------------------------------------

ttk.Label(
    root,
    text="Integration time:"
).pack()

int_time = ttk.Combobox(
    root,
    values=[
        "0.2 h",
        "1 h",
        "50 h",
        "500 h"
    ],
    state="readonly",
    width=25
)

int_time.current(0)
int_time.pack(pady=5)


# --------------------------------------------------
# Frequency
# --------------------------------------------------

ttk.Label(
    root,
    text="Frequency:"
).pack()

freq = ttk.Combobox(
    root,
    values=[
        "0 GHz",
        "50 GHz",
        "100 GHz",
        "250 GHz"
    ],
    state="readonly",
    width=25
)

freq.current(0)
freq.pack(pady=5)


# --------------------------------------------------
# Sky Model
# --------------------------------------------------

ttk.Label(
    root,
    text="Sky Model:"
).pack()

model = ttk.Combobox(
    root,
    values=[
        "Galaxy1.jpg",
        "Planet1.jpg",
        "BH1.jpg",
        "Misc4.jpg"
    ],
    state="readonly",
    width=25
)

model.current(0)
model.pack(pady=5)


# --------------------------------------------------
# Buttons
# --------------------------------------------------

button_frame = ttk.Frame(root)
button_frame.pack(pady=30)


start_button = ttk.Button(
    button_frame,
    text="START",
    command=lambda: print(
        "START:",
        ha.get(),
        dec.get(),
        int_time.get(),
        freq.get(),
        model.get()
    )
)

start_button.pack(side="left", padx=10)


stop_button = ttk.Button(
    button_frame,
    text="STOP",
    command=lambda: print("STOP")
)

stop_button.pack(side="left", padx=10)


# --------------------------------------------------
# GUI starten
# --------------------------------------------------

root.mainloop()
