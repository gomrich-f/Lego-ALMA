import logging
import os
import logging
import os
import sys
import time
import traceback

import tkinter as tk
import numpy as np

import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import Angle
import serial

from time import sleep
from multiprocessing import Process, Manager

from la_control_new import Control, id_usb_conn
from la_obs_img_new import Observatory, SkyImage, Observation
from la_disp_man import DisplayManager
from la_reader_new import ReadController, VideoReadController
import la_config

from la_gui import LlaGUI
# Hilfsfunktionen
# ============================================================

def vprint(*args, verbose=True):
    if verbose:
        print(*args)


# ============================================================
# Globale Variablen
# ============================================================
#
# Diese werden von START und STOP verwendet.
#

manager = None

last_measurements = None
video_dict = None

ser0_controller = None
ser1_controller = None
vid_controller = None

p0 = None
p1 = None
pv = None

alma = None
imgobj = None
cont = None
obs = None
dm = None


# ============================================================
# STOPPEN ALLER PROZESSE
# ============================================================

def stop_all_processes():

    global p0
    global p1
    global pv

    print()
    print("==========================================")
    print("Stopping all processes...")
    print("==========================================")

    processes = [
        ("Serial 0", p0),
        ("Video", pv),
    ]

    for name, process in processes:

        if process is None:
            continue

        try:

            if process.is_alive():

                print(f"Stopping {name}...")

                process.terminate()
                process.join(timeout=2)

                # Falls der Prozess immer noch läuft
                if process.is_alive():

                    print(
                        f"{name} did not terminate normally. "
                        f"Force terminating..."
                    )

                    process.kill()
                    process.join()

                else:

                    print(f"{name} stopped.")

        except Exception as e:

            print(
                f"Error stopping {name}:",
                e
            )

    # Referenzen zurücksetzen

    p0 = None
    p1 = None
    pv = None

    print("All processes stopped.")
    print()


# ============================================================
# OBSERVATION
# ============================================================

def start_observation(settings, stop_event, shared_settings_dict=None):

    global manager
    global last_measurements
    global video_dict
    global settings_dict
    global _shared_settings_dict

    global ser0_controller
    global ser1_controller
    global vid_controller

    global p0
    global p1
    global pv

    global alma
    global imgobj
    global cont
    global obs
    global dm

    print()
    print("==========================================")
    print("STARTING LEGO ALMA")
    print("==========================================")

    print("Settings:")
    print(settings)
    print()

    # Store reference to shared settings dict for use in observation loop
    _shared_settings_dict = shared_settings_dict

    # ========================================================
    # Manager
    # ========================================================

    manager = Manager()

    last_measurements = manager.dict()
    video_dict = manager.dict()
    
    # Shared settings dict for dynamic parameter updates
    settings_dict = manager.dict()
    settings_dict['ha_start'] = settings.ha_start
    settings_dict['ha_end'] = settings.ha_end
    settings_dict['obj_dec'] = settings.obj_dec
    settings_dict['obs_freq'] = settings.obs_freq
    settings_dict['img_file'] = settings.img_file
    settings_dict['webcam'] = settings.webcam
    settings_dict['_last_update'] = 0.0
    
    # Sync current settings to GUI's shared_settings_dict (clear old values from previous run)
    if shared_settings_dict is not None:
        shared_settings_dict.clear()
        shared_settings_dict['ha_start'] = settings.ha_start
        shared_settings_dict['ha_end'] = settings.ha_end
        shared_settings_dict['obj_dec'] = settings.obj_dec
        shared_settings_dict['obs_freq'] = settings.obs_freq
        shared_settings_dict['img_file'] = settings.img_file
        shared_settings_dict['webcam'] = settings.webcam
        shared_settings_dict['_last_update'] = 0.0

    # ========================================================
    # Reader Controller
    # ========================================================

    sleep_time = 0.1

    ser0_controller = ReadController(
        sleep_time=sleep_time
    )

    # Webcam Controller

    vid_controller = VideoReadController()

    # ========================================================
    # Serielle Verbindungen
    # ========================================================

    ser_conn_0 = {
        "path": "/dev/ttyACM1",
        "baud": 9600,
        "timeout": 1,
        "parity": serial.PARITY_NONE,
        "rtscts": False
    }


    # ========================================================
    # Serielle Prozesse starten
    # ========================================================

    print("Starting serial readers...")

    p0 = Process(
        target=ser0_controller._loop_read,
        args=(
            last_measurements,
            ser_conn_0,
            "ser"
        ),
        kwargs={
            "verbose": False
        }
    )

    p0.start()

    print("Serial readers started.")

    # ========================================================
    # Webcam
    # ========================================================

    if settings.webcam:

        print("Starting webcam...")

        pv = Process(
            target=vid_controller.read_vid,
            args=(
                video_dict,
            )
        )

        pv.start()

        print("Webcam process started.")

        # Kamera braucht etwas Zeit

        time.sleep(1)

    else:

        pv = None


    # ========================================================
    # Kurz warten, bis serielle Geräte im shared dict erscheinen
    # ========================================================

    print("Waiting for serial devices to appear in measurements...")

    for _ in range(80):  # bis zu 8 Sekunden warten

        if stop_event.is_set():

            print("Stop requested during startup.")

            stop_all_processes()

            if manager is not None:
                manager.shutdown()

            return

        candidates = [k for k in list(last_measurements.keys()) if ('USB' in k or 'ACM' in k)]
        if len(candidates) > 0:
            break

        time.sleep(0.1)

    # ========================================================
    # Observatory
    # ========================================================

    # Wenn das serielle Gerät gefunden wurde, warte kurz auf erste Messwerte
    if len(candidates) > 0:
        dev = candidates[0]
        for _ in range(50):  # bis zu 5 Sekunden warten
            try:
                if stop_event.is_set():
                    stop_all_processes()
                    if manager is not None:
                        manager.shutdown()
                    return

                val = last_measurements.get(dev, None)
                if val is not None and len(val) > 0:
                    break

            except Exception:
                pass

            time.sleep(0.1)

    # Debug: show what serial keys and sample measurements are available
    print("DEBUG: last_measurements keys:", list(last_measurements.keys()))
    for _k in list(last_measurements.keys()):
        try:
            if _k.startswith('_debug'):
                print("DEBUG:", _k, "->", last_measurements[_k])
            else:
                print("DEBUG:", _k, "->", last_measurements[_k][:20] if len(last_measurements[_k]) > 0 else "[]")
        except Exception as _e:
            print("DEBUG:", _k, "-> (error reading):", _e)

    print("Initializing observatory...")

    alma = Observatory(
        ant_pos_bit_file="./ant_pos.2.txt"
    )

    alma.load_ant_pos_bit_file()

    # ========================================================
    # USB IDs finden
    # ========================================================


    try:

        try:
            ant_usb_id, ctrl_usb_id = id_usb_conn(
                last_measurements
            )
        except Exception as e:
            print("id_usb_conn error:", e)
            # Fallback: use first available serial-like key from last_measurements
            candidates = [k for k in list(last_measurements.keys()) if ('USB' in k or 'ACM' in k)]
            if len(candidates) > 0:
                ant_usb_id = candidates[0]
                ctrl_usb_id = None
                print("Fallback: using", ant_usb_id, "as antenna source; no control device.")
            else:
                raise

    except Exception as e:

        print()
        print("ERROR while identifying USB devices:")
        print(e)
        print()

        stop_all_processes()

        if manager is not None:
            manager.shutdown()

        return

    print(
        "Antenna USB:",
        ant_usb_id
    )

    print(
        "Control USB:",
        ctrl_usb_id
    )

    src_list = [
        ant_usb_id
    ]

    ctrl_list = [
        ctrl_usb_id
    ]

    alma.set_read_source_ids(
        src_list
    )

    # ========================================================
    # Antennenpositionen
    # ========================================================

    print("Reading antenna positions...")

    try:

        alma.set_ant_pos(
            last_measurements
        )

        alma.make_baselines()

    except Exception as e:

        print(
            "Error while initializing antenna positions:"
        )

        print(e)

        stop_all_processes()

        if manager is not None:
            manager.shutdown()

        return

    # ========================================================
    # Sky Image
    # ========================================================

    print("Loading sky model...")

    # Webcam überschreibt das ausgewählte Bild

    if settings.webcam:

        image_filename = "Misc4.png"

    else:

        image_filename = settings.img_file

    imgobj = SkyImage(
        path="./models/",
        filename=image_filename
    )

    # Deklination aus GUI

    imgobj.declination = (
        settings.obj_dec * u.deg
    )

    # Bild laden

    if settings.webcam:

        # Beim ersten Laden existiert eventuell noch
        # kein Videobild.

        try:

            if "val" in video_dict:

                imgobj.load_image(
                    video_stream=video_dict["val"]
                )

            else:

                print(
                    "Waiting for webcam frame..."
                )

                for _ in range(30):

                    if stop_event.is_set():

                        stop_all_processes()

                        if manager is not None:
                            manager.shutdown()

                        return

                    if "val" in video_dict:
                        break

                    time.sleep(0.1)

                imgobj.load_image(
                    video_stream=video_dict.get("val")
                )

        except Exception as e:

            print(
                "Error loading webcam:"
            )

            print(e)

            stop_all_processes()

            if manager is not None:
                manager.shutdown()

            return

    else:

        imgobj.load_image()

    imgobj.make_invert()

    # ========================================================
    # Control
    # ========================================================

    print("Initializing control...")

    cont = Control(
        ctrl_id=ctrl_usb_id
    )

    cont.add_buttons()

    cont.set_but_bit_dict_file(
        "but_dict.pickle"
    )

    cont.load_but_bit_dict()

    cont.set_swi_bit_list(
        la_config.swi_bits
    )

    cont.get_state(
        last_measurements
    )

    # ========================================================
    # Observation
    # ========================================================

    print("Initializing observation...")

    obs = Observation(
        alma,
        imgobj,
        cont,
        obs_frequency=settings.obs_freq * u.GHz,
        var_dic=la_config.var_dic
    )

    # --------------------------------------------------------
    # GUI-Werte direkt setzen
    # --------------------------------------------------------

    obs.SkyImage.declination = (
        settings.obj_dec * u.deg
    )

    obs.obs_frequency = (
        settings.obs_freq * u.GHz
    )

    # Wellenlänge korrekt setzen

    from astropy.constants import c

    obs.obs_lam = (
        c / obs.obs_frequency
    )

    # --------------------------------------------------------
    # Hour Angle
    # --------------------------------------------------------

    # Die GUI gibt momentan einen einzelnen HA-Wert vor.
    #
    # Wir verwenden ihn als START und setzen das Ende
    # abhängig von der Integrationszeit.
    #

    # Hour Angle: support old `hr_angle` or new `ha_start`/`ha_end` from GUI
    if hasattr(settings, 'ha_start') and hasattr(settings, 'ha_end'):
        obs.HA_START = (
            Angle(settings.ha_start, u.hourangle)
        )
        obs.HA_END = (
            Angle(settings.ha_end, u.hourangle)
        )
    elif hasattr(settings, 'hr_angle'):
        obs.HA_START = (
            Angle(settings.hr_angle, u.hourangle)
        )
        obs.HA_END = (
            obs.HA_START
            + Angle(settings.int_time, u.hourangle)
        )
    else:
        # sensible default if GUI doesn't provide HA
        obs.HA_START = Angle(-3.0, u.hourangle)
        obs.HA_END = Angle(3.0, u.hourangle)

    # --------------------------------------------------------
    # Initiale Berechnungen
    # --------------------------------------------------------

    # Number of samples: convert HA interval to hours and multiply by sample frequency
    # compute duration in hours from hourangle-aware HA values
    try:
        duration_hours = (obs.HA_END.to(u.hourangle).value - obs.HA_START.to(u.hourangle).value)
    except Exception:
        duration_hours = (obs.HA_END.to(u.hour).value - obs.HA_START.to(u.hour).value)
    # support sample_freq as Quantity or plain number
    try:
        if hasattr(obs.sample_freq, 'to'):
            sf = obs.sample_freq.to(1 / u.hour).value
        else:
            sf = float(obs.sample_freq)
    except Exception:
        sf = float(obs.sample_freq)

    obs.N_samples = int(duration_hours * sf) + 1

    obs.calc_el_curve()

    obs.make_uv_coverage()

    obs.grid_uv_coverage()

    obs.make_masked_arr()

    obs.make_dirty_arr()

    # ========================================================
    # Display Manager
    # ========================================================

    print("Initializing display...")

    dm = DisplayManager()

    dm.setup_main_figure()

    dm.init_ant_plot(
        maxoffset=120
    )

    dm.init_ant_proj_plot()

    pixel_size = obs.SkyImage.pixel_size

    print(
        "Pixel size:",
        pixel_size
    )

    inv_pixel_size = (
        1. / pixel_size
    ).to(
        1. / u.radian
    )

    dm.init_img_plot(
        pixel_size=pixel_size
    )

    dm.init_fft_plot()

    dm.init_uvc_plot(
        inv_pixel_size=inv_pixel_size
    )

    dm.init_dbe_plot(
        pixel_size=pixel_size
    )

    dm.init_dim_plot(
        pixel_size=pixel_size
    )

    dm.init_mft_plot(
        inv_pixel_size=inv_pixel_size
    )

    dm.init_ind_plot(
        la_config.var_dic,
        obs
    )

    dm.setup_blit_manager()

    # ========================================================
    # Hauptschleife
    # ========================================================

    print()
    print("==========================================")
    print("OBSERVATION RUNNING")
    print("==========================================")
    print()

    try:

        debug_last = time.time()
        
        # Initialize parameter change tracking
        start_observation._last_param_check = 0.0

        while not stop_event.is_set():

            # =================================================
            # Dynamic parameter updates from GUI
            # =================================================
            
            try:
                # Check if settings have been updated in shared dict
                if _shared_settings_dict is not None and _shared_settings_dict.get('_last_update', 0.0) > getattr(start_observation, '_last_param_check', 0.0):
                    
                    # Update parameters from shared dict
                    new_ha_start = _shared_settings_dict.get('ha_start', settings.ha_start)
                    new_ha_end = _shared_settings_dict.get('ha_end', settings.ha_end)
                    new_dec = _shared_settings_dict.get('obj_dec', settings.obj_dec)
                    new_freq = _shared_settings_dict.get('obs_freq', settings.obs_freq)
                    new_img = _shared_settings_dict.get('img_file', settings.img_file)
                    new_webcam = _shared_settings_dict.get('webcam', settings.webcam)
                    
                    params_changed = False
                    
                    # Hour Angle changed
                    if new_ha_start != settings.ha_start or new_ha_end != settings.ha_end:
                        settings.ha_start = new_ha_start
                        settings.ha_end = new_ha_end
                        obs.HA_START = Angle(settings.ha_start, u.hourangle)
                        obs.HA_END = Angle(settings.ha_end, u.hourangle)
                        print(f"[DYNAMIC] HA updated: {settings.ha_start} to {settings.ha_end}")
                        params_changed = True
                    
                    # Declination changed
                    if new_dec != settings.obj_dec:
                        settings.obj_dec = new_dec
                        obs.SkyImage.declination = settings.obj_dec * u.deg
                        print(f"[DYNAMIC] Declination updated: {settings.obj_dec}°")
                        params_changed = True
                    
                    # Frequency changed
                    if new_freq != settings.obs_freq:
                        settings.obs_freq = new_freq
                        obs.obs_frequency = settings.obs_freq * u.GHz
                        from astropy.constants import c
                        obs.obs_lam = c / obs.obs_frequency
                        print(f"[DYNAMIC] Frequency updated: {settings.obs_freq} GHz")
                        params_changed = True
                    
                    # Image file changed
                    if new_img != settings.img_file:
                        settings.img_file = new_img
                        print(f"[DYNAMIC] Image file updated: {settings.img_file}")
                        # Reload image
                        try:
                            obs.SkyImage.load_image(filename=settings.img_file)
                            print(f"[DYNAMIC] Image loaded successfully")
                        except Exception as e:
                            print(f"[DYNAMIC] Error loading image: {e}")
                        params_changed = True
                    
                    # Webcam changed
                    if new_webcam != settings.webcam:
                        settings.webcam = new_webcam
                        print(f"[DYNAMIC] Webcam mode updated: {settings.webcam}")
                        params_changed = True
                    
                    start_observation._last_param_check = _shared_settings_dict.get('_last_update', 0.0)
                    
            except Exception as e:
                print(f"[DYNAMIC] Error in parameter update: {e}")

            # =================================================
            # Antennenpositionen aktualisieren
            # =================================================

            obs.Observatory.set_ant_pos(
                last_measurements
            )

            obs.Observatory.make_baselines()

            # =================================================
            # Webcam aktualisieren
            # =================================================

            if settings.webcam:

                if "val" in video_dict:

                    obs.SkyImage.load_image(
                        video_stream=video_dict["val"]
                    )

            # periodic debug print for webcam state (once per second)
            try:
                if settings.webcam and (time.time() - debug_last) > 1.0:
                    debug_last = time.time()
                    print("WEBCAM DEBUG: _debug_cam=", video_dict.get('_debug_cam'),
                          "_frame_shape=", video_dict.get('_frame_shape'),
                          "_val_ready=", video_dict.get('_val_ready'),
                          "Misc4 exists=", os.path.exists('./Misc4.png'))
            except Exception:
                pass

            # =================================================
            # Control aktualisieren
            # =================================================

            obs.update_obs_from_control(
                last_measurements,
                video_stream=(
                    video_dict.get("val")
                    if settings.webcam
                    else None
                )
            )

            # =================================================
            # Observation calculations
            # =================================================

            obs.calc_el_curve()

            obs.make_uv_coverage()

            obs.grid_uv_coverage()

            obs.make_masked_arr(
                weights="uniform"
            )

            obs.make_dirty_arr()

            pixel_size = (
                obs.SkyImage.pixel_size
            )

            inv_pixel_size = (
                1. / pixel_size
            ).to(
                1. / u.radian
            )

            # =================================================
            # Display aktualisieren
            # =================================================

            dm.update_ant_plot(
                (
                    obs.Observatory.ant_pos_EW,
                    obs.Observatory.ant_pos_NS
                )
            )

            dm.update_ant_proj_plot(
                (
                    obs.Observatory.ant_pos_EW,
                    obs.Observatory.ant_pos_NS
                ),
                (
                    obs.HA_START
                    + obs.HA_END
                ) / 2,
                obs.RA_elev
            )

            dm.update_img_plot(
                obs.SkyImage.data,
                pixel_size=pixel_size
            )

            dm.update_fft_plot(
                obs.SkyImage.fft_data
            )

            dm.update_uvc_plot(
                obs.UVC,
                inv_pixel_size=inv_pixel_size
            )

            dm.update_dbe_plot(
                obs.dirty_beam,
                pixel_size=pixel_size
            )

            dm.update_dim_plot(
                obs.dirty_image,
                pixel_size=pixel_size
            )

            dm.update_mft_plot(
                obs.uv_fft_sampled,
                inv_pixel_size=inv_pixel_size
            )

            dm.update_ind_plot(
                la_config.var_dic,
                obs
            )

            dm.update_blit_manager()

            # =================================================
            # Stop überprüfen
            # =================================================

            if stop_event.is_set():
                break

            # CPU etwas entlasten

            sleep(0.01)

    except KeyboardInterrupt:

        print(
            "KeyboardInterrupt received."
        )

    except Exception as e:

        trace = traceback.format_exc()

        print()
        print("==========================================")
        print("ERROR IN MAIN LOOP")
        print("==========================================")
        print(e)
        print(trace)

        logging.exception(
            e
        )

    finally:

        # ====================================================
        # Beobachtung sauber beenden
        # ====================================================

        print()
        print("Observation finished.")

        stop_all_processes()

        # ----------------------------------------------------
        # Matplotlib schließen
        # ----------------------------------------------------

        try:

            plt.close(
                "all"
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Manager schließen
        # ----------------------------------------------------

        try:

            if manager is not None:

                manager.shutdown()

        except Exception as e:

            print(
                "Error shutting down manager:",
                e
            )

        print(
            "Observation completely stopped."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    logging.basicConfig(
        filename="lego_alma.log",
        level=logging.INFO
    )

    print()
    print("==========================================")
    print("LEGO ALMA")
    print("==========================================")
    print()
    print("Opening control GUI...")
    print()

    # ========================================================
    # Create a Manager for shared settings dict
    # ========================================================
    
    main_manager = Manager()
    shared_settings_dict = main_manager.dict()

    # ========================================================
    # GUI
    # ========================================================

    gui = LlaGUI(
        start_callback=start_observation,
        stop_callback=stop_all_processes,
        shared_settings_dict=shared_settings_dict
    )

    # ========================================================
    # GUI starten
    # ========================================================

    gui.run()

    # ========================================================
    # Falls GUI geschlossen wurde
    # ========================================================

    print(
        "GUI closed."
    )

    stop_all_processes()

    print(
        "LEGO ALMA terminated."
    )


# ============================================================
# Programmstart
# ============================================================

if __name__ == "__main__":

    main()
