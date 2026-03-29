#!/usr/bin/env python3
"""
POCSAG encoder: Create POCSAG WAV files from message parameters
"""

import sys
import wave
import argparse
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from pocsag_common import (
    SAMPLE_RATE, MARK_FREQ, SPACE_FREQ,
    build_address_codeword, build_message_codeword,
    encode_numeric_message, encode_alpha_message,
    fsk_modulate, int_to_bits, build_batch,
    IDLE_WORD
)


def create_pocsag_transmission(ric, message, baud_rate=1200, function_bits=None, numeric_mode=None):
    """
    Create a complete POCSAG transmission with preamble and batch.

    Args:
        ric: Radio Identity Code (0-2097151)
        message: Message text
        baud_rate: 512, 1200, or 2400 (default 1200)
        function_bits: Override function bits (0-3). If None, auto-detect from message
        numeric_mode: Force numeric (True) or alphanumeric (False). If None, auto-detect

    Returns:
        List of bits representing the complete transmission
    """
    # Validate RIC
    ric = int(ric) & 0x1FFFFF  # Mask to 21 bits
    if not (0 <= ric <= 0x1FFFFF):
        raise ValueError(f"RIC must be 0-2097151, got {ric}")

    # Auto-detect message type if needed
    if numeric_mode is None:
        # Try to detect if message is numeric
        numeric_chars = set('0123456789 U-[]')
        numeric_mode = all(c in numeric_chars for c in message)

    # Determine function bits if not specified
    if function_bits is None:
        function_bits = 0 if numeric_mode else 2

    # Extract address and frame from RIC
    address_bits = (ric >> 3) & 0x3FFFF
    frame_position = ric & 0x7

    # Build address codeword
    addr_codeword = build_address_codeword(address_bits, function_bits)

    # Encode message
    if numeric_mode:
        msg_chunks = encode_numeric_message(message)
    else:
        msg_chunks = encode_alpha_message(message)

    # Build message codewords
    msg_codewords = [build_message_codeword(chunk) for chunk in msg_chunks]

    # Pad frame with idle codewords if needed
    # Each frame has 2 codewords; we have 1 address + N message codewords
    # If address is in slot 0 of frame, message goes in slot 1 onward
    frame_codewords = [addr_codeword] + msg_codewords

    # Pad to multiple of 2 (frame size)
    while len(frame_codewords) % 2:
        frame_codewords.append(IDLE_WORD)

    # Organize into 8-frame batch (16 codewords total)
    # Our message goes in the frame corresponding to frame_position
    # Fill other frames with idle codewords
    batch_frames = []
    for f in range(8):
        if f == frame_position:
            # Put our message here
            frame_cws = frame_codewords[:2]
            frame_codewords = frame_codewords[2:]
        else:
            # Idle frame
            frame_cws = [IDLE_WORD, IDLE_WORD]

        batch_frames.append(frame_cws)

    # If we have more codewords, add another batch
    if frame_codewords:
        batch_frames_2 = []
        for f in range(8):
            if frame_codewords:
                frame_cws = frame_codewords[:2]
                frame_codewords = frame_codewords[2:]
            else:
                frame_cws = [IDLE_WORD, IDLE_WORD]
            batch_frames_2.append(frame_cws)

    # Build preamble (576 bits of 10101010...)
    preamble_bits = []
    for _ in range(576 // 2):
        preamble_bits.extend([1, 0])

    # Convert codewords to bits
    bits = preamble_bits.copy()

    # Add first batch
    for cw in build_batch(batch_frames):
        cw_bits = int_to_bits(cw, 32)
        bits.extend(cw_bits)

    # Add second batch if needed
    if frame_codewords or 'batch_frames_2' in locals():
        for cw in build_batch(batch_frames_2):
            cw_bits = int_to_bits(cw, 32)
            bits.extend(cw_bits)

    return bits


def main():
    parser = argparse.ArgumentParser(description='Encode POCSAG message to WAV file')
    parser.add_argument('output_file', help='Output WAV filename')
    parser.add_argument('--address', '--ric', type=int, default=1234567,
                        help='Pager address / RIC (0-2097151, default 1234567)')
    parser.add_argument('--message', type=str, default='TEST',
                        help='Message text (default: TEST)')
    parser.add_argument('--numeric', action='store_true',
                        help='Force numeric encoding')
    parser.add_argument('--alpha', action='store_true',
                        help='Force alphanumeric encoding')
    parser.add_argument('--baud', type=int, default=1200, choices=[512, 1200, 2400],
                        help='Baud rate (default 1200)')
    parser.add_argument('--function', type=int, default=None, choices=[0, 1, 2, 3],
                        help='Function bits (0-3, default auto)')

    args = parser.parse_args()

    # Determine message encoding mode
    numeric_mode = None
    if args.numeric:
        numeric_mode = True
    elif args.alpha:
        numeric_mode = False

    print(f"Encoding message: {args.message}")
    print(f"  Address/RIC: {args.address}")
    print(f"  Baud rate: {args.baud}")
    print(f"  Message type: {'Numeric' if numeric_mode is True else 'Alphanumeric' if numeric_mode is False else 'Auto'}")

    # Create transmission
    bits = create_pocsag_transmission(
        args.address,
        args.message,
        baud_rate=args.baud,
        function_bits=args.function,
        numeric_mode=numeric_mode
    )

    # Modulate to audio
    audio = fsk_modulate(bits, SAMPLE_RATE, args.baud, MARK_FREQ, SPACE_FREQ)

    # Normalize to 16-bit range
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.95
    audio_int16 = np.int16(audio * 32767)

    # Write WAV file
    with wave.open(args.output_file, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio_int16.tobytes())

    print(f"Wrote {len(audio_int16)} samples to {args.output_file}")
    print(f"Duration: {len(audio_int16) / SAMPLE_RATE:.2f} seconds")


if __name__ == '__main__':
    main()
