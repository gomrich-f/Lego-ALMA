#!/usr/bin/env python3
"""
simulate_controller.py

Simuliert einen angeschlossenen Controller: erzeugt ein `last_measurements` dict
mit Antennen‑Bitlisten und Controller‑Bits und füttert damit die bestehenden
`la_`-Module (Observatory, Observation, Control) wie in `la_main`.

Das Skript ist headless und speichert pro Schritt die `dirty_image.npy` und
`uv_coverage.npy` sowie `dirty_image.png` in `--outdir`.
"""
import os
import argparse
import time
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import Angle
import astropy.constants as C

from la_obs_img import Observatory, SkyImage, Observation
from la_control import Control
import la_config


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def save_image(arr, fname, cmap='inferno'):
    if np.iscomplexobj(arr):
        arr = np.abs(arr)
    plt.figure(figsize=(6,6))
    plt.imshow(arr, origin='lower', cmap=cmap)
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(fname, dpi=150)
    plt.close()


def recompute_uv_indices(obs):
    try:
        px = obs.SkyImage.pixel_size.to(u.radian).value
        imx = obs.SkyImage.imsize_X
        imy = obs.SkyImage.imsize_Y
        Uarr = np.array(obs.U)
        Varr = np.array(obs.V)
        u_flat = Uarr.flatten()
        v_flat = Varr.flatten()
        u_idx = np.round(u_flat * px * imx + imx / 2.0).astype(int)
        v_idx = np.round(v_flat * px * imy + imy / 2.0).astype(int)
        shape0 = int(imx) if hasattr(imx, '__int__') else int(obs.SkyImage.fft_data.shape[0])
        shape1 = int(imy) if hasattr(imy, '__int__') else int(obs.SkyImage.fft_data.shape[1])
        mask = (u_idx >= 0) & (u_idx < shape0) & (v_idx >= 0) & (v_idx < shape1)
        u_idx = u_idx[mask]
        v_idx = v_idx[mask]
        obs.u = np.array(u_idx, dtype=np.int16)
        obs.v = np.array(v_idx, dtype=np.int16)
    except Exception:
        return


def expand_uv_indices(obs, radius=1):
    try:
        if not hasattr(obs, 'u') or not hasattr(obs, 'v'):
            return
        u0 = np.array(obs.u, dtype=int)
        v0 = np.array(obs.v, dtype=int)
        if u0.size == 0:
            return
        shape0 = obs.SkyImage.fft_data.shape[0]
        shape1 = obs.SkyImage.fft_data.shape[1]
        new_u = []
        new_v = []
        for uu, vv in zip(u0, v0):
            for dx in range(-radius, radius+1):
                for dy in range(-radius, radius+1):
                    nu = uu + dx
                    nv = vv + dy
                    if 0 <= nu < shape0 and 0 <= nv < shape1:
                        new_u.append(nu)
                        new_v.append(nv)
        if len(new_u) > 0:
            obs.u = np.array(new_u, dtype=np.int16)
            obs.v = np.array(new_v, dtype=np.int16)
    except Exception:
        return


def main():
    parser = argparse.ArgumentParser(description='Simulate controller and antenna data for la_* pipeline')
    parser.add_argument('--steps', type=int, default=10)
    parser.add_argument('--outdir', type=str, default='./sim_ctrl_outputs')
    parser.add_argument('--img', type=str, default='./models/galaxy_lobes.png')
    parser.add_argument('--bits-count', type=int, default=6, help='how many antenna bits active per step')
    parser.add_argument('--ha-start', type=float, default=-4.0, help='HA start (hours)')
    parser.add_argument('--ha-end', type=float, default=4.0, help='HA end (hours)')
    parser.add_argument('--freq', type=float, default=200.0, help='observing frequency in GHz')
    parser.add_argument('--decl', type=float, default=-90.0, help='source declination in degrees')
    parser.add_argument('--rand-seed', type=int, default=0)
    parser.add_argument('--playback', type=str, default=None, help='CSV file with playback rows (time,usb0_bits,usb1_bits)')
    args = parser.parse_args()

    ensure_dir(args.outdir)

    alma = Observatory(ant_pos_bit_file='./ant_pos.2.txt')
    # load mapping from bits -> positions
    alma.vlbi_mode = False
    try:
        alma.load_ant_pos_bit_file()
    except Exception:
        pass

    # sky image
    dirpath = os.path.dirname(args.img) or './models/'
    if not dirpath.endswith('/'):
        dirpath += '/'
    imgobj = SkyImage(path=dirpath, filename=os.path.basename(args.img))
    imgobj.load_image()
    imgobj.make_invert()

    # controller wrapper
    cont = Control(ctrl_id='/dev/ttyUSB1')
    cont.add_buttons()
    try:
        cont.set_but_bit_dict_file('but_dict.pickle')
        cont.load_but_bit_dict()
    except Exception:
        pass
    cont.set_swi_bit_list(la_config.swi_bits)

    obs = Observation(alma, imgobj, cont, obs_frequency=args.freq * u.GHz, var_dic=la_config.var_dic)
    obs.HA_START = Angle(args.ha_start, u.hour)
    obs.HA_END = Angle(args.ha_end, u.hour)
    obs.obs_frequency = args.freq * u.GHz
    obs.obs_lam = C.c / obs.obs_frequency
    obs.SkyImage.declination = args.decl * u.deg
    obs.calc_el_curve()

    rng = np.random.default_rng(args.rand_seed)
    bit_ids = []
    try:
        bit_ids = list(alma._ant_bit_dict.keys())
    except Exception:
        # fallback: use a reasonable set of bit indices
        bit_ids = list(range(1,33))

    alma.set_read_source_ids(['/dev/ttyUSB0'])

    # Playback mode: read rows from CSV (time,usb0_bits,usb1_bits)
    if args.playback is not None:
        import csv
        rows = []
        with open(args.playback, 'r') as fin:
            rdr = csv.DictReader(fin)
            for r in rdr:
                rows.append(r)
        total = min(len(rows), args.steps if args.steps is not None else len(rows))
        iter_rows = rows[:total]
    else:
        iter_rows = [None] * args.steps

    for i, row in enumerate(iter_rows):
        if row is None:
            # pick a random subset of antenna bits (simulate antennas present)
            k = min(args.bits_count, len(bit_ids))
            selected = rng.choice(bit_ids, size=k, replace=False)
            # create control bits: include some switch bits (S0,S1,S2) sometimes
            swi = la_config.swi_bits
            ctrl_bits = []
            if i % 5 == 0:
                ctrl_bits += [swi[0]]
            last_measurements = {
                '/dev/ttyUSB0': np.array(selected, dtype=int),
                '/dev/ttyUSB1': np.array(ctrl_bits, dtype=int)
            }
        else:
            # parse playback row
            def parse_bits(s):
                if s is None:
                    return np.array([], dtype=int)
                s = s.strip()
                if s == '' or s.lower() == 'none':
                    return np.array([], dtype=int)
                parts = [p for p in s.replace(';', ',').split(',') if p != '']
                try:
                    return np.array([int(p) for p in parts], dtype=int)
                except Exception:
                    return np.array([], dtype=int)

            usb0 = parse_bits(row.get('usb0_bits') or row.get('usb0') or '')
            usb1 = parse_bits(row.get('usb1_bits') or row.get('usb1') or '')
            last_measurements = {
                '/dev/ttyUSB0': usb0,
                '/dev/ttyUSB1': usb1
            }

        # feed to observatory and observation as la_main would
        alma.set_ant_pos(last_measurements)
        alma.make_baselines()

        # let observation read controller state (updates buffers / images if S0 set)
        try:
            obs.update_obs_from_control(last_measurements, video_stream=None)
        except Exception:
            pass

        obs.calc_el_curve()
        obs.make_uv_coverage()
        obs.grid_uv_coverage()

        recompute_uv_indices(obs)
        expand_uv_indices(obs, radius=1)

        obs.make_masked_arr()
        obs.make_dirty_arr()

        # save
        step_dir = os.path.join(args.outdir, f'step_{i:03d}')
        ensure_dir(step_dir)
        np.save(os.path.join(step_dir, 'dirty_image.npy'), obs.dirty_image)
        np.save(os.path.join(step_dir, 'uv_coverage.npy'), obs.UVC)
        save_image(obs.dirty_image, os.path.join(step_dir, 'dirty_image.png'))
        bits_list = last_measurements.get('/dev/ttyUSB0')
        try:
            bits_display = bits_list.tolist()
        except Exception:
            bits_display = list(bits_list)
        print(f'[sim_ctrl] step {i} saved -> {step_dir} (bits={bits_display})')
        time.sleep(0.1)


if __name__ == '__main__':
    main()
