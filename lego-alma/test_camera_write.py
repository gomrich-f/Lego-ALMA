#!/usr/bin/env python3
"""Test script to debug Misc4.jpg writing - direct execution."""

import sys
sys.path.insert(0, '.')

import cv2
import numpy as np
import time
import os

# Clean up old test file
if os.path.exists('./Misc4_direct_test.jpg'):
    os.remove('./Misc4_direct_test.jpg')

print("Direct test: writing to ./Misc4_direct_test.jpg\n")

test_array = np.random.randint(0, 256, (480, 480), dtype=np.uint8)

print(f"Array shape: {test_array.shape}")
print(f"Array dtype: {test_array.dtype}")

tmpname = './Misc4_direct_test.jpg.tmp'
outname = './Misc4_direct_test.jpg'

print(f"\nWriting to temp file: {tmpname}")
ret = cv2.imwrite(tmpname, test_array)
print(f"cv2.imwrite() returned: {ret}")
print(f"Temp file exists: {os.path.exists(tmpname)}")

if os.path.exists(tmpname):
    size = os.path.getsize(tmpname)
    print(f"Temp file size: {size} bytes")
    
    print(f"\nRenaming to: {outname}")
    try:
        os.replace(tmpname, outname)
        print("rename succeeded")
    except Exception as e:
        print(f"rename failed: {e}")
        cv2.imwrite(outname, test_array)
        print("wrote directly instead")

print(f"\nFinal file exists: {os.path.exists(outname)}")
if os.path.exists(outname):
    size = os.path.getsize(outname)
    print(f"Final file size: {size} bytes")
    print("✓ SUCCESS\n")
else:
    print("✗ FAILED\n")

# Now test with real camera
print("\n" + "="*60)
print("Now testing with real camera frames (10 seconds)...")
print("="*60 + "\n")

from multiprocessing import Manager, Process
from la_reader_new import VideoReadController

manager = Manager()
video_dict = manager.dict()

vid_controller = VideoReadController()

pv = Process(
    target=vid_controller.read_vid,
    args=(video_dict,)
)

pv.start()

# Monitor for 10 seconds
for i in range(10):
    time.sleep(1)
    
    misc_exists = os.path.exists('./Misc4.jpg')
    val_in_dict = 'val' in video_dict
    frame_shape = video_dict.get('_frame_shape', 'N/A')
    cam_open = video_dict.get('_cam_open', False)
    
    print(f"[{i+1}s] cam_open={cam_open}, val in dict={val_in_dict}, "
          f"frame_shape={frame_shape}, Misc4.jpg exists={misc_exists}")
    
    if misc_exists:
        size = os.path.getsize('./Misc4.jpg')
        mtime = os.path.getmtime('./Misc4.jpg')
        print(f"       → Misc4.jpg: {size} bytes, modified {time.strftime('%H:%M:%S', time.localtime(mtime))}")

try:
    video_dict['_stop'] = True
except Exception:
    pass

pv.terminate()
pv.join(timeout=2)
if pv.is_alive():
    pv.kill()
    pv.join()

manager.shutdown()

print("\n" + "="*60)
print("Final check")
print("="*60 + "\n")

if os.path.exists('./Misc4.jpg'):
    size = os.path.getsize('./Misc4.jpg')
    print(f"✓ ./Misc4.jpg exists (size: {size} bytes)")
else:
    print("✗ ./Misc4.jpg does not exist")

print("Done.\n")
