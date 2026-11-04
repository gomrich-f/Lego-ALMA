import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
import threading
import time


# ================================================================
# GUI SETTINGS
# ================================================================

@dataclass
class GUISettings:
    """
    Einstellungen, die von der GUI an la_main
    übergeben werden.
    """

    ha_start: float = -3.0
    ha_end: float = 3.0
    obj_dec: float = -30.0
    obs_freq: float = 200.0
    img_file: str = "galaxy_lobes.png"
    webcam: bool = False


# ================================================================
# GUI
# ================================================================

class LlaGUI:

    def __init__(self, start_callback=None, stop_callback=None, shared_settings_dict=None):

        # --------------------------------------------------------
        # Hauptfenster
        # --------------------------------------------------------

        self.root = tk.Tk()

        self.root.title(
            "LEGO ALMA Control"
        )

        self.root.geometry(
            "550x650"
        )

        # --------------------------------------------------------
        # Callbacks zu la_main
        # --------------------------------------------------------

        self.start_callback = start_callback
        self.stop_callback = stop_callback

        # --------------------------------------------------------
        # Shared Settings Dictionary (für dynamische Updates)
        # --------------------------------------------------------

        self.shared_settings_dict = shared_settings_dict

        # --------------------------------------------------------
        # Zustand
        # --------------------------------------------------------

        self.running = False

        # Event zum Stoppen der Beobachtung
        self.stop_event = threading.Event()

        # Thread für die Beobachtung
        self.observation_thread = None

        # --------------------------------------------------------
        # GUI erstellen
        # --------------------------------------------------------

        self.create_widgets()

    # ============================================================
    # GUI AUFBAU
    # ============================================================

    def create_widgets(self):

        main_frame = ttk.Frame(
            self.root,
            padding=20
        )

        main_frame.pack(
            fill="both",
            expand=True
        )

        # ========================================================
        # Titel
        # ========================================================

        ttk.Label(
            main_frame,
            text="LEGO ALMA CONTROL",
            font=("TkDefaultFont", 20, "bold")
        ).pack(
            pady=(0, 20)
        )

        # ========================================================
        # OBSERVATION SETTINGS
        # ========================================================

        settings_frame = ttk.LabelFrame(
            main_frame,
            text="Observation settings",
            padding=15
        )

        settings_frame.pack(
            fill="x",
            pady=10
        )

        # --------------------------------------------------------
        # Hour Angle Start
        # --------------------------------------------------------

        ttk.Label(
            settings_frame,
            text="Hour Angle Start:"
        ).grid(
            row=0,
            column=0,
            sticky="w",
            pady=8
        )

        self.ha_start_var = tk.StringVar(
            value="-3"
        )

        # Trace für dynamische Updates
        self.ha_start_var.trace_add(
            "write",
            lambda *args: self._on_ha_start_changed()
        )

        ttk.Combobox(
            settings_frame,
            textvariable=self.ha_start_var,
            values=[
                "-6",
                "-5",
                "-4",
                "-3",
                "-2",
                "-1",
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6"
            ],
            state="readonly"
        ).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=10
        )

        ttk.Label(
            settings_frame,
            text="h"
        ).grid(
            row=0,
            column=2
        )

        # --------------------------------------------------------
        # Hour Angle End
        # --------------------------------------------------------

        ttk.Label(
            settings_frame,
            text="Hour Angle End:"
        ).grid(
            row=1,
            column=0,
            sticky="w",
            pady=8
        )

        self.ha_end_var = tk.StringVar(
            value="3"
        )

        self.ha_end_var.trace_add(
            "write",
            lambda *args: self._on_ha_end_changed()
        )

        ttk.Combobox(
            settings_frame,
            textvariable=self.ha_end_var,
            values=[
                "-6",
                "-5",
                "-4",
                "-3",
                "-2",
                "-1",
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6"
            ],
            state="readonly"
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=10
        )

        ttk.Label(
            settings_frame,
            text="h"
        ).grid(
            row=1,
            column=2
        )

        # --------------------------------------------------------
        # Declination
        # --------------------------------------------------------

        ttk.Label(
            settings_frame,
            text="Declination:"
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=8
        )

        self.dec_var = tk.StringVar(
            value="-30"
        )

        self.dec_var.trace_add(
            "write",
            lambda *args: self._on_dec_changed()
        )

        ttk.Combobox(
            settings_frame,
            textvariable=self.dec_var,
            values=[
                "-90",
                "-80",
                "-70",
                "-60",
                "-50",
                "-40",
                "-30",
                "-20",
                "-10",
                "0",
                "10",
                "20",
                "30",
                "40",
                "50",
                "60",
                "70",
                "80",
                "90"
            ],
            state="readonly"
        ).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=10
        )

        ttk.Label(
            settings_frame,
            text="deg"
        ).grid(
            row=2,
            column=2
        )

        # --------------------------------------------------------
        # Observation frequency
        # --------------------------------------------------------

        ttk.Label(
            settings_frame,
            text="Observation frequency:"
        ).grid(
            row=3,
            column=0,
            sticky="w",
            pady=8
        )

        self.freq_var = tk.StringVar(
            value="200"
        )

        self.freq_var.trace_add(
            "write",
            lambda *args: self._on_freq_changed()
        )

        ttk.Combobox(
            settings_frame,
            textvariable=self.freq_var,
            values=[
                "50",
                "100",
                "150",
                "200",
                "230",
                "345",
                "500",
                "1000"
            ],
            state="readonly"
        ).grid(
            row=3,
            column=1,
            sticky="ew",
            padx=10
        )

        ttk.Label(
            settings_frame,
            text="GHz"
        ).grid(
            row=3,
            column=2
        )

        # --------------------------------------------------------
        # Sky model
        # --------------------------------------------------------

        ttk.Label(
            settings_frame,
            text="Sky model:"
        ).grid(
            row=4,
            column=0,
            sticky="w",
            pady=8
        )

        self.img_var = tk.StringVar(
            value="galaxy_lobes.png"
        )

        self.img_var.trace_add(
            "write",
            lambda *args: self._on_img_changed()
        )

        ttk.Combobox(
            settings_frame,
            textvariable=self.img_var,
            values=[
                "galaxy_lobes.png",
                "Galaxy1.jpg",
                "Galaxy2.jpg",
                "Galaxy3.jpg",
                "Galaxy4.jpg",
                "Planet1.jpg",
                "Planet2.jpg",
                "Planet3.jpg",
                "Planet4.jpg",
                "BH1.jpg",
                "BH2.jpg",
                "BH3.jpg",
                "BH4.jpg",
                "Misc4.jpg"
            ],
            state="readonly"
        ).grid(
            row=4,
            column=1,
            sticky="ew",
            padx=10
        )

        settings_frame.columnconfigure(
            1,
            weight=1
        )

        # ========================================================
        # OPTIONS
        # ========================================================

        options_frame = ttk.LabelFrame(
            main_frame,
            text="Options",
            padding=15
        )

        options_frame.pack(
            fill="x",
            pady=10
        )

        # --------------------------------------------------------
        # Webcam
        # --------------------------------------------------------

        self.webcam_var = tk.BooleanVar(
            value=False
        )

        self.webcam_var.trace_add(
            "write",
            lambda *args: self._on_webcam_changed()
        )

        ttk.Checkbutton(
            options_frame,
            text="Use webcam",
            variable=self.webcam_var
        ).pack(
            anchor="w"
        )

        # ========================================================
        # STATUS
        # ========================================================

        status_frame = ttk.LabelFrame(
            main_frame,
            text="Status",
            padding=15
        )

        status_frame.pack(
            fill="x",
            pady=10
        )

        self.status_var = tk.StringVar(
            value="STOPPED"
        )

        ttk.Label(
            status_frame,
            textvariable=self.status_var
        ).pack(
            anchor="w"
        )

        # ========================================================
        # BUTTONS
        # ========================================================

        button_frame = ttk.Frame(
            main_frame
        )

        button_frame.pack(
            fill="x",
            pady=20
        )

        # --------------------------------------------------------
        # START
        # --------------------------------------------------------

        self.start_button = ttk.Button(
            button_frame,
            text="START",
            command=self.start
        )

        self.start_button.pack(
            side="left",
            expand=True,
            fill="x",
            padx=5
        )

        # --------------------------------------------------------
        # STOP
        # --------------------------------------------------------

        self.stop_button = ttk.Button(
            button_frame,
            text="STOP",
            command=self.stop,
            state="disabled"
        )

        self.stop_button.pack(
            side="left",
            expand=True,
            fill="x",
            padx=5
        )

        # --------------------------------------------------------
        # STOP ALL
        # --------------------------------------------------------

        self.stop_all_button = ttk.Button(
            button_frame,
            text="STOP ALL",
            command=self.stop_all
        )

        self.stop_all_button.pack(
            side="left",
            expand=True,
            fill="x",
            padx=5
        )

        # --------------------------------------------------------
        # CLOSE
        # --------------------------------------------------------

        ttk.Button(
            main_frame,
            text="Close",
            command=self.close
        ).pack()

    # ============================================================
    # EINSTELLUNGEN AUSLESEN
    # ============================================================

    def get_settings(self):

        return GUISettings(

            ha_start=float(
                self.ha_start_var.get()
            ),

            ha_end=float(
                self.ha_end_var.get()
            ),

            obj_dec=float(
                self.dec_var.get()
            ),

            obs_freq=float(
                self.freq_var.get()
            ),

            img_file=self.img_var.get(),

            webcam=self.webcam_var.get()
        )

    # ============================================================
    # START
    # ============================================================

    def start(self):

        # Falls bereits eine Beobachtung läuft
        if self.running:
            return

        # --------------------------------------------------------
        # Einstellungen auslesen
        # --------------------------------------------------------

        settings = self.get_settings()

        # --------------------------------------------------------
        # Prüfen des Hour-Angle-Bereichs
        # --------------------------------------------------------

        if settings.ha_start >= settings.ha_end:

            self.status_var.set(
                "ERROR: HA Start must be smaller than HA End"
            )

            print(
                "ERROR: Hour Angle Start must be smaller "
                "than Hour Angle End."
            )

            return

        # --------------------------------------------------------
        # Einstellungen ausgeben
        # --------------------------------------------------------

        print()
        print(
            "=========================================="
        )
        print(
            "Starting observation"
        )
        print(
            "=========================================="
        )
        print(
            settings
        )
        print(
            "=========================================="
        )

        # --------------------------------------------------------
        # Zustand aktualisieren
        # --------------------------------------------------------

        self.running = True

        self.stop_event.clear()

        self.status_var.set(
            "RUNNING"
        )

        self.start_button.config(
            state="disabled"
        )

        self.stop_button.config(
            state="normal"
        )

        # --------------------------------------------------------
        # Beobachtung starten
        # --------------------------------------------------------

        if self.start_callback is not None:

            self.observation_thread = threading.Thread(
                target=self.run_observation,
                args=(settings,),
                daemon=True
            )

            self.observation_thread.start()

        else:

            print(
                "WARNING: No start_callback was provided."
            )

    # ============================================================
    # BEOBACHTUNG
    # ============================================================

    def run_observation(self, settings):

        try:

            self.start_callback(
                settings,
                self.stop_event,
                self.shared_settings_dict
            )

        except Exception as e:

            print(
                "Error in observation:"
            )

            print(e)

        finally:

            # GUI darf nur aus dem Tkinter-Hauptthread
            # aktualisiert werden
            self.root.after(
                0,
                self.observation_finished
            )

    # ============================================================
    # BEOBACHTUNG BEENDET
    # ============================================================

    def observation_finished(self):

        self.running = False

        self.status_var.set(
            "STOPPED"
        )

        self.start_button.config(
            state="normal"
        )

        self.stop_button.config(
            state="disabled"
        )

    # ============================================================
    # STOP
    # ============================================================

    def stop(self):

        if not self.running:
            return

        print(
            "Stopping observation..."
        )

        self.stop_event.set()

        self.status_var.set(
            "STOPPING..."
        )

    # ============================================================
    # STOP ALL
    # ============================================================

    def stop_all(self):

        print(
            "Stopping all processes..."
        )

        # --------------------------------------------------------
        # Beobachtungsthread auffordern zu stoppen
        # --------------------------------------------------------

        self.stop_event.set()

        # --------------------------------------------------------
        # la_main informieren
        # --------------------------------------------------------

        if self.stop_callback is not None:

            try:

                self.stop_callback()

            except Exception as e:

                print(
                    "Error while stopping all processes:"
                )

                print(e)

        # --------------------------------------------------------
        # GUI zurücksetzen
        # --------------------------------------------------------

        self.running = False

        self.status_var.set(
            "ALL PROCESSES STOPPED"
        )

        self.start_button.config(
            state="normal"
        )

        self.stop_button.config(
            state="disabled"
        )

    # ============================================================
    # DYNAMIC PARAMETER UPDATE CALLBACKS
    # ============================================================

    def _update_shared_settings(self):
        """Write current GUI values to shared_settings_dict"""
        if self.shared_settings_dict is not None:
            try:
                self.shared_settings_dict['ha_start'] = float(self.ha_start_var.get())
                self.shared_settings_dict['ha_end'] = float(self.ha_end_var.get())
                self.shared_settings_dict['obj_dec'] = float(self.dec_var.get())
                self.shared_settings_dict['obs_freq'] = float(self.freq_var.get())
                self.shared_settings_dict['img_file'] = self.img_var.get()
                self.shared_settings_dict['webcam'] = self.webcam_var.get()
                self.shared_settings_dict['_last_update'] = time.time()
            except Exception as e:
                print(f"Error updating shared settings: {e}")

    def _on_ha_start_changed(self):
        """Called when HA start is changed"""
        if self.running:
            self._update_shared_settings()

    def _on_ha_end_changed(self):
        """Called when HA end is changed"""
        if self.running:
            self._update_shared_settings()

    def _on_dec_changed(self):
        """Called when declination is changed"""
        if self.running:
            self._update_shared_settings()

    def _on_freq_changed(self):
        """Called when frequency is changed"""
        if self.running:
            self._update_shared_settings()

    def _on_img_changed(self):
        """Called when image is changed"""
        if self.running:
            self._update_shared_settings()

    def _on_webcam_changed(self):
        """Called when webcam option is changed"""
        if self.running:
            self._update_shared_settings()

    # ============================================================
    # CLOSE
    # ============================================================

    def close(self):

        print(
            "Closing GUI..."
        )

        # Beobachtung stoppen
        self.stop_event.set()

        # Alle Prozesse stoppen
        if self.stop_callback is not None:

            try:

                self.stop_callback()

            except Exception as e:

                print(
                    "Error while stopping processes:"
                )

                print(e)

        # Fenster schließen
        self.root.destroy()

    # ============================================================
    # GUI STARTEN
    # ============================================================

    def run(self):

        self.root.mainloop()


# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    gui = LlaGUI()

    gui.run()