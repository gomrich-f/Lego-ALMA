import serial
import numpy as np
import time

PORT = "/dev/ttyACM0"
BAUDRATE = 19200

print("Verbinde mit Arduino...")
print(f"Port: {PORT}")
print(f"Baudrate: {BAUDRATE}")

try:
    ser = serial.Serial(
        PORT,
        BAUDRATE,
        timeout=2
    )

    print("Verbindung erfolgreich!")
    print("Lese Antennendaten...\n")

    while True:

        # Arduino nach dem aktuellen Zustand fragen
        ser.write(b"b\r")

        # Antwort lesen
        line = ser.readline()

        if not line:
            print("Keine Antwort vom Arduino")
            time.sleep(0.5)
            continue

        # Bytes -> String
        raw = line.decode("utf-8", errors="ignore").strip()

        print("--------------------------------")
        print("Arduino:")
        print(raw)

        # Nur 0 und 1 berücksichtigen
        bit_string = "".join(
            char for char in raw
            if char in "01"
        )

        print("Bitstring:")
        print(bit_string)

        # Positionen der 1en bestimmen
        positions = np.where(
            np.array(
                [char == "1" for char in bit_string]
            )
        )[0]

        print("Positionen der 1en:")
        print(positions)

        print("Anzahl aktiver Antennen:")
        print(len(positions))

        time.sleep(0.5)

except KeyboardInterrupt:

    print("\nProgramm beendet.")

except Exception as e:

    print("\nFEHLER:")
    print(type(e).__name__)
    print(e)

finally:

    try:
        ser.close()
        print("Serielle Verbindung geschlossen.")
    except:
        pass