import serial
from time import sleep
import glob
from serial.tools.list_ports import comports
import numpy as np
import cv2
import time
import os


class VideoReadController:
    def __init__(self, resolution=(480, 480)):
        self.resolution = resolution

    def read_vid(self, shared_var):
        # Try to open a video capture device; try indices 0..3 and pick first working
        VidObj = None

        # Build candidate device index list: prefer USB devices from /dev/video* (sysfs path contains 'usb')
        candidates = []
        try:
            devs = sorted(glob.glob('/dev/video*'))
            dev_indices = []
            for d in devs:
                try:
                    n = int(os.path.basename(d).replace('video', ''))
                    dev_indices.append(n)
                except Exception:
                    continue

            usb_list = []
            other_list = []
            for n in dev_indices:
                try:
                    sys_path = f"/sys/class/video4linux/video{n}/device"
                    real = os.path.realpath(sys_path)
                    if 'usb' in real.lower():
                        usb_list.append(n)
                    else:
                        other_list.append(n)
                except Exception:
                    other_list.append(n)

            # candidates: USB first, then others
            candidates = usb_list + other_list
        except Exception:
            candidates = []

        # always append a small index fallback set (0..3) to handle systems without /dev/video entries
        for i in range(4):
            if i not in candidates:
                candidates.append(i)

        # try candidates in order
        VidObj = None
        for idx in candidates:
            try:
                cap = cv2.VideoCapture(idx)
            except Exception:
                cap = None

            if cap is None:
                continue

            if not cap.isOpened():
                try:
                    cap.release()
                except Exception:
                    pass
                continue

            # request desired resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.resolution[0]))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.resolution[1]))

            # try one read to verify
            ret, frame = cap.read()

            if ret and frame is not None:
                VidObj = cap
                try:
                    shared_var['_cam_index'] = idx
                    shared_var['_cam_open'] = True
                    shared_var['_device_candidates'] = candidates
                except Exception:
                    pass
                break
            else:
                try:
                    cap.release()
                except Exception:
                    pass

        if VidObj is None:
            print("Could not open any webcam (indices 0-3).")
            return

        # Continuous read loop: center-crop or pad to target resolution, publish as 2D uint8
        target_h, target_w = int(self.resolution[0]), int(self.resolution[1])

        while True:

            # support external stop flag in shared_var
            try:
                if shared_var.get('_stop', False):
                    break
            except Exception:
                pass

            ret, frame = VidObj.read()

            if not ret or frame is None:
                sleep(0.05)
                continue

            # convert to grayscale if needed
            if frame.ndim == 3:
                try:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                except Exception:
                    # fallback: take one channel
                    frame = frame[..., 0]

            frame = np.asarray(frame).astype(np.uint8)

            h, w = frame.shape

            # center crop or pad to requested resolution
            if h >= target_h:
                minx = (h - target_h) // 2
                maxx = minx + target_h
                vert = frame[minx:maxx, :]
            else:
                vert = frame

            if w >= target_w:
                miny = (w - target_w) // 2
                maxy = miny + target_w
                cropped = vert[:, miny:maxy]
            else:
                cropped = vert

            ch, cw = cropped.shape
            if ch != target_h or cw != target_w:
                pad_h = max(0, target_h - ch)
                pad_w = max(0, target_w - cw)
                pad_top = pad_h // 2
                pad_bottom = pad_h - pad_top
                pad_left = pad_w // 2
                pad_right = pad_w - pad_left
                cropped = np.pad(
                    cropped,
                    ((pad_top, pad_bottom), (pad_left, pad_right)),
                    mode='constant',
                    constant_values=0
                )

            try:
                # publish frame and some debug info
                shared_var['val'] = cropped
                try:
                    shared_var['_frame_shape'] = cropped.shape
                except Exception:
                    pass
                try:
                    shared_var['_val_ready'] = True
                except Exception:
                    pass
                # also set a lightweight debug flag for parent visibility
                try:
                    shared_var['_debug_cam'] = f"frame from idx {shared_var.get('_cam_index', 'unknown')}"
                except Exception:
                    pass

                # periodically write to disk so other code can read Misc4.jpg
                try:
                    # write at most every 0.5s
                    last_save = shared_var.get('_last_save_ts', 0)
                    now = time.time()
                    if now - last_save > 0.5:
                        out = cropped.copy()
                        tmpname = './Misc4.jpg.tmp'
                        outname = './Misc4.jpg'
                        cv2.imwrite(tmpname, out)
                        try:
                            os.replace(tmpname, outname)
                        except Exception:
                            cv2.imwrite(outname, out)
                        shared_var['_last_save_ts'] = now
                except Exception:
                    pass
            except Exception:
                # if Manager dict can't handle large writes, skip
                pass

            sleep(0.02)

        try:
            VidObj.release()
        except Exception:
            pass


class Reader:

    def __init__(self):

        self.ser_conn_dict = dict()
        # buffer for continuous byte stream parsing
        self._recv_buffer = bytearray()

    # ============================================================
    # SERIAL CONNECTION
    # ============================================================

    def create_ser_conn(
        self,
        path='/dev/ttyACM1',
        baud=9600,
        timeout=1,
        parity=serial.PARITY_NONE,
        rtscts=False,
        auto_search_free=True
    ):

        print("Creating connection to " + path)

        print("Existing ports:")

        port_list = comports()

        for port in port_list:
            print(port)

        # --------------------------------------------------------
        # Try requested port
        # --------------------------------------------------------

        if path in [_p.device for _p in port_list]:

            try:

                self.ser_conn_dict = {
                    'info': [
                        path,
                        baud,
                        timeout,
                        parity,
                        rtscts
                    ],

                    'connection': serial.Serial(
                        path,
                        baud,
                        timeout=timeout,
                        parity=parity,
                        rtscts=rtscts,
                        exclusive=True
                    )
                }

                print("Connected to " + path)

                return 1

            except Exception as e:

                print(
                    "Could not open",
                    path,
                    ":",
                    e
                )

        # --------------------------------------------------------
        # Automatically search for another USB port
        # --------------------------------------------------------

        if auto_search_free:

            print(
                "Path "
                + path
                + " not found, looking for next"
            )


            prefixes = ['/dev/ttyACM', '/dev/ttyUSB']

            for prefix in prefixes:
                for i in range(10):

                    try:

                        test_path = f'{prefix}{i}'

                        self.ser_conn_dict = {
                            'info': [
                                test_path,
                                baud,
                                timeout,
                                parity,
                                rtscts
                            ],

                            'connection': serial.Serial(
                                test_path,
                                baud,
                                timeout=timeout,
                                parity=parity,
                                rtscts=rtscts,
                                exclusive=True
                            )
                        }

                        print(
                            "Connected to",
                            test_path
                        )

                        return i

                    except Exception as e:

                        print(
                            i,
                            e,
                            "can't connect to this port, trying next"
                        )

            print("No serial ports found.")

            return 0

        return 0

    # ============================================================
    # READ BUTTON CONTROLLER
    # ============================================================

    def scan_ser_conn(
        self,
        return_raw_string=False,
        print_raw_string=False,
        shared_var=None
    ):
        try:
            # Read up to 1024 bytes (timeout on Serial will bound this)
            linein = self.ser_conn_dict['connection'].read(1024)

        except Exception as e:
            debug_msg = f"scan_ser_conn: serial I/O error: {e}"
            if shared_var is not None:
                shared_var['_debug'] = debug_msg
            return np.array([], dtype=int)

        # Append received raw bytes into rolling buffer
        if linein:
            self._recv_buffer.extend(linein)

        # Log to shared dict so parent can see
        if shared_var is not None:
            debug_msg = (
                f"scan_ser_conn: bytes_buffered={len(self._recv_buffer)}, "
                f"last_recv={len(linein) if linein else 0}"
            )
            shared_var['_debug'] = debug_msg

        # Frame format: [0]=0xAA, [1]=0x55, [2..9]=8 data bytes, [10]=0xFF
        START_SEQ = b"\xAA\x55"
        END_BYTE = 0xFF

        # Process all complete frames in the buffer; return positions from the
        # last complete frame parsed in this call (keeps compatibility).
        buf = self._recv_buffer
        last_bit_pos = None
        frames_parsed = 0

        while True:

            start = buf.find(START_SEQ)

            if start == -1:
                break

            # Not enough data yet for a full frame
            if len(buf) < start + 11:
                break

            # If end byte not present at expected location, discard up to start+1
            if buf[start + 10] != END_BYTE:
                del buf[:start + 1]
                continue

            # Extract payload (8 bytes)
            payload = bytes(buf[start + 2:start + 10])

            # Remove processed frame from buffer
            del buf[:start + 11]

            # Convert payload bytes to a bit string (MSB first per byte)
            bit_string = ''.join(f"{b:08b}" for b in payload)

            # Optionally print or return raw bit string
            if print_raw_string:
                print(bit_string)

            if return_raw_string:
                # If multiple frames, return the last bit string
                last_bit_pos = bit_string
            else:
                last_bit_pos = np.where(np.array([bit == '1' for bit in bit_string]))[0]

            frames_parsed += 1

        # Trim buffer if it grows too large
        if len(buf) > 8192:
            del buf[:-2048]

        # If we parsed at least one frame, return the last parsed positions/string
        if frames_parsed > 0:
            if return_raw_string:
                return last_bit_pos
            else:
                return last_bit_pos if last_bit_pos is not None else np.array([], dtype=int)

        # No complete frame parsed
        return np.array([], dtype=int)

    # ============================================================
    # DISCONNECT SERIAL
    # ============================================================

    def disconnect_ser(self):

        try:

            self.ser_conn_dict['connection'].close()

        except Exception:
            pass

        self.ser_conn_dict = {}


class ReadController:

    def __init__(self, sleep_time=0.05):

        self.sleep_time = sleep_time

    # ============================================================
    # SERIAL READING LOOP
    # ============================================================

    def _loop_read(
        self,
        shared_var,
        conn_details,
        connection_type,
        sleep_time=None,
        verbose=False
    ):

        if sleep_time is None:
            sleep_time = self.sleep_time

        # --------------------------------------------------------
        # SERIAL
        # --------------------------------------------------------

        if connection_type == 'ser':

            print("[DEBUG _loop_read] STARTING SERIAL READER")
            print("[DEBUG _loop_read] conn_details:", conn_details)

            reader = Reader()

            print("[DEBUG _loop_read] Reader object created")

            result = reader.create_ser_conn(
                **conn_details
            )

            print("[DEBUG _loop_read] create_ser_conn returned:", result)
            print("[DEBUG _loop_read] ser_conn_dict:", reader.ser_conn_dict)

            # Write an initial presence marker into the shared dict so the
            # parent process can detect that this reader started (may be
            # helpful if the reader fails later or prints are not visible).
            try:
                key = reader.ser_conn_dict.get('info', [conn_details.get('path', 'unknown')])[0]
                shared_var[key] = np.array([], dtype=int)
                print("ReadController: registered reader key", key)
            except Exception as e:
                print("ReadController: could not register reader key:", e)

            print("[DEBUG _loop_read] Entering read loop...")

            loop_counter = 0
            while True:

                sleep(sleep_time)

                loop_counter += 1

                # Register loop iteration in shared dict
                shared_var['_loop_count'] = f"Loop {loop_counter}"

                try:

                    val = reader.scan_ser_conn(
                        shared_var=shared_var
                    )

                    shared_var[
                        reader.ser_conn_dict['info'][0]
                    ] = val

                    # Log successful reads
                    if len(val) > 0:
                        shared_var['_debug_bits'] = f"Loop {loop_counter}: got {len(val)} bits: {list(val)}"
                    else:
                        shared_var['_debug_empty'] = f"Loop {loop_counter}: empty read"

                    if verbose:

                        print(
                            val,
                            shared_var,
                            '#'
                        )

                except Exception as e:

                    shared_var['_debug_error'] = f"Loop {loop_counter}: {str(e)}"

                    print(
                        "ser ctrl error!",
                        conn_details,
                        e
                    )

                    pass

            reader.disconnect_ser()

        # --------------------------------------------------------
        # Unknown connection type
        # --------------------------------------------------------

        else:

            print(
                "Unknown connection type:",
                connection_type
            )

            print(
                "Only 'ser' is supported."
            )