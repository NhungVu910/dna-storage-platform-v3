"""
DNA Codec Module
Handles binary-to-DNA encoding and DNA-to-binary decoding using quaternary mapping.
"""

import struct
from typing import Tuple, Optional

# DNA mapping: 2 bits -> 1 nucleotide
BINARY_TO_DNA = {
    '00': 'A',
    '01': 'T',
    '10': 'G',
    '11': 'C'
}

DNA_TO_BINARY = {v: k for k, v in BINARY_TO_DNA.items()}


def bytes_to_binary(data: bytes) -> str:
    """Convert bytes to binary string."""
    return ''.join(format(byte, '08b') for byte in data)


def binary_to_bytes(binary_str: str) -> bytes:
    """Convert binary string to bytes."""
    # Pad to multiple of 8
    padding = (8 - len(binary_str) % 8) % 8
    binary_str = binary_str + '0' * padding
    
    byte_list = []
    for i in range(0, len(binary_str), 8):
        byte_list.append(int(binary_str[i:i+8], 2))
    return bytes(byte_list)


def encode_to_dna(data: bytes, compressed: bool = False, 
                  compression_type: str = 'none', 
                  original_extension: str = '') -> str:
    """
    Encode binary data to DNA sequence.
    
    Metadata format (embedded at start):
    - 8 nucleotides: Magic marker 'DNASTOR1'
    - 4 nucleotides: Compression flag and type
    - 16 nucleotides: Original data length (32-bit)
    - 8 nucleotides: Extension length + extension (variable)
    """
    # Create metadata
    metadata = create_metadata(compressed, compression_type, 
                               len(data), original_extension)
    
    # Convert data to binary
    binary_data = bytes_to_binary(data)
    
    # Pad binary to multiple of 2 for DNA encoding
    if len(binary_data) % 2 != 0:
        binary_data += '0'
    
    # Convert to DNA
    dna_sequence = ''
    for i in range(0, len(binary_data), 2):
        dna_sequence += BINARY_TO_DNA[binary_data[i:i+2]]
    
    return metadata + dna_sequence


def create_metadata(compressed: bool, compression_type: str, 
                    data_length: int, extension: str) -> str:
    """Create metadata header for DNA sequence."""
    # Magic marker: 'DNASTOR1' encoded
    magic = 'ATGCATGC'  # Fixed 8-nt marker
    
    # Compression info (4 nucleotides = 8 bits)
    # Support: none, brotli, webp, pdf_gs, pdf_opt, flac, mp3, aac, h264, av1
    comp_types = {'none': 0, 'brotli': 1, 'webp': 2, 'pdf_gs': 3, 'pdf_opt': 4, 'flac': 5, 'mp3': 6, 'aac': 7, 'h264': 8, 'av1': 9}
    comp_byte = (1 if compressed else 0) | (comp_types.get(compression_type, 0) << 1)
    comp_dna = encode_int_to_dna(comp_byte, 4)
    
    # Data length (16 nucleotides = 32 bits)
    length_dna = encode_int_to_dna(data_length, 16)
    
    # Extension (4 nucleotides for length + variable for extension)
    ext_bytes = extension.encode('utf-8')
    ext_len_dna = encode_int_to_dna(len(ext_bytes), 4)
    ext_dna = encode_bytes_to_dna(ext_bytes)
    
    return magic + comp_dna + length_dna + ext_len_dna + ext_dna


def encode_int_to_dna(value: int, num_nucleotides: int) -> str:
    """Encode integer to DNA sequence of specified length."""
    num_bits = num_nucleotides * 2
    binary = format(value, f'0{num_bits}b')
    dna = ''
    for i in range(0, len(binary), 2):
        dna += BINARY_TO_DNA[binary[i:i+2]]
    return dna


def encode_bytes_to_dna(data: bytes) -> str:
    """Encode bytes to DNA sequence."""
    binary = bytes_to_binary(data)
    if len(binary) % 2 != 0:
        binary += '0'
    dna = ''
    for i in range(0, len(binary), 2):
        dna += BINARY_TO_DNA[binary[i:i+2]]
    return dna


def decode_from_dna(dna_sequence: str) -> Tuple[bytes, dict]:
    """
    Decode DNA sequence back to binary data.
    Returns tuple of (data, metadata_dict)
    """
    # Parse metadata
    metadata, payload_start = parse_metadata(dna_sequence)
    
    # Extract payload
    payload_dna = dna_sequence[payload_start:]
    
    # Convert DNA to binary
    binary_data = ''
    for nt in payload_dna:
        if nt in DNA_TO_BINARY:
            binary_data += DNA_TO_BINARY[nt]
    
    # Convert binary to bytes
    data = binary_to_bytes(binary_data)
    
    # Trim to original length
    if metadata['data_length'] > 0:
        data = data[:metadata['data_length']]
    
    return data, metadata


def parse_metadata(dna_sequence: str) -> Tuple[dict, int]:
    """Parse metadata from DNA sequence header."""
    pos = 0
    
    # Skip magic marker (8 nucleotides)
    magic = dna_sequence[pos:pos+8]
    pos += 8
    
    # Compression info (4 nucleotides)
    comp_dna = dna_sequence[pos:pos+4]
    comp_byte = decode_dna_to_int(comp_dna)
    compressed = bool(comp_byte & 1)
    comp_type_id = (comp_byte >> 1) & 0x0F  # 4 bits for compression type
    comp_types = {0: 'none', 1: 'brotli', 2: 'webp', 3: 'pdf_gs', 4: 'pdf_opt', 5: 'flac', 6: 'mp3', 7: 'aac', 8: 'h264', 9: 'av1'}
    compression_type = comp_types.get(comp_type_id, 'none')
    pos += 4
    
    # Data length (16 nucleotides)
    length_dna = dna_sequence[pos:pos+16]
    data_length = decode_dna_to_int(length_dna)
    pos += 16
    
    # Extension length (4 nucleotides)
    ext_len_dna = dna_sequence[pos:pos+4]
    ext_len = decode_dna_to_int(ext_len_dna)
    pos += 4
    
    # Extension (variable)
    ext_nucleotides = (ext_len * 8 + 1) // 2  # Ceiling division for bits to nucleotides
    ext_dna = dna_sequence[pos:pos+ext_nucleotides]
    extension = decode_dna_to_bytes(ext_dna)[:ext_len].decode('utf-8', errors='ignore')
    pos += ext_nucleotides
    
    metadata = {
        'magic': magic,
        'compressed': compressed,
        'compression_type': compression_type,
        'data_length': data_length,
        'extension': extension
    }
    
    return metadata, pos


def decode_dna_to_int(dna: str) -> int:
    """Decode DNA sequence to integer."""
    binary = ''
    for nt in dna:
        if nt in DNA_TO_BINARY:
            binary += DNA_TO_BINARY[nt]
    return int(binary, 2) if binary else 0


def decode_dna_to_bytes(dna: str) -> bytes:
    """Decode DNA sequence to bytes."""
    binary = ''
    for nt in dna:
        if nt in DNA_TO_BINARY:
            binary += DNA_TO_BINARY[nt]
    return binary_to_bytes(binary)


def calculate_encoding_density(original_size: int, dna_length: int) -> float:
    """
    Calculate encoding density in bits per nucleotide.
    Theoretical max for quaternary encoding: 2 bits/nt
    """
    if dna_length == 0:
        return 0.0
    original_bits = original_size * 8
    return original_bits / dna_length


def validate_dna_sequence(sequence: str) -> bool:
    """Validate that sequence contains only valid DNA characters."""
    valid_chars = set('ATGC')
    return all(c in valid_chars for c in sequence.upper())
