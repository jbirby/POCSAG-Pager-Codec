# POCSAG Pager Codec

A complete POCSAG (Post Office Code Standardisation Advisory Group) paging protocol encoder and decoder for SDR hobbyists. This toolkit allows you to create and decode POCSAG messages in WAV format using standard Python libraries.

## What is POCSAG?

POCSAG is the international standard for one-way RF paging, used worldwide in hospitals, emergency services, fire departments, restaurants, and many other services. It operates on dedicated VHF/UHF frequencies and uses 2-FSK (Frequency Shift Keying) modulation.

**Key characteristics:**
- **Data rates:** 512, 1200, or 2400 baud
- **Frequencies:** VHF/UHF (e.g., 152.0075, 157.450, 931.9375 MHz in the US)
- **Modulation:** 2-FSK with ±4.5 kHz deviation
- **Error correction:** BCH(31,21) with 2-bit error correction
- **Addressing:** 21-bit Radio Identity Code (RIC) or CAP code

## Installation

```bash
pip install numpy --break-system-packages
```

## Usage

### Decode a POCSAG WAV file from your SDR

```bash
python3 scripts/pocsag_decode.py recording.wav
```

Options:
- `--baud N` - Specify baud rate (512, 1200, 2400). Default: auto-detect
- `--json` - Output as JSON
- `output.txt` - Optional output file

**Example:**
```bash
python3 scripts/pocsag_decode.py myrecording.wav messages.txt
python3 scripts/pocsag_decode.py myrecording.wav --baud 1200 --json
```

**Output format:**
```
RIC    1234567 [alphanumeric] HELLO WORLD
RIC    9876543 [numeric     ] 1234567890
RIC     555555 [tone        ] (tone only)
```

### Encode a test POCSAG transmission

```bash
python3 scripts/pocsag_encode.py output.wav [options]
```

Options:
- `--address N` / `--ric N` - Pager address (0-2097151, default 1234567)
- `--message TEXT` - Message text (default: "TEST")
- `--numeric` - Force numeric encoding
- `--alpha` - Force alphanumeric encoding (default: auto)
- `--baud N` - Baud rate (512, 1200, 2400, default 1200)
- `--function N` - Function bits (0-3, default auto)

**Example:**
```bash
# Create a simple test message
python3 scripts/pocsag_encode.py test.wav --ric 1234567 --message "HELLO"

# Numeric message
python3 scripts/pocsag_encode.py test.wav --address 555555 --message "1234567890" --numeric

# Custom settings
python3 scripts/pocsag_encode.py test.wav --ric 9876543 --message "Alert" --baud 2400
```

### Run tests

```bash
python3 scripts/pocsag_test.py
```

Tests include:
- BCH error correction (1-bit and 2-bit)
- Numeric and alphanumeric encoding/decoding
- Address codeword construction
- FSK modulation/demodulation
- Full WAV roundtrip tests at all baud rates
- Multiple messages in transmission

## File Structure

```
pocsag/
├── SKILL.md                 # Skill metadata
├── README.md               # This file
└── scripts/
    ├── pocsag_common.py    # Core codec functions
    ├── pocsag_encode.py    # WAV encoder CLI
    ├── pocsag_decode.py    # WAV decoder CLI
    └── pocsag_test.py      # Test suite
```

## Technical Details

### POCSAG Frame Structure

Each POCSAG transmission begins with a **preamble** (576 bits of alternating 1010...) for bit synchronization, followed by **batches**.

Each batch contains:
1. **Sync codeword** (32 bits): 0x7CD215D8
2. **8 frames**, each with 2 codewords (32 bits each)
3. Total: 1 + 16 = 17 codewords per batch

### Codeword Types

**Address codeword** (bit 31 = 0):
- Bits 30-13: Address (18 bits)
- Bits 12-11: Function (2 bits)
- Bits 10-1: BCH parity (10 bits)
- Bit 0: Even parity

**Message codeword** (bit 31 = 1):
- Bits 30-11: Message data (20 bits)
- Bits 10-1: BCH parity (10 bits)
- Bit 0: Even parity

### RIC (Radio Identity Code) Calculation

The full 21-bit RIC is computed from:
- Address bits (18 bits) from the address codeword
- Frame position (3 bits) where the address appears

```
RIC = (address_bits << 3) | frame_position
```

This allows up to 2,097,152 unique pagers.

### Message Types

**Numeric** (function = 0):
- 4 bits per digit
- Supports 0-9, space, U, hyphen, brackets

**Alphanumeric** (function = 2 or 3):
- 7-bit ASCII characters
- Sent LSB first within each 20-bit message field

**Tone-only** (function = 1):
- No message data
- Used for alert/alert-and-ack paging

### Error Correction

BCH(31,21) code with generator polynomial:
```
x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1
```

This can correct up to **2-bit errors** in each 31-bit codeword. The decoder automatically corrects errors and reports the error count per codeword.

## How to Use with SDR

### Example with RTL-SDR:

1. Record POCSAG broadcast:
```bash
rtl_fm -f 152.0075M -s 22k -g 30 - | sox -t raw -r 22k -e s -b 16 -c 1 - recording.wav
```

2. Decode the recording:
```bash
python3 scripts/pocsag_decode.py recording.wav
```

### Example with other SDR software:

1. Use GQRX, CubicSDR, or similar to tune to a POCSAG frequency
2. Record the audio output as WAV (mono, 44.1 kHz or higher recommended)
3. Decode with the decoder script

## Limitations

- **Demodulation quality** depends on signal-to-noise ratio. Clean SDR recordings work best.
- **Alphanumeric messages** are limited to 7-bit ASCII; extended ASCII won't decode correctly.
- **Multi-RIC batches** (multiple pagers addressed in one batch) are all decoded independently.
- **Auto baud rate detection** tries 512, 1200, 2400 in order; if the first one finds valid sync words, it stops.

## Examples

### Example 1: Decode a hospital pager transmission
```bash
$ python3 scripts/pocsag_decode.py hospital_sdr.wav
Decoding: hospital_sdr.wav
RIC    1234567 [alphanumeric] CALL DOCTOR
RIC    7654321 [alphanumeric] EMERGENCY DEPT
RIC    5555555 [tone        ] (tone alert)
```

### Example 2: Create a test transmission at 2400 baud
```bash
$ python3 scripts/pocsag_encode.py emergency.wav --ric 1234567 --message "FIRE ALERT" --baud 2400
Encoding message: FIRE ALERT
  Address/RIC: 1234567
  Baud rate: 2400
  Message type: Auto
Wrote 141120 samples to emergency.wav
Duration: 3.20 seconds
```

### Example 3: Test numeric message
```bash
$ python3 scripts/pocsag_encode.py number.wav --ric 999999 --message "1234567890" --numeric
$ python3 scripts/pocsag_decode.py number.wav
RIC     999999 [numeric     ] 1234567890
```

## Known Issues

- Sync word detection uses Hamming distance ≤ 2; may occasionally find false positives in noisy recordings
- Alphanumeric decoding stops at null bytes; messages with embedded nulls won't decode fully
- Very short messages may not be reliably decoded in presence of burst noise

## Contributing

This is a hobby/educational project. Feel free to enhance it with:
- Improved bit sync (PLL instead of simple demodulation)
- Tone-only message handling
- Multi-batch message reassembly
- Performance optimizations

## References

- POCSAG Protocol Specification (Motorola)
- Wikipedia: Paging (radio)
- SDR decoding guides for POCSAG

## License

Public domain - use freely for hobby/educational purposes.
