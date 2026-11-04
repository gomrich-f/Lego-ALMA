def make_frame(payload_bytes: bytes) -> bytes:
    # START 0xAA 0x55, 8 payload bytes, END 0xFF
    assert len(payload_bytes) == 8
    return b"\xAA\x55" + payload_bytes + b"\xFF"


def parse_first_frame(data: bytes):
    START_SEQ = b"\xAA\x55"
    END_BYTE = 0xFF

    start = data.find(START_SEQ)
    if start == -1:
        return []
    if len(data) < start + 11:
        return []
    if data[start + 10] != END_BYTE:
        return []

    payload = data[start + 2:start + 10]
    bit_string = ''.join(f"{b:08b}" for b in payload)
    return [i for i, ch in enumerate(bit_string) if ch == '1']


def main():
    # payload with bits at positions 0 and 15 (across first 16 bits)
    payload = bytes([0b10000000, 0b00000001] + [0] * 6)
    frame = make_frame(payload)

    res = parse_first_frame(frame)

    print('Returned positions:', res)

    expected = [0, 15]

    if res == expected:
        print('TEST PASSED')
        return 0
    else:
        print('TEST FAILED - expected', expected)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
