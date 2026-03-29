#!/usr/bin/env python3
"""
POCSAG decoder: Extract messages from WAV recordings
"""

import sys
import wave
import argparse
import json
import numpy as np
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from pocsag_common import (
    SAMPLE_RATE, BAUD_RATES, MARK_FREQ, SPACE_FREQ,
    fsk_demodulate, find_sync_word_position, parse_batch,
    bits_to_int, SYNC_WORD, IDLE_WORD
)


def detect_preamble(bits, min_length=100):
    """
    Find the start of a preamble (long run of alternating 1010...).

    Args:
        bits: Array of bits
        min_length: Minimum alternating bits to consider valid preamble

    Returns:
        Index of start of preamble, or -1 if not found
    """
    alternating_count = 0
    start_idx = -1

    for i in range(len(bits) - 1):
        if bits[i] != bits[i + 1]:
            if alternating_count == 0:
                start_idx = i
            alternating_count += 1
        else:
            if alternating_count >= min_length:
                return start_idx
            alternating_count = 0
            start_idx = -1

    if alternating_count >= min_length:
        return start_idx
    return -1


def find_batches(bits):
    """
    Find sync words and extract batch data.

    Args:
        bits: Array of bits

    Returns:
        List of batches, where each batch is a list of 32-bit codewords
    """
    batches = []
    pos = 0

    while pos < len(bits) - 32:
        # Find next sync word
        sync_pos = find_sync_word_position(bits[pos:], tolerance=2)
        if sync_pos == -1:
            break

        pos += sync_pos

        # Extract batch (sync word + 16 codewords)
        batch_bits = bits[pos:pos + 32 * 17]
        if len(batch_bits) < 32 * 17:
            break

        # Convert to codewords
        codewords = []
        for i in range(17):
            cw_bits = batch_bits[i * 32:(i + 1) * 32]
            cw = bits_to_int(cw_bits)
            codewords.append(cw)

        batches.append(codewords)
        pos += 32 * 17

    return batches


def decode_wav(filename, baud_rate=None):
    """
    Decode a POCSAG WAV file.

    Args:
        filename: Path to WAV file
        baud_rate: Baud rate (512, 1200, 2400). If None, auto-detect.

    Returns:
        List of message dicts with 'ric', 'function', 'text', 'numeric' keys
    """
    # Read WAV file
    with wave.open(filename, 'rb') as wav_file:
        num_channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        file_sample_rate = wav_file.getframerate()
        num_frames = wav_file.getnframes()

        audio_bytes = wav_file.readframes(num_frames)

    # Convert to float samples
    if sample_width == 1:
        audio_int = np.frombuffer(audio_bytes, dtype=np.uint8)
        audio = (audio_int.astype(np.float32) - 128) / 128.0
    elif sample_width == 2:
        audio_int = np.frombuffer(audio_bytes, dtype=np.int16)
        audio = audio_int.astype(np.float32) / 32768.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Convert to mono if needed
    if num_channels > 1:
        audio = audio.reshape(-1, num_channels).mean(axis=1)

    # Resample to standard rate if needed
    if file_sample_rate != SAMPLE_RATE:
        factor = SAMPLE_RATE / file_sample_rate
        new_length = int(len(audio) * factor)
        indices = np.linspace(0, len(audio) - 1, new_length)
        audio = np.interp(indices, np.arange(len(audio)), audio)

    # Normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val

    all_messages = []

    # Try each baud rate if not specified
    baud_rates = [baud_rate] if baud_rate else BAUD_RATES

    for current_baud in baud_rates:
        print(f"Trying baud rate: {current_baud}", file=sys.stderr)

        # FSK demodulate
        bits = fsk_demodulate(audio, SAMPLE_RATE, current_baud, MARK_FREQ, SPACE_FREQ)
        bits = np.array(bits, dtype=np.int8)

        # Find preamble
        preamble_pos = detect_preamble(bits)
        if preamble_pos == -1:
            print(f"  No preamble found", file=sys.stderr)
            continue

        print(f"  Preamble found at bit {preamble_pos}", file=sys.stderr)

        # Extract batches after preamble
        batches = find_batches(bits[preamble_pos:])
        print(f"  Found {len(batches)} batches", file=sys.stderr)

        if not batches:
            continue

        # Parse messages from batches
        messages = []
        for batch_idx, batch in enumerate(batches):
            batch_messages = parse_batch(batch, frame_position_offset=batch_idx * 8)
            messages.extend(batch_messages)

        if messages:
            print(f"  Decoded {len(messages)} messages", file=sys.stderr)
            all_messages.extend(messages)
            break  # Stop trying other baud rates if we found messages

    return all_messages


def format_message(msg):
    """Format a message dict for display"""
    ric = msg.get('ric', 'unknown')
    func = msg.get('function', '?')
    text = msg.get('text', '')
    numeric = msg.get('numeric', False)

    func_names = {0: 'numeric', 1: 'tone', 2: 'alphanumeric', 3: 'alphanumeric'}
    func_name = func_names.get(func, f'func{func}')

    return f"RIC {ric:7d} [{func_name:12s}] {text}"


def main():
    parser = argparse.ArgumentParser(description='Decode POCSAG WAV file')
    parser.add_argument('input_file', help='Input WAV filename')
    parser.add_argument('output_file', nargs='?', default=None,
                        help='Output text file (optional)')
    parser.add_argument('--baud', type=int, default=None, choices=[512, 1200, 2400],
                        help='Baud rate (default: auto-detect)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')

    args = parser.parse_args()

    print(f"Decoding: {args.input_file}", file=sys.stderr)

    # Decode
    messages = decode_wav(args.input_file, baud_rate=args.baud)

    if not messages:
        print("No messages found.", file=sys.stderr)
        return

    # Format output
    if args.json:
        output = json.dumps(messages, indent=2)
    else:
        output_lines = []
        for msg in messages:
            output_lines.append(format_message(msg))
        output = '\n'.join(output_lines)

    # Write output
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"Wrote {len(messages)} messages to {args.output_file}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
