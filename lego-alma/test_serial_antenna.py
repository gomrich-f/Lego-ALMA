#!/usr/bin/env python3
"""
Simple serial antenna signal test for Raspberry Pi.
Checks if /dev/ttyACM0 responds to 'b\r' command and shows received data.
Run with: python3 test_serial_antenna.py
"""

import serial
import time
import sys

def test_serial():
    port = '/dev/ttyACM0'
    baud = 19200
    timeout = 1
    
    print(f"Testing serial connection to {port} at {baud} baud")
    print("-" * 60)
    
    try:
        ser = serial.Serial(port, baud, timeout=timeout, exclusive=True)
        print(f"✓ Connection opened successfully")
    except Exception as e:
        print(f"✗ Failed to open {port}: {e}")
        sys.exit(1)
    
    # Test multiple reads
    num_reads = 10
    print(f"\nPerforming {num_reads} reads from device...\n")
    
    for attempt in range(num_reads):
        try:
            # Send command
            ser.write(b'b\r')
            print(f"Attempt {attempt + 1}:")
            print(f"  Sent: b\\r")
            
            # Read response
            data = ser.readline()
            
            print(f"  Bytes received: {len(data)}")
            print(f"  Raw (repr):     {repr(data)}")
            print(f"  Hex:            {data.hex()}")
            
            # Decode
            decoded = data.decode('utf8', errors='replace')
            print(f"  Decoded:        {repr(decoded)}")
            
            # Extract bit positions (same logic as reader)
            if len(decoded) > 0:
                import numpy as np
                bit_positions = np.where(
                    np.array([bit == '1' for bit in decoded])
                )[0]
                print(f"  Bit positions:  {list(bit_positions)} ({len(bit_positions)} bits active)")
            else:
                print(f"  Bit positions:  (empty)")
            
            print()
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print()
    
    ser.close()
    print("-" * 60)
    print("Test complete. If 'Bytes received' is 0 or only empty lines,")
    print("the device is not responding to the 'b\\r' command.")
    print("\nTo troubleshoot:")
    print("  1. Check: ls -l /dev/ttyACM0")
    print("  2. Try: cat /dev/ttyACM0 (and move antenna)")
    print("  3. Check device manual for correct command/protocol")

if __name__ == '__main__':
    test_serial()
