#!/usr/bin/env python3
"""
run_simulation.py

Lightweight runner to exercise the la_* pipeline with simulated antenna data.

Usage examples:
  # run 5 steps using explicit coordinate sequences
  python scripts/run_simulation.py --mode coords --steps 5 --outdir /tmp/alma_sim

  # run 10 steps using bit-based simulation (uses ant_pos.2.txt mapping)
  python scripts/run_simulation.py --mode bits --steps 10 --outdir /tmp/alma_sim

The script will call the same pipeline functions used by la_main: baselines,
UV coverage, masked FFT and dirty image creation and save outputs per step.
"""
import os
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import astropy.units as u
import logging
from astropy.coordinates import Angle
import astropy.constants as C

# Import project modules (must run from project root)
from la_obs_img import Observatory, SkyImage, Observation
from la_control import Control
import la_config


def recompute_uv_indices(obs):
    """Recompute u/v grid indices from obs.U and obs.V using pixel size and image dims.
    This overrides any prior grid_uv_coverage mapping so we don't modify la_obs_img.py.
    """
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
    """Expand each uv index into a (2*radius+1)^2 patch around it.
    Modifies obs.u and obs.v in-place to include neighboring indices (clamped).
    """
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


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def save_image(arr, fname, cmap='inferno'):
    # ensure real-valued image for plotting
    if np.iscomplexobj(arr):
        arr = np.abs(arr)
    plt.figure(figsize=(6,6))
    plt.imshow(arr, origin='lower', cmap=cmap)
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(fname, dpi=150)
    plt.close()


def run_coords_mode(outdir, steps, img_path, ha_start=-4.0, ha_end=4.0, freq=200.0, decl=-90.0):
    # simple deterministic coordinate sequences for testing
    alma = Observatory(ant_pos_bit_file='./ant_pos.2.txt')
    # No need to load bit file for coords mode, but safe to do so
    try:
        alma.load_ant_pos_bit_file()
    except Exception:
        pass

    # create sky image and observation
    dirpath = os.path.dirname(img_path) or './models/'
    if not dirpath.endswith('/'):
        dirpath += '/'
    imgobj = SkyImage(path=dirpath, filename=os.path.basename(img_path))
    imgobj.load_image()
    imgobj.make_invert()

    cont = Control(ctrl_id='SIM')
    cont.add_buttons()
    cont.set_but_bit_dict_file('but_dict.pickle')
    try:
        cont.load_but_bit_dict()
    except Exception:
        pass
    cont.set_swi_bit_list(la_config.swi_bits)

    obs = Observation(alma, imgobj, cont, obs_frequency=freq*u.GHz, var_dic=la_config.var_dic)
    # apply user-specified observation parameters (bypass hardware controller)
    obs.HA_START = Angle(ha_start, u.hour)
    obs.HA_END = Angle(ha_end, u.hour)
    obs.obs_frequency = freq * u.GHz
    obs.obs_lam = C.c / obs.obs_frequency
    obs.SkyImage.declination = decl * u.deg
    obs.calc_el_curve()

    # generate a few synthetic antenna configurations
    rng = np.random.default_rng(42)
    n_ant = 6
    for i in range(steps):
        # jitter positions around a small layout
        ew = np.linspace(0, 10, n_ant) + rng.normal(scale=1.0, size=n_ant)
        ns = np.linspace(0, -5, n_ant) + rng.normal(scale=1.0, size=n_ant)
        alma.ant_pos_EW = np.array(ew)
        alma.ant_pos_NS = np.array(ns)
        alma.ant_pos_X = -1 * alma.ant_pos_NS * np.sin(alma.latitude)
        alma.ant_pos_Y = alma.ant_pos_EW
        alma.ant_pos_Z = alma.ant_pos_NS * np.cos(alma.latitude)

        alma.make_baselines()
        obs.calc_el_curve()
        obs.make_uv_coverage()
        obs.grid_uv_coverage()
        # recompute indices robustly here, without editing la_obs_img.py
        recompute_uv_indices(obs)
        # expand uv sampling to a small patch to reduce severe aliasing when sparse
        expand_uv_indices(obs, radius=1)
        obs.make_masked_arr()
        obs.make_dirty_arr()

        # save outputs
        step_dir = os.path.join(outdir, f'step_{i:03d}')
        ensure_dir(step_dir)
        np.save(os.path.join(step_dir, 'dirty_image.npy'), obs.dirty_image)
        np.save(os.path.join(step_dir, 'uv_coverage.npy'), obs.UVC)
        save_image(obs.dirty_image, os.path.join(step_dir, 'dirty_image.png'))
        print(f'[coords] saved step {i} → {step_dir}')


def run_bits_mode(outdir, steps, img_path, use_bits_count=6):
    alma = Observatory(ant_pos_bit_file='./ant_pos.2.txt')
    alma.load_ant_pos_bit_file()

    # extract available bit ids
    bit_ids = list(alma._ant_bit_dict.keys())
    if len(bit_ids) == 0:
        raise RuntimeError('No antenna bit mapping loaded from ant_pos.2.txt')

    dirpath = os.path.dirname(img_path) or './models/'
    if not dirpath.endswith('/'):
        dirpath += '/'
    imgobj = SkyImage(path=dirpath, filename=os.path.basename(img_path))
    imgobj.load_image()
    imgobj.make_invert()

    cont = Control(ctrl_id='SIM')
    cont.add_buttons()
    cont.set_swi_bit_list(la_config.swi_bits)

    obs = Observation(alma, imgobj, cont, obs_frequency=200*u.GHz, var_dic=la_config.var_dic)
    # default observation params; can be adjusted later by passing args in main
    obs.calc_el_curve()

    rng = np.random.default_rng(1)
    for i in range(steps):
        # pick a random subset of bits to simulate antennas present
        k = min(use_bits_count, len(bit_ids))
        selected = rng.choice(bit_ids, size=k, replace=False)
        fake_last = {'/dev/ttyUSB0': np.array(selected)}
        alma.set_read_source_ids(['/dev/ttyUSB0'])
        alma.set_ant_pos(fake_last)
        alma.make_baselines()

        obs.calc_el_curve()
        obs.make_uv_coverage()
        obs.grid_uv_coverage()
        recompute_uv_indices(obs)
        expand_uv_indices(obs, radius=1)
        obs.make_masked_arr()
        obs.make_dirty_arr()

        step_dir = os.path.join(outdir, f'step_{i:03d}')
        ensure_dir(step_dir)
        np.save(os.path.join(step_dir, 'dirty_image.npy'), obs.dirty_image)
        np.save(os.path.join(step_dir, 'uv_coverage.npy'), obs.UVC)
        save_image(obs.dirty_image, os.path.join(step_dir, 'dirty_image.png'))
        print(f'[bits] saved step {i} (bits={selected.tolist()}) → {step_dir}')


def main():
    parser = argparse.ArgumentParser(description='Run la_* pipeline with simulated antenna data')
    parser.add_argument('--mode', choices=['coords', 'bits'], default='coords')
    parser.add_argument('--steps', type=int, default=5)
    parser.add_argument('--outdir', type=str, default='./sim_outputs')
    parser.add_argument('--img', type=str, default='./models/galaxy_lobes.png')
    parser.add_argument('--bits-count', type=int, default=6,
                        help='number of antenna bits to choose when in bits mode')
    parser.add_argument('--ha-start', type=float, default=-4.0, help='HA start (hours)')
    parser.add_argument('--ha-end', type=float, default=4.0, help='HA end (hours)')
    parser.add_argument('--freq', type=float, default=200.0, help='observing frequency in GHz')
    parser.add_argument('--decl', type=float, default=-90.0, help='source declination in degrees')
    args = parser.parse_args()

    ensure_dir(args.outdir)

    logging.basicConfig(level=logging.INFO)
    print('Starting simulation runner, mode=', args.mode)

    if args.mode == 'coords':
        run_coords_mode(args.outdir, args.steps, args.img, ha_start=args.ha_start, ha_end=args.ha_end, freq=args.freq, decl=args.decl)
    else:
        run_bits_mode(args.outdir, args.steps, args.img, use_bits_count=args.bits_count)


if __name__ == '__main__':
    main()
