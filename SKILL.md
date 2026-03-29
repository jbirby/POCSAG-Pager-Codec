---
name: pocsag-codec
description: >
  Encode and decode POCSAG paging messages in audio WAV format. POCSAG is the
  dominant paging protocol worldwide, used in hospitals, fire departments,
  restaurants, and emergency services. Supports 512/1200/2400 baud FSK with
  BCH(31,21) error correction. Use this skill whenever the user mentions POCSAG,
  pager, paging, alphanumeric pager, hospital pager, restaurant pager, fire pager,
  Cap Code, RIC, pager decoder, SDR pager decode, or wants to create/analyze
  pager audio WAV files. Covers encoding (messages to WAV) and decoding
  (WAV to messages).
---

# POCSAG Pager Codec

Encode and decode POCSAG (Post Office Code Standardisation Advisory Group) paging messages in audio WAV format. POCSAG is the dominant paging protocol worldwide, used in hospitals, fire departments, restaurants, emergency services, and personal pagers. Operates on VHF/UHF frequencies with 2-FSK (Frequency Shift Keying) modulation at 512, 1200, or 2400 baud rates.

## Triggers

POCSAG, pager, paging, alphanumeric pager, numeric pager, hospital pager, restaurant pager, fire pager, Cap Code, RIC, Radio Identity Code, pager decoder, pager tones, two-tone paging, SDR pager decode, pager WAV, pager audio, pager message, tone-only pager

## Key Features

- **Encode**: Create POCSAG WAV files with custom messages, addresses, and baud rates
- **Decode**: Extract messages, addresses, and metadata from SDR recordings of pager traffic
- **Auto-detection**: Automatically detects baud rate (512, 1200, 2400)
- **Error correction**: BCH(31,21) error correction with 2-bit error correction capability
- **Message types**: Numeric (digits + special chars), alphanumeric (7-bit ASCII), tone-only
- **Robust sync**: Tolerates bit errors when finding sync codewords (Hamming distance ≤ 2)

## Usage

### Decode a pager WAV recording from your SDR

Simply provide the WAV file and the decoder will:
1. Detect the baud rate automatically
2. Find the preamble and sync codewords
3. Extract and correct errors in all messages
4. Display all captured pager messages with addresses and text

Output includes RIC/Cap Code, function type, and decoded message text.

### Encode a test transmission

Create a WAV file with a custom message, address, and settings.

## What is POCSAG?

POCSAG is the international standard for one-way paging. It operates on dedicated VHF/UHF frequencies (common US frequencies: 152.0075, 157.450, 152.480, 931.9375 MHz). Each pager has a unique Radio Identity Code (RIC), also called CAP code, which identifies it within the paging network. Messages are sent at 512, 1200, or 2400 baud with FSK modulation at ±4.5 kHz deviation. The protocol uses BCH error correction to survive channel noise and interference common in radio environments.

POCSAG frames contain an address codeword (identifying the target pager) followed by one or more message codewords (containing the actual message data). Multiple pagers can be addressed in a single transmission batch.
