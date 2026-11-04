#!/usr/bin/env python3
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

if len(sys.argv) < 2:
    print('Usage: show_uv.py <step_dir>')
    sys.exit(1)
step_dir = sys.argv[1]
uvf = os.path.join(step_dir, 'uv_coverage.npy')
if not os.path.exists(uvf):
    print('uv file not found:', uvf)
    sys.exit(1)
uvc = np.load(uvf)
plt.figure(figsize=(6,6))
plt.imshow(uvc, origin='lower', cmap='viridis')
plt.colorbar()
plt.title('UVC (sampling grid)')
plt.tight_layout()
out = os.path.join(step_dir, 'uvc_vis.png')
plt.savefig(out, dpi=150)
print('Saved', out)
