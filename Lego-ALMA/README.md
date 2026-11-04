# LEGO-ALMA

Software for controlling and performing observations with the LEGO-ALMA device.

The program connects to the serial antenna/controller hardware, processes camera and measurement data, and provides a graphical user interface.

## Getting Started

Run the following command from the `Lego-ALMA` directory:

```bash
python la_main_with_gui.py
```

For Raspberry Pi installations, additional setup and service files are provided in `pi_deploy/`.

## Main Files

- `la_main_with_gui.py` – Main program and GUI entry point
- `la_gui.py` – Graphical user interface
- `la_control_new.py` – Processing of controller buttons and switches
- `la_reader_new.py` – Serial data and video input
- `la_obs_img_new.py` – Observation and image processing
- `la_disp_man.py` – Display management
- `la_config.py` – Controller configuration values and assignments
- `pi_deploy/` – Setup and automatic startup configuration for Raspberry Pi

## Requirements

The software requires Python 3 and the following Python packages:

| Package (pip) | Purpose |
|---|---|
| `numpy` | Numerical calculations and measurement data |
| `scipy` | Scientific functions, including filtering |
| `matplotlib` | Plotting and data visualization |
| `astropy` | Astronomical coordinates and units |
| `Pillow` | Image file handling |
| `opencv-python` | Camera and video data processing |
| `pyserial` | Serial communication with the hardware |
| `tqdm` | Progress bars and progress indicators |
| `tenacity` | Retry logic for failed operations |

Additionally, `tkinter` is required for the graphical user interface. It is usually included with standard Python installations, but may need to be installed separately on some Linux systems.

The hardware must be accessible through the expected serial devices and a connected camera.
