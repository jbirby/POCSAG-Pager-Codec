#!/usr/bin/env python3
"""
POCSAG codec common functions and constants
"""

import numpy as np
import struct
import math

# Constants
SAMPLE_RATE = 44100
BAUD_RATES = [512, 1200, 2400]
MARK_FREQ = 1200.0
SPACE_FREQ = 1800.0

SYNC_WORD = 0x7CD215D8
IDLE_WORD = 0x7A89C197

# BCH(31,21) parameters
BCH_GENERATOR = 0x769  # x^10 + x^9 + x^8 + x^6 + x^5 + x^3 + 1


def bch_encode(data_21bits):
    """
    Encode 21-bit data using BCH(31,21).
    Returns 31-bit codeword (data in bits 30-10).

    Args:
        data_21bits: 21-bit value to encode

    Returns:
        31-bit BCH codeword
    """
    # Shift data to positions 30-10
    codeword = (data_21bits & 0x1FFFFF) << 10

    # Calculate syndrome (remainder)
    syndrome = codeword
    for i in range(20, 9, -1):
        if syndrome & (1 << i):
            syndrome ^= (BCH_GENERATOR << (i - 10))

    # Combine data with parity bits
    codeword |= (syndrome & 0x3FF)

    return codeword & 0x7FFFFFFF


def _hamming_distance(x, y):
    """Calculate Hamming distance between two bit patterns"""
    # Ensure x and y are Python ints, not numpy integers
    x = int(x) & 0xFFFFFFFF
    y = int(y) & 0xFFFFFFFF
    return bin(x ^ y).count('1')


def _bch_syndrome(codeword_31bits):
    """Calculate syndrome for a 31-bit BCH codeword"""
    syndrome = codeword_31bits
    for i in range(20, 9, -1):
        if syndrome & (1 << i):
            syndrome ^= (BCH_GENERATOR << (i - 10))
    return syndrome & 0x3FF


def _gf_poly_div(dividend, divisor):
    """Polynomial division in GF(2) - returns quotient, remainder"""
    quotient = 0
    remainder = dividend
    divisor_bits = divisor.bit_length()

    while remainder.bit_length() >= divisor_bits:
        shift = remainder.bit_length() - divisor_bits
        quotient |= (1 << shift)
        remainder ^= (divisor << shift)

    return quotient, remainder


def bch_decode(codeword_31bits):
    """
    Decode and error-correct a 31-bit BCH codeword.
    Can correct up to 2-bit errors.

    Args:
        codeword_31bits: 31-bit received codeword

    Returns:
        Tuple (corrected_21bit_data, error_count, is_valid)
    """
    # Calculate syndrome
    syndrome = _bch_syndrome(codeword_31bits)

    if syndrome == 0:
        # No errors
        data = (codeword_31bits >> 10) & 0x1FFFFF
        return (data, 0, True)

    # Try all single-bit error positions and check if correction leads to zero syndrome
    for bit_pos in range(31):
        test_codeword = codeword_31bits ^ (1 << bit_pos)
        if _bch_syndrome(test_codeword) == 0:
            data = (test_codeword >> 10) & 0x1FFFFF
            return (data, 1, True)

    # Try all two-bit error combinations
    for bit_pos1 in range(31):
        for bit_pos2 in range(bit_pos1 + 1, 31):
            test_codeword = codeword_31bits ^ (1 << bit_pos1) ^ (1 << bit_pos2)
            if _bch_syndrome(test_codeword) == 0:
                data = (test_codeword >> 10) & 0x1FFFFF
                return (data, 2, True)

    # Uncorrectable error - return original data
    data = (codeword_31bits >> 10) & 0x1FFFFF
    return (data, -1, False)


def _parity_bit(value):
    """Calculate even parity bit for a value"""
    return bin(value).count('1') % 2


def build_address_codeword(address_18bits, function_bits):
    """
    Build a 32-bit address codeword.

    Args:
        address_18bits: 18-bit address (from RIC >> 3)
        function_bits: 2-bit function (00/01/10/11)

    Returns:
        32-bit address codeword (bit 31 = 0)
    """
    # Build 21-bit data for bits 30-10: address(18) + function(2) + unused(1)
    data_21bits = ((address_18bits & 0x3FFFF) << 3) | (function_bits & 0x3)

    # BCH encode produces 31-bit codeword
    bch_codeword = bch_encode(data_21bits)

    # Construct 32-bit address codeword:
    # bit 31 = 0 (address marker)
    # bits 30-0 = BCH codeword
    codeword_32bit = bch_codeword & 0x7FFFFFFF

    return codeword_32bit


def build_message_codeword(data_20bits):
    """
    Build a 32-bit message codeword.

    Args:
        data_20bits: 20-bit message data

    Returns:
        32-bit message codeword (bit 31 = 1)
    """
    # Build 21-bit data for bits 30-10: message(20) + unused(1)
    data_21bits = (data_20bits & 0xFFFFF) << 1

    # BCH encode
    bch_codeword = bch_encode(data_21bits)

    # Construct 32-bit message codeword:
    # bit 31 = 1 (message marker)
    # bits 30-0 = BCH codeword
    codeword_32bit = bch_codeword | (1 << 31)

    return codeword_32bit


def parse_codeword(codeword_32bit):
    """
    Parse a 32-bit codeword and extract data with error correction.

    Returns:
        Tuple (is_address, data, error_count, is_valid)
    """
    # Ensure we're working with 32-bit unsigned value
    codeword_32bit = codeword_32bit & 0xFFFFFFFF

    # Extract BCH codeword (bits 30-0, which is the 31-bit codeword)
    bch_codeword_31bit = codeword_32bit & 0x7FFFFFFF

    # BCH decode
    data_21bit, error_count, bch_ok = bch_decode(bch_codeword_31bit)

    # Determine if address or message codeword (bit 31)
    is_address = (codeword_32bit & (1 << 31)) == 0

    is_valid = bch_ok

    return (is_address, data_21bit, error_count, is_valid)


def compute_ric(address_bits, frame_position):
    """
    Compute the full 21-bit RIC from address bits and frame position.

    Args:
        address_bits: 18-bit address value (from codeword bits 30-13)
        frame_position: 3-bit frame position (0-7)

    Returns:
        21-bit RIC/CAP code
    """
    return (address_bits << 3) | (frame_position & 0x7)


def parse_address_codeword(codeword_32bit):
    """
    Parse address codeword and extract RIC and function type.

    Returns:
        Tuple (ric, function_type, error_count, is_valid)
    """
    is_address, data_21bit, error_count, is_valid = parse_codeword(codeword_32bit)

    if not is_address:
        return (None, None, -1, False)

    # Extract address and function from data
    address_bits = (data_21bit >> 3) & 0x3FFFF
    function_bits = data_21bit & 0x3

    # Note: frame position is embedded in the batch/frame structure, not here
    # Return just the address bits for now
    return (address_bits, function_bits, error_count, is_valid)


def encode_numeric_message(digits_string):
    """
    Encode a numeric message string to 20-bit chunks.
    Numeric encoding: 4 bits per digit
    0-9: normal, A=0x0A (space), B=0x0B (U), C=0x0C (hyphen), D=0x0D ([, E=0x0E (], F=0x0F (unused)

    Args:
        digits_string: String of digits and special chars

    Returns:
        List of 20-bit data values
    """
    # Map characters to 4-bit values
    char_map = {
        '0': 0x0, '1': 0x1, '2': 0x2, '3': 0x3, '4': 0x4,
        '5': 0x5, '6': 0x6, '7': 0x7, '8': 0x8, '9': 0x9,
        ' ': 0xA, 'U': 0xB, '-': 0xC, '[': 0xD, ']': 0xE,
    }

    # Convert string to 4-bit values
    nibbles = []
    for char in digits_string:
        if char in char_map:
            nibbles.append(char_map[char])
        else:
            nibbles.append(0xF)  # Unknown = unused

    # Pack nibbles into 20-bit chunks (5 nibbles per 20 bits)
    chunks = []
    for i in range(0, len(nibbles), 5):
        chunk_nibbles = nibbles[i:i+5]
        # Pad with 0xF if needed
        while len(chunk_nibbles) < 5:
            chunk_nibbles.append(0xF)

        # Pack MSB first
        value = 0
        for nibble in chunk_nibbles:
            value = (value << 4) | nibble
        chunks.append(value & 0xFFFFF)

    return chunks


def decode_numeric_message(data_chunks):
    """
    Decode numeric message from 20-bit chunks.

    Args:
        data_chunks: List of 20-bit values

    Returns:
        Decoded string
    """
    # Reverse map
    value_map = {
        0x0: '0', 0x1: '1', 0x2: '2', 0x3: '3', 0x4: '4',
        0x5: '5', 0x6: '6', 0x7: '7', 0x8: '8', 0x9: '9',
        0xA: ' ', 0xB: 'U', 0xC: '-', 0xD: '[', 0xE: ']',
        0xF: ''  # unused
    }

    result = []
    for chunk in data_chunks:
        # Extract 5 nibbles (4 bits each)
        for i in range(4, -1, -1):
            nibble = (chunk >> (i * 4)) & 0xF
            char = value_map.get(nibble, '')
            result.append(char)

    # Remove trailing unused characters
    while result and result[-1] == '':
        result.pop()

    return ''.join(result)


def encode_alpha_message(text):
    """
    Encode alphanumeric message to 20-bit chunks.
    Uses 7-bit ASCII, LSB first (bit 0 of character sent first).

    Args:
        text: ASCII text string

    Returns:
        List of 20-bit data values
    """
    # Convert text to 7-bit ASCII values (LSB first)
    bits = []
    for char in text:
        ascii_val = ord(char) & 0x7F
        for i in range(7):
            bits.append((ascii_val >> i) & 1)

    # Pack bits into 20-bit chunks
    chunks = []
    for i in range(0, len(bits), 20):
        chunk_bits = bits[i:i+20]
        # Pad with zeros if needed
        while len(chunk_bits) < 20:
            chunk_bits.append(0)

        # Pack MSB first (even though bits were LSB first)
        value = 0
        for bit in chunk_bits:
            value = (value << 1) | bit
        chunks.append(value & 0xFFFFF)

    return chunks


def decode_alpha_message(data_chunks):
    """
    Decode alphanumeric message from 20-bit chunks.

    Args:
        data_chunks: List of 20-bit values

    Returns:
        Decoded string
    """
    # Extract bits from chunks
    bits = []
    for chunk in data_chunks:
        for i in range(19, -1, -1):
            bits.append((chunk >> i) & 1)

    # Group into 7-bit characters (LSB first)
    result = []
    for i in range(0, len(bits) - 6, 7):
        char_bits = bits[i:i+7]
        # Convert from LSB-first to ASCII
        ascii_val = 0
        for j, bit in enumerate(char_bits):
            ascii_val |= (bit << j)

        char = chr(ascii_val & 0x7F)
        if char.isprintable() or char == ' ':
            result.append(char)

    return ''.join(result).rstrip('\x00')


def fsk_modulate(bits, sample_rate, baud_rate, mark_freq, space_freq):
    """
    Modulate a bit sequence using continuous-phase FSK.

    Args:
        bits: List or array of bits (0 or 1)
        sample_rate: Sample rate in Hz
        baud_rate: Baud rate in baud
        mark_freq: Frequency for mark (1) in Hz
        space_freq: Frequency for space (0) in Hz

    Returns:
        NumPy array of audio samples
    """
    bits = np.asarray(bits, dtype=np.int32)  # Use int32 instead of int8
    samples_per_bit = sample_rate // baud_rate
    total_samples = len(bits) * samples_per_bit

    # Generate continuous phase signal
    audio = np.zeros(total_samples, dtype=np.float32)
    phase = 0.0

    for bit_idx, bit in enumerate(bits):
        freq = mark_freq if bit else space_freq

        for sample_idx in range(samples_per_bit):
            sample_num = bit_idx * samples_per_bit + sample_idx
            phase += 2.0 * np.pi * freq / sample_rate
            audio[sample_num] = np.sin(phase)

    return audio


def fsk_demodulate(audio, sample_rate, baud_rate, mark_freq, space_freq, use_ook=False):
    """
    Demodulate FSK audio to bit sequence using tone detection.

    Args:
        audio: Audio samples (float array)
        sample_rate: Sample rate in Hz
        baud_rate: Baud rate in baud
        mark_freq: Frequency for mark (1) in Hz
        space_freq: Frequency for space (0) in Hz
        use_ook: If True, use simple threshold-based detection

    Returns:
        List of bits (0 or 1)
    """
    audio = np.asarray(audio, dtype=np.float64)
    samples_per_bit = sample_rate // baud_rate
    num_bits = len(audio) // samples_per_bit

    bits = []

    for bit_idx in range(num_bits):
        start_idx = bit_idx * samples_per_bit
        end_idx = start_idx + samples_per_bit

        if end_idx > len(audio):
            break

        bit_samples = audio[start_idx:end_idx]

        # Use FFT-like approach for more reliable detection
        # Create complex exponentials at mark and space frequencies
        t = np.arange(len(bit_samples)) / sample_rate

        mark_phase = 2.0 * np.pi * mark_freq * t
        space_phase = 2.0 * np.pi * space_freq * t

        mark_real = np.sum(bit_samples * np.cos(mark_phase))
        mark_imag = np.sum(bit_samples * np.sin(mark_phase))
        mark_power = mark_real*mark_real + mark_imag*mark_imag

        space_real = np.sum(bit_samples * np.cos(space_phase))
        space_imag = np.sum(bit_samples * np.sin(space_phase))
        space_power = space_real*space_real + space_imag*space_imag

        # Decode based on which frequency has more power
        bit = 1 if mark_power > space_power else 0
        bits.append(bit)

    return bits


def build_batch(frames_data):
    """
    Build a complete batch (sync + 8 frames of 2 codewords each).

    Args:
        frames_data: List of 8 frame data, where each frame is a list of 2 codewords (32-bit each)

    Returns:
        List of 32-bit codewords (1 sync + 16 data = 17 total)
    """
    codewords = [SYNC_WORD]

    for frame_data in frames_data:
        for codeword in frame_data:
            codewords.append(codeword)

    return codewords


def parse_batch(codewords, frame_position_offset=0):
    """
    Parse a batch of codewords and extract messages.

    Args:
        codewords: List of 32-bit codewords (should start with sync word)
        frame_position_offset: Frame offset for multi-batch transmission

    Returns:
        List of message dicts with keys: 'ric', 'function', 'text', 'numeric', 'errors'
    """
    messages = []

    # Skip sync word
    if codewords and codewords[0] == SYNC_WORD:
        codewords = codewords[1:]

    current_ric = None
    current_function = None
    message_chunks = []
    is_numeric = None

    for cw_idx, codeword in enumerate(codewords):
        frame_idx = cw_idx // 2
        frame_position = frame_idx % 8
        is_address = (codeword & (1 << 31)) == 0

        if is_address:
            # Save previous message if any
            if current_ric is not None and message_chunks:
                if is_numeric:
                    text = decode_numeric_message(message_chunks)
                else:
                    text = decode_alpha_message(message_chunks)
                messages.append({
                    'ric': current_ric,
                    'function': current_function,
                    'text': text,
                    'numeric': is_numeric,
                })

            # Parse new address
            addr_bits, func_bits, error_count, is_valid = parse_address_codeword(codeword)
            if is_valid and addr_bits is not None:
                current_ric = compute_ric(addr_bits, frame_position)
                current_function = func_bits
                message_chunks = []
                is_numeric = func_bits == 0  # Function 0 = numeric
        else:
            # Message codeword
            if current_ric is not None:
                _, msg_data, _, _ = parse_codeword(codeword)
                message_chunks.append(msg_data)

    # Save last message
    if current_ric is not None and message_chunks:
        if is_numeric:
            text = decode_numeric_message(message_chunks)
        else:
            text = decode_alpha_message(message_chunks)
        messages.append({
            'ric': current_ric,
            'function': current_function,
            'text': text,
            'numeric': is_numeric,
        })

    return messages


def find_sync_word_position(bits, tolerance=2):
    """
    Find the position of the first valid sync word in a bit sequence.
    Allows up to 'tolerance' bit errors (Hamming distance).

    Args:
        bits: Array of bits
        tolerance: Maximum Hamming distance allowed

    Returns:
        Index of sync word start, or -1 if not found
    """
    # Sliding window search
    for i in range(len(bits) - 31):
        # Extract 32 bits starting at position i
        candidate = 0
        for j in range(32):
            candidate = (candidate << 1) | int(bits[i + j])

        # Calculate Hamming distance to SYNC_WORD
        distance = _hamming_distance(candidate, SYNC_WORD)
        if distance <= tolerance:
            return i

    return -1


def bits_to_int(bits):
    """Convert a list of bits to an integer (MSB first)"""
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def int_to_bits(value, num_bits):
    """Convert an integer to a list of bits (MSB first)"""
    value = int(value) & ((1 << num_bits) - 1)  # Mask to num_bits
    bits = []
    for i in range(num_bits - 1, -1, -1):
        bits.append(int((value >> i) & 1))
    return bits
