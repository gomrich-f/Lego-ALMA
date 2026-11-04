#!/usr/bin/env python3
"""
touch_ui.py

Simple touchscreen menu for choosing simulation/observation configurations.
- Select model image from ./models
- Choose HA start/end, frequency, steps, bits_count
- Save selection to `scripts/touch_selection.json`
- Optional: launch `scripts/simulate_controller.py` with chosen options

Designed to be clicked on a Pi touchscreen. Minimal dependencies (Tkinter, stdlib).
"""
import os
import json
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT = os.path.dirname(os.path.dirname(__file__))
MODELS_DIR = os.path.join(ROOT, 'models')
SELECTION_FILE = os.path.join(os.path.dirname(__file__), 'touch_selection.json')
SIM_SCRIPT = os.path.join(os.path.dirname(__file__), 'simulate_controller.py')


def list_models():
    try:
        files = sorted([f for f in os.listdir(MODELS_DIR) if os.path.isfile(os.path.join(MODELS_DIR, f))])
        if not files:
            return ['']
        return files
    except Exception:
        return ['']


class TouchUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ALMA Touch Control')
        self.geometry('600x480')
        self.configure(bg='black')
        self.create_widgets()

    def create_widgets(self):
        pad = 8
        lbl_style = {'bg':'black','fg':'white','font':('Arial',12)}

        # Image selection
        tk.Label(self, text='Image model', **lbl_style).place(x=20, y=20)
        self.model_var = tk.StringVar(value='')
        models = list_models()
        self.model_cb = ttk.Combobox(self, textvariable=self.model_var, values=models, width=30)
        self.model_cb.place(x=160, y=20)

        # HA start/end
        tk.Label(self, text='HA start (hours)', **lbl_style).place(x=20, y=70)
        self.ha_start = tk.DoubleVar(value=-4.0)
        tk.Spinbox(self, from_=-12, to=12, increment=0.5, textvariable=self.ha_start, width=8).place(x=160, y=70)

        tk.Label(self, text='HA end (hours)', **lbl_style).place(x=300, y=70)
        self.ha_end = tk.DoubleVar(value=4.0)
        tk.Spinbox(self, from_=-12, to=12, increment=0.5, textvariable=self.ha_end, width=8).place(x=420, y=70)

        # Frequency
        tk.Label(self, text='Frequency (GHz)', **lbl_style).place(x=20, y=120)
        self.freq = tk.DoubleVar(value=200.0)
        tk.Spinbox(self, from_=1.0, to=1000.0, increment=1.0, textvariable=self.freq, width=10).place(x=160, y=120)

        # Steps
        tk.Label(self, text='Steps', **lbl_style).place(x=20, y=170)
        self.steps = tk.IntVar(value=5)
        tk.Spinbox(self, from_=1, to=200, textvariable=self.steps, width=8).place(x=160, y=170)

        # Bits count
        tk.Label(self, text='Antennas (bits)', **lbl_style).place(x=300, y=170)
        self.bits = tk.IntVar(value=6)
        tk.Spinbox(self, from_=1, to=64, textvariable=self.bits, width=8).place(x=420, y=170)

        # Mode radio
        tk.Label(self, text='Mode', **lbl_style).place(x=20, y=220)
        self.mode = tk.StringVar(value='coords')
        modes = [('coords','coords'),('bits','bits'),('playback','playback')]
        x = 160
        for txt,val in modes:
            rb = tk.Radiobutton(self, text=txt, variable=self.mode, value=val, bg='black', fg='white', selectcolor='gray')
            rb.place(x=x, y=220)
            x += 90

        # Playback file chooser
        tk.Label(self, text='Playback file', **lbl_style).place(x=20, y=270)
        self.playback_var = tk.StringVar(value='')
        self.playback_entry = tk.Entry(self, textvariable=self.playback_var, width=40)
        self.playback_entry.place(x=160, y=270)
        tk.Button(self, text='Browse', command=self.browse_playback).place(x=480, y=265)

        # Buttons
        btn_save = tk.Button(self, text='Save selection', command=self.save_selection, width=18)
        btn_save.place(x=100, y=340)
        btn_run = tk.Button(self, text='Run simulation', command=self.run_simulation, width=18)
        btn_run.place(x=320, y=340)

        # Status
        self.status_var = tk.StringVar(value='Ready')
        tk.Label(self, textvariable=self.status_var, bg='black', fg='lightgreen').place(x=20, y=420)

    def browse_playback(self):
        f = filedialog.askopenfilename(initialdir='.', title='Select playback CSV', filetypes=[('CSV files','*.csv'),('All files','*.*')])
        if f:
            self.playback_var.set(f)

    def save_selection(self):
        cfg = self._gather()
        try:
            with open(SELECTION_FILE, 'w') as fout:
                json.dump(cfg, fout, indent=2)
            self.status_var.set('Saved to {}'.format(SELECTION_FILE))
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def _gather(self):
        model = self.model_var.get() or ''
        cfg = {
            'img': os.path.join('models', model) if model else '',
            'ha_start': float(self.ha_start.get()),
            'ha_end': float(self.ha_end.get()),
            'freq': float(self.freq.get()),
            'steps': int(self.steps.get()),
            'bits_count': int(self.bits.get()),
            'mode': self.mode.get(),
            'playback': self.playback_var.get() or None
        }
        return cfg

    def run_simulation(self):
        cfg = self._gather()
        self.save_selection()
        cmd = [sys.executable, SIM_SCRIPT]
        if cfg['mode']:
            cmd += ['--mode', cfg['mode']]
        if cfg['img']:
            cmd += ['--img', cfg['img']]
        if cfg['mode'] == 'bits':
            cmd += ['--bits-count', str(cfg['bits_count'])]
        cmd += ['--steps', str(cfg['steps'])]
        cmd += ['--ha-start', str(cfg['ha_start']), '--ha-end', str(cfg['ha_end']), '--freq', str(cfg['freq'])]
        if cfg['playback']:
            cmd += ['--playback', cfg['playback']]

        self.status_var.set('Starting simulation...')
        try:
            # Start as background process
            subprocess.Popen(cmd, cwd=os.path.dirname(SIM_SCRIPT), env=dict(os.environ, PYTHONPATH='.'), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.status_var.set('Simulation started')
        except Exception as e:
            messagebox.showerror('Run Error', str(e))
            self.status_var.set('Run failed')


if __name__ == '__main__':
    app = TouchUI()
    app.mainloop()
