# %%
import astropy.units as u
import numpy as np
from astropy.coordinates import Angle
import astropy.constants as C
from PIL import Image
from astropy.io import ascii
import traceback
import logging
from scipy.ndimage import gaussian_filter
from tqdm import tqdm
from time import sleep
import pickle


# ============================================================
# Observatory
# ============================================================

class Observatory:

    def __init__(
        self,
        name="ALMA",
        latitude=-23.0229 * u.deg,
        longitude=-67.755 * u.deg,
        ant_pos_EW=[],
        ant_pos_NS=[],
        ant_pos_bit_file='./ant_pos.2.txt'
    ):

        self.latitude = latitude
        self.longitude = longitude

        # Antennenpositionen
        self.ant_pos_EW = np.array(
            ant_pos_EW,
            dtype=float
        )

        self.ant_pos_NS = np.array(
            ant_pos_NS,
            dtype=float
        )

        self.vlbi_mode = False

        # ----------------------------------------------------
        # Kartesische Koordinaten
        # ----------------------------------------------------

        _lat_rad = self.latitude.to(u.radian).value

        sin_lat = np.sin(_lat_rad)
        cos_lat = np.cos(_lat_rad)

        self.ant_pos_X = (
            -1 * self.ant_pos_NS * sin_lat
        )

        self.ant_pos_Y = self.ant_pos_EW

        self.ant_pos_Z = (
            self.ant_pos_NS * cos_lat
        )

        self.ant_pos_bit_file = ant_pos_bit_file

        self.scale_factor = 2

    # ========================================================
    # Antennenpositionen laden
    # ========================================================

    def load_ant_pos_bit_file(
        self,
        ant_pos_bit_file=None,
        center_coords=(115. / 2, 115. / 2),
        scale_factor=2
    ):
        print("\n==============================")
        print("Loading antenna position file")
        print("==============================")

        self.scale_factor = scale_factor

        if ant_pos_bit_file is None:

            ant_file_data = ascii.read(
                self.ant_pos_bit_file
            )

        else:

            ant_file_data = ascii.read(
                ant_pos_bit_file
            )

        print(
            "Antenna position file loaded:"
        )

        print(ant_file_data)

        # build robust mapping: convert bits to ints, compute centered positions
        bits = np.array(ant_file_data['bit'], dtype=int)
        posx = (ant_file_data['posx'] - center_coords[0]) * scale_factor
        posy = -(ant_file_data['posy'] - center_coords[1]) * scale_factor

        # detect duplicate bit IDs
        unique_bits, counts = np.unique(bits, return_counts=True)
        dup_bits = unique_bits[counts > 1]
        if dup_bits.size > 0:
            print("WARNING: duplicate bit IDs found in antenna position file:", dup_bits)
            for db in dup_bits:
                rows = np.nonzero(bits == db)[0]
                print(f" bit {db} appears at rows: {rows}")

        # create mapping, keep first occurrence for any duplicate bit
        ant_bit_dict = {}
        for ii, b in enumerate(bits):
            bi = int(b)
            if bi in ant_bit_dict:
                # already mapped, skip duplicate
                continue
            ant_bit_dict[bi] = (float(posx[ii]), float(posy[ii]))

        self._ant_bit_dict = ant_bit_dict

        print("Antenna bit dictionary:")
        print(self._ant_bit_dict)

    # ========================================================
    # Read source IDs
    # ========================================================

    def set_read_source_ids(self, src_list):

        self._read_source_list = src_list

        print(
            "Read source list:",
            self._read_source_list
        )

    # ========================================================
    # Set antenna positions
    # ========================================================

    def set_ant_pos(self, last_measurements):

        print("\n==============================")
        print("Updating antenna positions")
        print("==============================")

        # start with an empty 2x0 float array for stacking (EW, NS)
        pos = np.empty((2, 0), dtype=float)

        try:

            for src in self._read_source_list:

                print(
                    "Checking source:",
                    src
                )
                # Accept keys for Arduino/serial devices ('USB', 'ACM', or '/dev/*')
                if ('USB' in src) or ('ACM' in src) or (isinstance(src, str) and src.startswith('/dev')):

                    try:
                        bit_array = last_measurements[src]
                    except Exception:
                        # no data for this source yet
                        continue

                    print(
                        "Serial bit array:",
                        bit_array
                    )

                    # If no antenna bits present, skip
                    if len(bit_array) < 1:
                        continue

                    try:

                        new_positions = np.array(
                            [
                                np.array(
                                    self._ant_bit_dict.get(int(bit), (None, None))
                                )
                                for bit in bit_array
                                if int(bit) in self._ant_bit_dict
                            ]
                        )

                        if new_positions.size == 0:
                            # no valid bits mapping to antenna positions
                            continue

                        # Ensure shape is (2, N)
                        new_positions = new_positions.T

                        print(
                            "Serial antenna positions:",
                            new_positions.shape
                        )

                        pos = np.hstack(
                            (
                                pos,
                                new_positions
                            )
                        )

                    except Exception as e:

                        print(
                            "ERROR converting serial positions:"
                        )

                        print(e)

                        traceback.print_exc()

            # ------------------------------------------------
            # BLE / Decawave
            # ------------------------------------------------

            if self.vlbi_mode is True:

                print(
                    "VLBI mode active"
                )

                for src in last_measurements:

                    if src.startswith('DW'):

                        try:

                            transformed = self.apply_transform(
                                last_measurements[src][:-1]
                            )

                            print(
                                "BLE transformed:",
                                transformed
                            )

                            pos = np.hstack(
                                [
                                    pos,
                                    transformed[
                                        np.newaxis
                                    ].T
                                ]
                            )

                        except Exception as e:

                            print(
                                "set_ant_pos BLE error:",
                                e
                            )

        except Exception as e:

            print(
                "ERROR in set_ant_pos:"
            )

            print(e)

            traceback.print_exc()

        # ----------------------------------------------------
        # Convert to numpy arrays
        # ----------------------------------------------------

        try:

            self.ant_pos_EW = np.array(
                pos[0],
                dtype=float
            )

            self.ant_pos_NS = np.array(
                pos[1],
                dtype=float
            )

        except Exception as e:

            print(
                "ERROR converting antenna positions:"
            )

            print(e)

            self.ant_pos_EW = np.array(
                [],
                dtype=float
            )

            self.ant_pos_NS = np.array(
                [],
                dtype=float
            )

        print(
            "Final EW:",
            self.ant_pos_EW,
            "shape:",
            self.ant_pos_EW.shape
        )

        print(
            "Final NS:",
            self.ant_pos_NS,
            "shape:",
            self.ant_pos_NS.shape
        )

        # ----------------------------------------------------
        # Cartesian coordinates
        # ----------------------------------------------------

        _lat_rad = self.latitude.to(
            u.radian
        ).value

        sin_lat = np.sin(_lat_rad)
        cos_lat = np.cos(_lat_rad)

        self.ant_pos_X = (
            -1
            * self.ant_pos_NS
            * sin_lat
        )

        self.ant_pos_Y = self.ant_pos_EW

        self.ant_pos_Z = (
            self.ant_pos_NS
            * cos_lat
        )

        print(
            "Cartesian antenna positions:"
        )

        print(
            "X:",
            self.ant_pos_X,
            self.ant_pos_X.shape
        )

        print(
            "Y:",
            self.ant_pos_Y,
            self.ant_pos_Y.shape
        )

        print(
            "Z:",
            self.ant_pos_Z,
            self.ant_pos_Z.shape
        )

    # ========================================================
    # BLE calibration
    # ========================================================

    def set_3pos_tag_single(
        self,
        last_measurements,
        tag_id
    ):

        X_vecs = []

        print(
            "Aligning tags with ALMA"
        )

        for ii in [
            'red',
            'orange',
            'green'
        ]:

            input(
                "Place tag "
                + tag_id
                + " at the "
                + ii
                + " pad and press Enter"
            )

            temp_vec = []

            with tqdm(
                total=40,
                desc="Collecting position data",
                unit="tag positions"
            ):

                while len(temp_vec) < 40:

                    sleep(0.2)

                    try:

                        data_in = (
                            last_measurements[
                                tag_id
                            ][:-1]
                        )

                        if data_in is not None:

                            temp_vec.append(
                                data_in
                            )

                    except KeyError:

                        pass

            temp_vec = np.median(
                temp_vec,
                axis=0
            )

            X_vecs.append(
                temp_vec
            )

        self.X_vecs = X_vecs

    # ========================================================

    def set_3pos_tag_all(
        self,
        last_measurements,
        tag_ids
    ):

        print(
            "Aligning tags with ALMA"
        )

        input(
            "Place tag "
            + str(tag_ids)
            + " at the red, orange, and green pads, respectively, and press Enter"
        )

        temp_vec = []

        with tqdm(
            total=40,
            desc="Collecting position data",
            unit="tag positions"
        ):

            while len(temp_vec) < 40:

                sleep(0.2)

                try:

                    data_in = np.array(
                        [
                            last_measurements[
                                tag_id
                            ][:-1]
                            for tag_id in tag_ids
                        ]
                    )

                    if data_in is not None:

                        temp_vec.append(
                            data_in
                        )

                except KeyError:

                    pass

        temp_vec = np.median(
            temp_vec,
            axis=0
        )

        self.X_vecs = temp_vec

        return temp_vec

    # ========================================================
    # BLE transform
    # ========================================================

    def set_transform(self, X=None):

        print(
            "\nCalculating BLE transformation"
        )

        if X is None:

            X = self.X_vecs

        x1, x2, x3 = X

        try:

            X12 = np.array(
                [x1, x2]
            ).T

            X23 = np.array(
                [x2, x3]
            ).T

            Y12 = (
                np.array(
                    [
                        [-109., -108.],
                        [108., -107.]
                    ]
                ).T
                / 2
                * self.scale_factor
            )

            Y23 = (
                np.array(
                    [
                        [108, -107.],
                        [106, 108]
                    ]
                ).T
                / 2
                * self.scale_factor
            )

            A = np.matmul(
                (Y12 - Y23),
                np.linalg.inv(
                    X12 - X23
                )
            )

            B = (
                Y12
                - np.matmul(
                    A,
                    X12
                )
            )

            self.A = A
            self.b = B.T[0]

            print("A:")
            print(self.A)

            print("b:")
            print(self.b)

            return 1

        except Exception as e:

            print(
                "Can't get matrix transform:"
            )

            print(e)

            traceback.print_exc()

            return 0

    # ========================================================

    def transform_query(
        self,
        last_measurements,
        tag_id
    ):

        ans = input(
            "Perform tag to ALMA position calibration?"
            "(y) load from disk? (l) don't use tags! (n) quit (q)"
        )

        if ans == "y":

            if isinstance(tag_id, str):

                self.set_3pos_tag_single(
                    last_measurements,
                    tag_id
                )

            elif isinstance(tag_id, list):

                self.set_3pos_tag_all(
                    last_measurements,
                    tag_id
                )

            self.set_transform()

            with open(
                "transM.pickle",
                "wb"
            ) as fout:

                pickle.dump(
                    [
                        self.A,
                        self.b
                    ],
                    fout
                )

            self.vlbi_mode = True

        elif ans == "l":

            try:

                with open(
                    "transM.pickle",
                    "rb"
                ) as fin:

                    self.A, self.b = pickle.load(
                        fin
                    )

                self.vlbi_mode = True

            except Exception as e:

                print(
                    e,
                    "File not loaded!"
                )

                self.vlbi_mode = False

        elif ans == "n":

            self.vlbi_mode = False

            return False

        elif ans == "q":

            self.vlbi_mode = False

        return self.vlbi_mode

    # ========================================================

    def apply_transform(
        self,
        x,
        A=None,
        b=None
    ):

        if A is None:

            A = self.A

        if b is None:

            b = self.b

        y = A @ x + b

        return y

    # ========================================================

    def set_raw_ant_pos_from_ble(
        self,
        ble_data
    ):

        self.ant_pos_ble = np.array(
            [
                pos
                for pos in ble_data.values()
            ]
        ).T

    # ========================================================
    # Baselines
    # ========================================================

    def make_baselines(self):

        print(
            "\n=============================="
        )

        print(
            "Calculating baselines"
        )

        print(
            "=============================="
        )

        nant = len(
            self.ant_pos_X
        )

        print(
            "Number of antennas:",
            nant
        )

        res = np.zeros(
            (
                3,
                nant,
                nant
            )
        )

        if nant > 1:

            for i in range(nant):

                for j in range(nant):

                    res[
                        0,
                        i,
                        j
                    ] = (
                        self.ant_pos_X[i]
                        - self.ant_pos_X[j]
                    )

                    res[
                        1,
                        i,
                        j
                    ] = (
                        self.ant_pos_Y[i]
                        - self.ant_pos_Y[j]
                    )

                    res[
                        2,
                        i,
                        j
                    ] = (
                        self.ant_pos_Z[i]
                        - self.ant_pos_Z[j]
                    )

        self.BX = res[0] * u.m
        self.BY = res[1] * u.m
        self.BZ = res[2] * u.m

        print(
            "BX shape:",
            self.BX.shape
        )

        print(
            "BY shape:",
            self.BY.shape
        )

        print(
            "BZ shape:",
            self.BZ.shape
        )

    # ========================================================

    def get_baselines(self):

        try:

            return (
                self.BX,
                self.BY,
                self.BZ
            )

        except Exception as e:

            print(e)

            return None


# ============================================================
# SkyImage
# ============================================================

class SkyImage:

    def __init__(
        self,
        path="./models/",
        filename="galaxy_lobes.png",
        declination=-90 * u.deg,
        pixel_size=0.3 * u.arcsec
    ):

        self.path = path
        self.filename = filename
        self.pixel_size = pixel_size
        self.declination = declination

        self._webcam_mode = False
        self._loaded_img = False

    # ========================================================

    def load_image(
        self,
        path=None,
        filename=None,
        new_size=(480, 480),
        video_stream=None
    ):

        print(
            "\n=============================="
        )

        print(
            "Loading image"
        )

        print(
            "=============================="
        )

        if path is None:

            path = self.path

        else:

            self.path = path

        if filename is None:

            filename = self.filename

        else:

            self.filename = filename

        print(
            "Path:",
            path
        )

        print(
            "Filename:",
            filename
        )

        # ----------------------------------------------------
        # Webcam
        # ----------------------------------------------------

        if "Misc4.jpg" in filename:

            print(
                "Webcam mode"
            )

            self._webcam_mode = True

            try:

                if video_stream is None:

                    raise ValueError(
                        "Webcam mode selected, but no video_stream supplied."
                    )

                self.data = np.asarray(
                    video_stream
                )

                print(
                    "Raw webcam shape:",
                    self.data.shape
                )

                # ------------------------------------------------
                # Ensure 2D
                # ------------------------------------------------

                if self.data.ndim != 2:

                    raise ValueError(
                        "Webcam image must be 2D. "
                        f"Received shape {self.data.shape}"
                    )

                # ------------------------------------------------
                # Make dimensions odd
                # ------------------------------------------------

                if self.data.shape[1] % 2 == 0:

                    self.data = np.hstack(
                        [
                            self.data,
                            np.zeros(
                                (
                                    self.data.shape[0],
                                    1
                                ),
                                dtype=self.data.dtype
                            )
                        ]
                    )

                if self.data.shape[0] % 2 == 0:

                    self.data = np.vstack(
                        [
                            self.data,
                            np.zeros(
                                (
                                    1,
                                    self.data.shape[1]
                                ),
                                dtype=self.data.dtype
                            )
                        ]
                    )

                self.imsize_Y, self.imsize_X = (
                    self.data.shape
                )

                print(
                    "Final webcam image shape:",
                    self.data.shape
                )

                # mark successful load
                self._loaded_img = True

            except Exception as e:

                print(
                    "ERROR loading webcam:"
                )

                print(e)

                traceback.print_exc()

                # failed to load webcam frame
                self._loaded_img = False

        # ----------------------------------------------------
        # Normal image
        # ----------------------------------------------------

        else:

            print(
                "Normal image mode"
            )

            self._webcam_mode = False

            try:

                im = Image.open(
                    path + filename
                )

                im.thumbnail(
                    new_size
                )

                self.data = np.flipud(
                    np.asarray(
                        im.convert("L")
                    )
                )

                print(
                    "Image shape after loading:",
                    self.data.shape
                )

                # ------------------------------------------------
                # Make dimensions odd
                # ------------------------------------------------

                if self.data.shape[1] % 2 == 0:

                    self.data = np.hstack(
                        [
                            self.data,
                            np.zeros(
                                (
                                    self.data.shape[0],
                                    1
                                ),
                                dtype=self.data.dtype
                            )
                        ]
                    )

                if self.data.shape[0] % 2 == 0:

                    self.data = np.vstack(
                        [
                            self.data,
                            np.zeros(
                                (
                                    1,
                                    self.data.shape[1]
                                ),
                                dtype=self.data.dtype
                            )
                        ]
                    )

                self.imsize_Y, self.imsize_X = (
                    self.data.shape
                )

                print(
                    "Final image shape:",
                    self.data.shape
                )

                # mark successful load
                self._loaded_img = True

            except Exception as e:

                print(
                    "IMAGE ERROR:"
                )

                print(e)

                print(
                    "path:",
                    self.path
                )

                print(
                    "filename:",
                    self.filename
                )

                traceback.print_exc()

                # failed to load normal image
                self._loaded_img = False

    # ========================================================

    def make_invert(
        self,
        video_stream=None
    ):

        print(
            "\n------------------------------"
        )

        print(
            "make_invert()"
        )

        print(
            "data shape:",
            np.shape(self.data) if hasattr(self, 'data') else None
        )

        print(
            "loaded flag:",
            self._loaded_img
        )

        print(
            "webcam:",
            self._webcam_mode
        )

        print(
            "------------------------------"
        )

        if self._loaded_img is True:

            try:

                self.fft_data = (
                    np.fft.ifftshift(
                        np.fft.fft2(
                            self.data
                        )
                    )
                )

                self.fftsize_X, self.fftsize_Y = (
                    self.fft_data.shape
                )

                print(
                    "FFT shape:",
                    self.fft_data.shape
                )

            except Exception as e:

                print(
                    "ERROR in FFT:"
                )

                print(e)

                traceback.print_exc()

                raise

        else:
            # Not loaded: try to load if webcam mode and video_stream provided
            if self._webcam_mode is True:
                print("Updating webcam FFT")
                try:
                    self.load_image(video_stream=video_stream)
                    if not hasattr(self, 'data'):
                        raise RuntimeError('Failed to load webcam frame')
                    self.fft_data = (
                        np.fft.ifftshift(
                            np.fft.fft2(
                                self.data
                            )
                        )
                    )
                    self.fftsize_X, self.fftsize_Y = (
                        self.fft_data.shape
                    )
                    print("Webcam FFT shape:", self.fft_data.shape)
                except Exception as e:
                    print('ERROR updating webcam FFT:', e)
                    traceback.print_exc()
                    raise
            else:
                raise RuntimeError('No image loaded (and not in webcam mode)')


# ============================================================
# Observation
# ============================================================

class Observation:

    def __init__(
        self,
        Observatory,
        SkyImage,
        Control,
        obs_frequency=180 * u.GHz,
        HA_START=Angle(-4, u.hourangle),
        HA_END=Angle(4, u.hourangle),
        sample_freq=0.05 * u.Hz,
        EL_LIMIT=10 * u.deg,
        var_dic=None
    ):

        self.obs_frequency = obs_frequency

        self.obs_lam = (
            C.c / obs_frequency
        )

        self._buf_obs_frequency = (
            obs_frequency
        )

        self.HA_START = HA_START
        self.HA_END = HA_END

        self._buf_HA_START = HA_START
        self._buf_HA_END = HA_END

        self._buf_declination = (
            90 * u.deg
        )

        self.sample_freq = sample_freq

        self._buf_sample_freq = sample_freq

        self._buf_image_filename = None

        self.Observatory = Observatory
        self.SkyImage = SkyImage

        # ----------------------------------------------------
        # Initial FFT
        # ----------------------------------------------------

        print(
            "\nInitialising SkyImage FFT"
        )

        self.SkyImage.make_invert()

        # ----------------------------------------------------
        # Number of samples
        # ----------------------------------------------------

        # compute N_samples robustly: support HA as Angle or time-like Quantity
        try:
            ha_start_hours = self.HA_START.to(u.hourangle).value
            ha_end_hours = self.HA_END.to(u.hourangle).value
            duration_hours = ha_end_hours - ha_start_hours
        except Exception:
            # fallback if HA stored as time Quantity
            duration_hours = (self.HA_END.to(u.hour).value - self.HA_START.to(u.hour).value)

        try:
            if hasattr(sample_freq, 'to'):
                sf = sample_freq.to(1 / u.hour).value
            else:
                sf = float(sample_freq)
        except Exception:
            sf = float(sample_freq)

        self.N_samples = int(duration_hours * sf) + 1

        self.EL_LIMIT = EL_LIMIT

        self.Control = Control

        self.var_dic = var_dic

        self.rot_varname = None
        self.rot_value = None

        self.RA_elev = (
            90 * u.deg
        )

    # ========================================================

    def set_read_source_ids(
        self,
        src_list
    ):

        self.Control.ctrl_id = src_list[0]

    # ========================================================

    def set_var_dic(
        self,
        var_dic
    ):

        self.var_dic = var_dic

    # ========================================================

    def _return_val_button(
        self,
        but_pos,
        var_dic
    ):

        r0, r1, r2, s1, s2, s3 = tuple(
            [
                but_pos[_bid].get_state()
                for _bid in self.Control.button_ids
            ]
        )

        varname = var_dic[r0][0][r1]

        value = var_dic[r0][1][r1][0](
            var_dic[r0][1][r1][1],
            var_dic[r0][2][r1][r2]
        )

        self.rot_varname = varname
        self.rot_value = value

        return varname, value

    # ========================================================

    def update_obs_from_control(
        self,
        last_measurements,
        video_stream=None
    ):

        try:

            but_pos = (
                self.Control.get_state(
                    last_measurements
                )
            )

            varname, value = (
                self._return_val_button(
                    but_pos,
                    self.var_dic
                )
            )

        except Exception as e:

            print(
                "Error in button readout:"
            )

            print(e)

            traceback.print_exc()

            return 0

        # ----------------------------------------------------
        # Hour angle
        # ----------------------------------------------------

        if varname == "hr_angle":

            self._buf_HA_END = (
                Angle(
                    value,
                    u.hourangle
                )
                + self._buf_HA_END
                - self._buf_HA_START
            )

            self._buf_HA_START = Angle(
                value,
                u.hourangle
            )

            if but_pos['S0'].get_state() == 1:

                self.HA_END = (
                    self._buf_HA_END
                )

                self.HA_START = (
                    self._buf_HA_START
                )

        # ----------------------------------------------------
        # Integration time
        # ----------------------------------------------------

        if varname == "int_time":

            if value >= 12:

                self._buf_HA_START = Angle(
                    -6.,
                    u.hour
                )

                self._buf_HA_END = Angle(
                    +6,
                    u.hour
                )

            else:

                self._buf_HA_END = (
                    self._buf_HA_START
                    + Angle(
                        value,
                        u.hourangle
                    )
                )

            if but_pos['S0'].get_state() == 1:

                self.HA_END = (
                    self._buf_HA_END
                )

                self.HA_START = (
                    self._buf_HA_START
                )

        # ----------------------------------------------------
        # Declination
        # ----------------------------------------------------

        if varname == "obj_dec":

            self._buf_declination = (
                value * u.deg
            )

            if but_pos['S0'].get_state() == 1:

                self.SkyImage.declination = (
                    self._buf_declination
                )

        # ----------------------------------------------------
        # Frequency
        # ----------------------------------------------------

        if varname == "obs_freq":

            self._buf_obs_frequency = (
                value * u.GHz
            )

            if but_pos['S0'].get_state() == 1:

                self.obs_frequency = (
                    self._buf_obs_frequency
                )

                self.obs_lam = (
                    C.c
                    / self.obs_frequency
                )

        # ----------------------------------------------------
        # Image
        # ----------------------------------------------------

        if varname == "img_file":

            self._buf_image_filename = value

            if but_pos['S0'].get_state() == 1:

                self.SkyImage.load_image(
                    filename=self._buf_image_filename,
                    video_stream=video_stream
                )

        # ----------------------------------------------------
        # VLBI
        # ----------------------------------------------------

        if but_pos['S2'].get_state() == 1:

            self.vlbi_mode = True

        else:

            self.vlbi_mode = False

        # ----------------------------------------------------
        # FFT
        # ----------------------------------------------------

        self.SkyImage.make_invert(
            video_stream=video_stream
        )

    # ========================================================

    def update_obs(
        self,
        last_measurements=None,
        obs_frequency=180 * u.GHz,
        HA_START=Angle(-4, u.hour),
        HA_END=Angle(4, u.hour),
        sample_freq=0.05 * u.Hz,
        EL_LIMIT=10 * u.deg
    ):

        self.obs_frequency = obs_frequency

        self.obs_lam = (
            C.c / obs_frequency
        )

        self.sample_freq = sample_freq

        self.HA_START = HA_START
        self.HA_END = HA_END

        # robust N_samples computation
        try:
            ha_start_hours = self.HA_START.to(u.hourangle).value
            ha_end_hours = self.HA_END.to(u.hourangle).value
            duration_hours = ha_end_hours - ha_start_hours
        except Exception:
            duration_hours = (self.HA_END.to(u.hour).value - self.HA_START.to(u.hour).value)

        try:
            if hasattr(sample_freq, 'to'):
                sf = sample_freq.to(1 / u.hour).value
            else:
                sf = float(sample_freq)
        except Exception:
            sf = float(sample_freq)

        self.N_samples = int(duration_hours * sf) + 1

        self.EL_LIMIT = EL_LIMIT

    # ========================================================
    # Elevation curve
    # ========================================================

    def calc_el_curve(self):

        print(
            "\n=============================="
        )

        print(
            "Calculating elevation curve"
        )

        print(
            "=============================="
        )

        def _ha_to_rad(ha):
            # Accept Angle, time-like Quantity (hours), or numeric hourangle
            try:
                if isinstance(ha, Angle):
                    return ha.to(u.radian).value
            except Exception:
                pass

            try:
                if isinstance(ha, u.Quantity):
                    # time-like hours -> hourangle
                    if ha.unit.is_equivalent(u.hour):
                        return Angle(ha.to(u.hour).value, u.hourangle).to(u.radian).value
                    else:
                        return ha.to(u.radian).value
            except Exception:
                pass

            # fallback: treat as hourangle numeric
            return Angle(ha, u.hourangle).to(u.radian).value

        ha_start_rad = _ha_to_rad(self.HA_START)
        ha_end_rad = _ha_to_rad(self.HA_END)

        ha_arr_rad = np.linspace(
            ha_start_rad,
            ha_end_rad,
            self.N_samples
        )

        lat_rad = (
            self.Observatory.latitude
            .to(u.radian)
            .value
        )

        dec_rad = (
            self.SkyImage.declination
            .to(u.radian)
            .value
        )

        expr = (
            np.sin(lat_rad)
            * np.sin(dec_rad)
            + np.cos(lat_rad)
            * np.cos(dec_rad)
            * np.cos(ha_arr_rad)
        )

        expr = np.clip(
            expr,
            -1.0,
            1.0
        )

        elev_deg = np.degrees(
            np.arcsin(expr)
        )

        # ----------------------------------------------------
        # Mid observation elevation
        # ----------------------------------------------------

        # compute mid hour-angle robustly
        ha_mid = None
        try:
            ha_mid = (self.HA_START.to(u.hourangle).value + self.HA_END.to(u.hourangle).value) / 2.0
            ha_mid_rad = Angle(ha_mid, u.hourangle).to(u.radian).value
        except Exception:
            ha_mid_rad = _ha_to_rad((self.HA_START + self.HA_END) / 2)

        expr_mid = (
            np.sin(lat_rad)
            * np.sin(dec_rad)
            + np.cos(lat_rad)
            * np.cos(dec_rad)
            * np.cos(ha_mid_rad)
        )

        expr_mid = np.clip(
            expr_mid,
            -1.0,
            1.0
        )

        self.RA_elev = (
            np.degrees(
                np.arcsin(expr_mid)
            )
        )

        # ----------------------------------------------------
        # Elevation cut
        # ----------------------------------------------------

        el_limit_deg = (
            self.EL_LIMIT
            .to(u.deg)
            .value
        )

        mask = (
            elev_deg > el_limit_deg
        )

        self.HA_arr = (
            ha_arr_rad[mask]
        )

        self.cos_ha = np.cos(
            self.HA_arr
        )

        self.sin_ha = np.sin(
            self.HA_arr
        )

        self.sin_cos_ha = np.array(
            [
                self.sin_ha,
                self.cos_ha
            ]
        ).T

        print(
            "HA array shape:",
            self.HA_arr.shape
        )

        print(
            "sin_cos_ha shape:",
            self.sin_cos_ha.shape
        )

        print(
            "Elevation curve finished"
        )

    # ========================================================
    # UV coverage
    # ========================================================

    def make_uv_coverage(self):

        print(
            "\n=============================="
        )

        print(
            "make_uv_coverage()"
        )

        print(
            "=============================="
        )

        print(
            "Antennas:"
        )

        print(
            "X:",
            np.shape(
                self.Observatory.ant_pos_X
            )
        )

        print(
            "Y:",
            np.shape(
                self.Observatory.ant_pos_Y
            )
        )

        print(
            "Z:",
            np.shape(
                self.Observatory.ant_pos_Z
            )
        )

        print(
            "sin_cos_ha:",
            np.shape(
                self.sin_cos_ha
            )
        )

        # ----------------------------------------------------
        # Multiple antennas
        # ----------------------------------------------------

        if len(
            self.Observatory.ant_pos_X
        ) > 1:

            print(
                ">>> Multiple antennas"
            )

            try:

                self.U = (
                    np.array(
                        [
                            self.Observatory.BX.value
                            * sinha
                            + self.Observatory.BY.value
                            * cosha

                            for sinha, cosha
                            in self.sin_cos_ha
                        ]
                    )
                    * self.Observatory.BX.unit
                    / self.obs_lam
                ).decompose() * (
                    1. / u.radian
                )

                self.V = (
                    np.array(
                        [
                            -self.Observatory.BX.value
                            * np.sin(
                                self.SkyImage.declination
                            )
                            * cosha

                            + self.Observatory.BY.value
                            * np.sin(
                                self.SkyImage.declination
                            )
                            * sinha

                            + self.Observatory.BZ.value
                            * np.cos(
                                self.SkyImage.declination
                            )

                            for sinha, cosha
                            in self.sin_cos_ha
                        ]
                    )
                    * self.Observatory.BY.unit
                    / self.obs_lam
                ).decompose() * (
                    1. / u.radian
                )

                print(
                    "U shape:",
                    self.U.shape
                )

                print(
                    "V shape:",
                    self.V.shape
                )

            except Exception as e:

                print(
                    "\n!!! ERROR calculating U/V !!!"
                )

                print(
                    type(e).__name__
                )

                print(e)

                traceback.print_exc()

                raise

        # ----------------------------------------------------
        # Single antenna
        # ----------------------------------------------------

        else:

            print(
                ">>> Single antenna"
            )

            self.U = np.array(
                [0.0]
            )

            self.V = np.array(
                [0.0]
            )

            print(
                "U:",
                self.U,
                self.U.shape
            )

            print(
                "V:",
                self.V,
                self.V.shape
            )

        print(
            "make_uv_coverage() finished"
        )

    # ========================================================
    # Grid UV coverage
    # ========================================================

    def grid_uv_coverage(self):

        print(
            "\n=============================="
        )

        print(
            "grid_uv_coverage()"
        )

        print(
            "=============================="
        )

        if len(
            self.Observatory.ant_pos_X
        ) > 1:

            self.u = np.int16(
                (
                    (
                        self.U
                        + 1. /
                        self.SkyImage.pixel_size.to(
                            u.radian
                        )
                    )
                    / 2
                    * self.SkyImage.pixel_size.to(
                        u.radian
                    )
                    * self.SkyImage.imsize_X
                )
                .decompose()
                .value
            )

            self.v = np.int16(
                (
                    (
                        self.V
                        + 1. /
                        self.SkyImage.pixel_size.to(
                            u.radian
                        )
                    )
                    / 2
                    * self.SkyImage.pixel_size.to(
                        u.radian
                    )
                    * self.SkyImage.imsize_Y
                )
                .decompose()
                .value
            )

        else:

            self.u = np.array(
                [0],
                dtype=np.int16
            )

            self.v = np.array(
                [0],
                dtype=np.int16
            )

        print(
            "u shape:",
            self.u.shape
        )

        print(
            "v shape:",
            self.v.shape
        )

    # ========================================================
    # Mask UV coverage
    # ========================================================

    def make_masked_arr(
        self,
        weights="natural"
    ):

        print(
            "\n=============================="
        )

        print(
            "make_masked_arr()"
        )

        print(
            "=============================="
        )

        print(
            "fft_data:",
            self.SkyImage.fft_data.shape
        )

        print(
            "u:",
            np.shape(self.u)
        )

        print(
            "v:",
            np.shape(self.v)
        )

        # ----------------------------------------------------
        # UVC has exactly same size as FFT
        # ----------------------------------------------------

        self.UVC = np.zeros(
            self.SkyImage.fft_data.shape
        )

        print(
            "Initial UVC:",
            self.UVC.shape
        )

        # ----------------------------------------------------
        # Multiple antennas
        # ----------------------------------------------------

        if len(
            self.Observatory.ant_pos_X
        ) > 1:

            print(
                ">>> Multiple antennas"
            )

            valid = (
                (self.u > 0)
                &
                (self.v > 0)
                &
                (self.u < self.UVC.shape[0])
                &
                (self.v < self.UVC.shape[1])
            )

            print(
                "Valid UV points:",
                np.sum(valid)
            )

            uv_unique = np.unique(
                (
                    self.u[valid]
                    + self.v[valid] * 1.j
                ),
                return_counts=True
            )

            self.uv_u = uv_unique

            print(
                "Unique UV points:",
                len(
                    uv_unique[0]
                )
            )

            if weights == "uniform":

                self.UVC[
                    np.real(
                        uv_unique[0]
                    ).astype(int),

                    np.imag(
                        uv_unique[0]
                    ).astype(int)
                ] = 1

            elif weights == "natural":

                self.UVC[
                    np.real(
                        uv_unique[0]
                    ).astype(int),

                    np.imag(
                        uv_unique[0]
                    ).astype(int)
                ] = uv_unique[1]

            # ------------------------------------------------
            # Remove zero-frequency component
            # ------------------------------------------------

            self.UVC[
                int(
                    self.UVC.shape[0] / 2
                ),
                int(
                    self.UVC.shape[1] / 2
                )
            ] = 0

            # ------------------------------------------------
            # Normalize
            # ------------------------------------------------

            min_val = np.min(
                self.UVC
            )

            max_val = np.max(
                self.UVC
            )

            if max_val != min_val:

                self.UVC = (
                    self.UVC - min_val
                ) / (
                    max_val - min_val
                )

            else:

                print(
                    "WARNING: UVC has no variation"
                )

            self.UVC = self.UVC.T

        # ----------------------------------------------------
        # Single antenna
        # ----------------------------------------------------

        else:

            print(
                ">>> Single antenna"
            )

            self.UVC = np.ones_like(
                self.SkyImage.fft_data
            )

        print(
            "Final UVC shape:",
            self.UVC.shape
        )

    # ========================================================
    # Dirty image
    # ========================================================

    def make_dirty_arr(self):

        print(
            "\n=============================="
        )

        print(
            "make_dirty_arr()"
        )

        print(
            "=============================="
        )

        print(
            "Number of antennas:"
        )

        print(
            len(
                self.Observatory.ant_pos_X
            )
        )

        print(
            "SkyImage data:",
            np.shape(
                self.SkyImage.data
            )
        )

        print(
            "FFT data:",
            np.shape(
                self.SkyImage.fft_data
            )
        )

        print(
            "U:",
            np.shape(
                self.U
            )
        )

        print(
            "V:",
            np.shape(
                self.V
            )
        )

        print(
            "u:",
            np.shape(
                self.u
            )
        )

        print(
            "v:",
            np.shape(
                self.v
            )
        )

        print(
            "UVC:",
            np.shape(
                self.UVC
            )
        )

        # ----------------------------------------------------
        # Multiple antennas
        # ----------------------------------------------------

        if len(
            self.Observatory.ant_pos_X
        ) > 1:

            print(
                ">>> Multiple antennas"
            )

            if (
                self.UVC.shape
                != self.SkyImage.fft_data.shape
            ):

                print(
                    "WARNING:"
                )

                print(
                    "UVC and FFT have different shapes!"
                )

                print(
                    "UVC:",
                    self.UVC.shape
                )

                print(
                    "FFT:",
                    self.SkyImage.fft_data.shape
                )

            # ------------------------------------------------
            # Sample FFT
            # ------------------------------------------------

            self.uv_fft_sampled = (
                self.UVC
                * self.SkyImage.fft_data.T
            )

            print(
                "uv_fft_sampled:",
                self.uv_fft_sampled.shape
            )

            # ------------------------------------------------
            # Dirty beam
            # ------------------------------------------------

            self.dirty_beam = (
                np.fft.ifftshift(
                    np.fft.ifft2(
                        self.UVC
                    )
                )
            )

            print(
                "dirty_beam:",
                self.dirty_beam.shape
            )

            # ------------------------------------------------
            # Dirty image
            # ------------------------------------------------

            self.dirty_image = (
                np.fft.ifft2(
                    np.fft.ifftshift(
                        self.uv_fft_sampled.T
                    )
                )
            )

            print(
                "dirty_image:",
                self.dirty_image.shape
            )

        # ----------------------------------------------------
        # Single antenna
        # ----------------------------------------------------

        else:

            print(
                ">>> Single antenna"
            )

            self.uv_fft_sampled = (
                0
                * self.SkyImage.fft_data.T
                + 1
            )

            self.dirty_beam = (
                np.ones_like(
                    self.SkyImage.fft_data
                )
            )

            self.dirty_image = np.array(
                self.SkyImage.data,
                copy=True
            )

            print(
                "Dirty image before Gaussian:",
                self.dirty_image.shape
            )

            # ------------------------------------------------
            # Single dish beam
            # ------------------------------------------------

            fwhm = (
                2
                * 1.02
                * (
                    self.obs_lam
                    / (12. * u.m)
                ).decompose()
                * (
                    1 * u.radian
                ).to(u.arcsec)
                / self.SkyImage.pixel_size
            )

            sigma = (
                fwhm.decompose().value
                / 2.35
            )

            print(
                "FWHM:",
                fwhm
            )

            print(
                "Sigma:",
                sigma
            )

            self.dirty_image = (
                gaussian_filter(
                    self.SkyImage.data,
                    sigma=sigma,
                    mode='nearest'
                )
            )

            print(
                "Dirty image after Gaussian:",
                self.dirty_image.shape
            )

        print(
            "make_dirty_arr() finished"
        )