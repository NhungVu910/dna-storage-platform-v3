"""
Randomization Module
Implements DNA sequence randomization using chaotic systems.

Supported chaos maps (ordered from simple to complex):
1. Logistic Map (1D) - Simplest, single equation
2. Henon Map (2D) - Two coupled equations  
3. Lorenz System (3D) - Three coupled differential equations

All systems use primer sequences as encryption keys.
"""

import math
import hashlib
from typing import Tuple, List, Optional
from collections import Counter
from enum import Enum


class ChaosSystem(Enum):
    """Available chaotic systems ordered by complexity."""
    LOGISTIC = "logistic"    # 1D - Simplest
    HENON = "henon"          # 2D - Medium complexity
    LORENZ = "lorenz"        # 3D - Most complex


# DNA nucleotide mapping for operations
NT_TO_INT = {'A': 0, 'T': 1, 'G': 2, 'C': 3}
INT_TO_NT = {0: 'A', 1: 'T', 2: 'G', 3: 'C'}


# =============================================================================
# DNA SEQUENCE ANALYSIS
# =============================================================================

def calculate_dna_characteristics(sequence: str) -> dict:
    """
    Calculate DNA sequence characteristics.
    
    Returns dict with:
    - length: sequence length
    - max_homopolymer: longest run of same nucleotide
    - gc_ratio: proportion of G and C nucleotides
    - shannon_entropy: information entropy of sequence
    """
    if not sequence:
        return {
            'length': 0,
            'max_homopolymer': 0,
            'gc_ratio': 0.0,
            'shannon_entropy': 0.0
        }
    
    sequence = sequence.upper()
    length = len(sequence)
    
    # Max homopolymer
    max_homo = calculate_max_homopolymer(sequence)
    
    # GC ratio
    gc_count = sequence.count('G') + sequence.count('C')
    gc_ratio = gc_count / length if length > 0 else 0.0
    
    # Shannon entropy
    entropy = calculate_shannon_entropy(sequence)
    
    return {
        'length': length,
        'max_homopolymer': max_homo,
        'gc_ratio': gc_ratio,
        'shannon_entropy': entropy
    }


def calculate_max_homopolymer(sequence: str) -> int:
    """Calculate the maximum homopolymer run length."""
    if not sequence:
        return 0
    
    max_run = 1
    current_run = 1
    
    for i in range(1, len(sequence)):
        if sequence[i] == sequence[i-1]:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    
    return max_run


def calculate_shannon_entropy(sequence: str) -> float:
    """Calculate Shannon entropy of the sequence."""
    if not sequence:
        return 0.0
    
    length = len(sequence)
    counts = Counter(sequence)
    
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)
    
    return entropy


# =============================================================================
# KEY DERIVATION
# =============================================================================

def derive_chaos_params(forward_primer: str, reverse_primer: str) -> bytes:
    """
    Derive deterministic parameters from primer sequences.
    Returns 32 bytes of key material for chaos system initialization.
    """
    combined = (forward_primer + reverse_primer).upper().encode()
    return hashlib.sha256(combined).digest()


def derive_multiple_keys(forward_primer: str, reverse_primer: str, 
                         num_keys: int = 3) -> List[bytes]:
    """Derive multiple keys for multi-layer transformations."""
    combined = (forward_primer + reverse_primer).upper().encode()
    
    keys = []
    for i in range(num_keys):
        material = combined + i.to_bytes(4, 'big')
        key = hashlib.sha256(material).digest()
        keys.append(key)
    
    return keys


# =============================================================================
# LOGISTIC MAP (1D) - Simplest chaotic system
# =============================================================================
# Equation: x_{n+1} = r * x_n * (1 - x_n)
# Chaotic for r ∈ [3.57, 4.0]

def generate_logistic_sequence(length: int, key: bytes) -> List[int]:
    """
    Generate chaotic sequence using Logistic Map.
    
    The Logistic Map is a simple 1D discrete dynamical system that exhibits
    chaotic behavior for certain parameter values.
    
    Parameters derived from key:
    - r: Growth rate parameter in [3.7, 3.99] (chaotic regime)
    - x0: Initial condition in (0, 1)
    """
    # Extract parameters from key
    r_norm = int.from_bytes(key[0:4], 'big') / (2**32)
    x0_norm = int.from_bytes(key[4:8], 'big') / (2**32)
    
    # Map to chaotic regime
    r = 3.7 + r_norm * 0.29  # r in [3.7, 3.99]
    x = 0.1 + x0_norm * 0.8   # x0 in [0.1, 0.9]
    
    # Skip transient period
    for _ in range(1000):
        x = r * x * (1 - x)
    
    # Generate sequence
    sequence = []
    for _ in range(length):
        x = r * x * (1 - x)
        # Map x ∈ (0,1) to 0-3
        value = int(x * 3.999)
        sequence.append(value)
    
    return sequence


# =============================================================================
# HENON MAP (2D) - Medium complexity
# =============================================================================
# Equations: x_{n+1} = 1 - a*x_n^2 + y_n
#            y_{n+1} = b*x_n
# Chaotic for a ≈ 1.4, b ≈ 0.3

def generate_henon_sequence(length: int, key: bytes) -> List[int]:
    """
    Generate chaotic sequence using Henon Map.
    
    The Henon Map is a 2D discrete dynamical system with two coupled equations.
    It produces a strange attractor with fractal structure.
    
    Parameters derived from key:
    - a: Quadratic coefficient in [1.2, 1.4] (chaotic regime)
    - b: Linear coefficient in [0.2, 0.4]
    - x0, y0: Initial conditions
    """
    # Extract parameters from key
    h1 = int.from_bytes(key[0:4], 'big') / (2**32)
    h2 = int.from_bytes(key[4:8], 'big') / (2**32)
    h3 = int.from_bytes(key[8:12], 'big') / (2**32)
    h4 = int.from_bytes(key[12:16], 'big') / (2**32)
    
    # Map to chaotic regime
    a = 1.2 + h1 * 0.2   # a in [1.2, 1.4]
    b = 0.2 + h2 * 0.2   # b in [0.2, 0.4]
    x = -1.0 + h3 * 0.5  # x0 in [-1.0, -0.5]
    y = -0.5 + h4 * 0.5  # y0 in [-0.5, 0.0]
    
    # Skip transient period
    for _ in range(1000):
        x_new = 1 - a * x * x + y
        y_new = b * x
        x, y = x_new, y_new
    
    # Generate sequence
    sequence = []
    for _ in range(length):
        x_new = 1 - a * x * x + y
        y_new = b * x
        x, y = x_new, y_new
        
        # Map x to 0-3 (x typically in [-1.5, 1.5])
        normalized = (x + 1.5) / 3.0
        normalized = max(0.0, min(0.9999, normalized))
        value = int(normalized * 4)
        sequence.append(value)
    
    return sequence


# =============================================================================
# LORENZ SYSTEM (3D) - Most complex
# =============================================================================
# Equations: dx/dt = σ(y - x)
#            dy/dt = x(ρ - z) - y
#            dz/dt = xy - βz
# Classic chaotic parameters: σ=10, ρ=28, β=8/3

def generate_lorenz_sequence(length: int, key: bytes) -> List[int]:
    """
    Generate chaotic sequence using Lorenz System.
    
    The Lorenz System is a 3D continuous dynamical system (solved via RK4)
    that exhibits the famous "butterfly" strange attractor.
    
    Parameters derived from key:
    - σ (sigma): Prandtl number in [9, 11]
    - ρ (rho): Rayleigh number in [26, 30]
    - β (beta): Geometric factor in [2.5, 3.0]
    - x0, y0, z0: Initial conditions
    """
    # Extract parameters from key
    h1 = int.from_bytes(key[0:4], 'big') / (2**32)
    h2 = int.from_bytes(key[4:8], 'big') / (2**32)
    h3 = int.from_bytes(key[8:12], 'big') / (2**32)
    h4 = int.from_bytes(key[12:16], 'big') / (2**32)
    h5 = int.from_bytes(key[16:20], 'big') / (2**32)
    h6 = int.from_bytes(key[20:24], 'big') / (2**32)
    
    # Lorenz parameters (slightly varied from classic for key-dependence)
    sigma = 9.0 + h1 * 2.0   # σ in [9, 11]
    rho = 26.0 + h2 * 4.0    # ρ in [26, 30]
    beta = 2.5 + h3 * 0.5    # β in [2.5, 3.0]
    
    # Initial conditions
    x = -10.0 + h4 * 20.0    # x0 in [-10, 10]
    y = -10.0 + h5 * 20.0    # y0 in [-10, 10]
    z = 20.0 + h6 * 20.0     # z0 in [20, 40]
    
    # Integration step size
    dt = 0.01
    
    def lorenz_derivatives(x, y, z):
        """Compute Lorenz system derivatives."""
        dx = sigma * (y - x)
        dy = x * (rho - z) - y
        dz = x * y - beta * z
        return dx, dy, dz
    
    def rk4_step(x, y, z, dt):
        """4th-order Runge-Kutta integration step."""
        k1x, k1y, k1z = lorenz_derivatives(x, y, z)
        k2x, k2y, k2z = lorenz_derivatives(x + 0.5*dt*k1x, y + 0.5*dt*k1y, z + 0.5*dt*k1z)
        k3x, k3y, k3z = lorenz_derivatives(x + 0.5*dt*k2x, y + 0.5*dt*k2y, z + 0.5*dt*k2z)
        k4x, k4y, k4z = lorenz_derivatives(x + dt*k3x, y + dt*k3y, z + dt*k3z)
        
        x_new = x + (dt/6) * (k1x + 2*k2x + 2*k3x + k4x)
        y_new = y + (dt/6) * (k1y + 2*k2y + 2*k3y + k4y)
        z_new = z + (dt/6) * (k1z + 2*k2z + 2*k3z + k4z)
        
        return x_new, y_new, z_new
    
    # Skip transient period (1000 RK4 steps)
    for _ in range(1000):
        x, y, z = rk4_step(x, y, z, dt)
    
    # Generate sequence
    sequence = []
    for _ in range(length):
        # Multiple RK4 steps per output for better mixing
        for _ in range(5):
            x, y, z = rk4_step(x, y, z, dt)
        
        # Combine all three dimensions for output
        # x typically in [-20, 20], y in [-30, 30], z in [0, 50]
        combined = (x + 20) / 40.0 + (y + 30) / 60.0 + z / 50.0
        normalized = (combined / 3.0) % 1.0
        value = int(normalized * 4)
        sequence.append(value)
    
    return sequence


# =============================================================================
# UNIFIED CHAOS INTERFACE
# =============================================================================

def generate_chaotic_sequence(length: int, key: bytes, 
                               system: ChaosSystem = ChaosSystem.HENON) -> List[int]:
    """
    Generate a chaotic sequence using the specified system.
    
    Args:
        length: Number of values to generate
        key: 32-byte key for parameter initialization
        system: Which chaotic system to use
    
    Returns:
        List of integers in range [0, 3]
    """
    if system == ChaosSystem.LOGISTIC:
        return generate_logistic_sequence(length, key)
    elif system == ChaosSystem.HENON:
        return generate_henon_sequence(length, key)
    elif system == ChaosSystem.LORENZ:
        return generate_lorenz_sequence(length, key)
    else:
        raise ValueError(f"Unknown chaos system: {system}")


# =============================================================================
# TRANSFORMATION LAYERS
# =============================================================================

def generate_permutation(length: int, key: bytes, 
                         system: ChaosSystem = ChaosSystem.HENON) -> List[int]:
    """
    Generate a permutation sequence using chaos-based randomness.
    Uses Fisher-Yates shuffle with chaotic sequence.
    """
    perm = list(range(length))
    chaos_seq = generate_chaotic_sequence(length, key, system)
    
    # Fisher-Yates shuffle
    for i in range(length - 1, 0, -1):
        j = (chaos_seq[i] * (i + 1)) % (i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    
    return perm


def apply_substitution(sequence: str, key: bytes, 
                       system: ChaosSystem = ChaosSystem.HENON) -> str:
    """
    Apply position-dependent substitution using chaotic sequence.
    Each position gets a different transformation.
    """
    chaos_seq = generate_chaotic_sequence(len(sequence), key, system)
    
    result = []
    for i, nt in enumerate(sequence):
        if nt in NT_TO_INT:
            original_val = NT_TO_INT[nt]
            new_val = (original_val + chaos_seq[i]) % 4
            result.append(INT_TO_NT[new_val])
        else:
            result.append(nt)
    
    return ''.join(result)


def reverse_substitution(sequence: str, key: bytes,
                         system: ChaosSystem = ChaosSystem.HENON) -> str:
    """Reverse the position-dependent substitution."""
    chaos_seq = generate_chaotic_sequence(len(sequence), key, system)
    
    result = []
    for i, nt in enumerate(sequence):
        if nt in NT_TO_INT:
            scrambled_val = NT_TO_INT[nt]
            original_val = (scrambled_val - chaos_seq[i]) % 4
            result.append(INT_TO_NT[original_val])
        else:
            result.append(nt)
    
    return ''.join(result)


def apply_permutation(sequence: str, perm: List[int]) -> str:
    """Apply permutation to shuffle sequence positions."""
    result = [''] * len(sequence)
    for i, p in enumerate(perm):
        result[p] = sequence[i]
    return ''.join(result)


def reverse_permutation(sequence: str, perm: List[int]) -> str:
    """Reverse the permutation to restore original positions."""
    result = [''] * len(sequence)
    for i, p in enumerate(perm):
        result[i] = sequence[p]
    return ''.join(result)


def apply_diffusion(sequence: str, key: bytes,
                    system: ChaosSystem = ChaosSystem.HENON) -> str:
    """
    Apply diffusion layer - each nucleotide depends on neighbors.
    This spreads changes throughout the sequence.
    """
    if len(sequence) < 2:
        return sequence
    
    chaos_seq = generate_chaotic_sequence(len(sequence), key, system)
    seq_list = list(sequence)
    
    # Forward pass: each position depends on previous
    for i in range(1, len(seq_list)):
        if seq_list[i] in NT_TO_INT and seq_list[i-1] in NT_TO_INT:
            prev_val = NT_TO_INT[seq_list[i-1]]
            curr_val = NT_TO_INT[seq_list[i]]
            new_val = (curr_val + prev_val + chaos_seq[i]) % 4
            seq_list[i] = INT_TO_NT[new_val]
    
    return ''.join(seq_list)


def reverse_diffusion(sequence: str, key: bytes,
                      system: ChaosSystem = ChaosSystem.HENON) -> str:
    """Reverse the diffusion layer."""
    if len(sequence) < 2:
        return sequence
    
    chaos_seq = generate_chaotic_sequence(len(sequence), key, system)
    seq_list = list(sequence)
    
    # Backward pass: reverse the forward diffusion
    for i in range(len(seq_list) - 1, 0, -1):
        if seq_list[i] in NT_TO_INT and seq_list[i-1] in NT_TO_INT:
            prev_val = NT_TO_INT[seq_list[i-1]]
            curr_val = NT_TO_INT[seq_list[i]]
            original_val = (curr_val - prev_val - chaos_seq[i]) % 4
            seq_list[i] = INT_TO_NT[original_val]
    
    return ''.join(seq_list)


# =============================================================================
# MAIN RANDOMIZATION FUNCTIONS
# =============================================================================

def randomize_dna_single(sequence: str, keys: List[bytes], 
                         system: ChaosSystem) -> str:
    """
    Apply single chaos system randomization.
    
    Args:
        sequence: DNA sequence to randomize
        keys: List of 3 keys for substitution, permutation, diffusion
        system: Chaotic system to use
    
    Returns:
        Randomized DNA sequence
    """
    result = sequence
    
    # Layer 1: Substitution
    result = apply_substitution(result, keys[0], system)
    
    # Layer 2: Permutation
    perm = generate_permutation(len(result), keys[1], system)
    result = apply_permutation(result, perm)
    
    # Layer 3: Diffusion
    result = apply_diffusion(result, keys[2], system)
    
    return result


def derandomize_dna_single(sequence: str, keys: List[bytes],
                           system: ChaosSystem) -> str:
    """
    Reverse single chaos system randomization.
    
    Args:
        sequence: Randomized DNA sequence
        keys: List of 3 keys used during randomization
        system: Chaotic system used
    
    Returns:
        Original DNA sequence
    """
    result = sequence
    
    # Reverse Layer 3: Diffusion
    result = reverse_diffusion(result, keys[2], system)
    
    # Reverse Layer 2: Permutation
    perm = generate_permutation(len(result), keys[1], system)
    result = reverse_permutation(result, perm)
    
    # Reverse Layer 1: Substitution
    result = reverse_substitution(result, keys[0], system)
    
    return result


def randomize_dna(sequence: str, forward_primer: str, reverse_primer: str,
                  system: ChaosSystem = ChaosSystem.HENON,
                  systems: Optional[List[ChaosSystem]] = None) -> str:
    """
    Randomize DNA sequence using chaos-based scrambling.
    
    Can use a single system or chain multiple systems for enhanced security.
    When multiple systems are used, they are applied in order, each adding
    another layer of randomization.
    
    Applies three transformation layers per system:
    1. Substitution: Position-dependent nucleotide transformation
    2. Permutation: Shuffle positions using chaotic sequence
    3. Diffusion: Spread dependencies across the sequence
    
    Args:
        sequence: Original DNA sequence
        forward_primer: Forward primer sequence (key part 1)
        reverse_primer: Reverse primer sequence (key part 2)
        system: Single chaotic system to use (ignored if systems is provided)
        systems: List of chaotic systems to chain (e.g., [LOGISTIC, HENON, LORENZ])
    
    Returns:
        Randomized DNA sequence
    """
    if not sequence or not forward_primer or not reverse_primer:
        return sequence
    
    sequence = sequence.upper()
    
    # Determine which systems to use
    if systems is None or len(systems) == 0:
        systems = [system]
    
    # Derive keys for all systems (3 keys per system)
    total_keys_needed = len(systems) * 3
    all_keys = derive_multiple_keys(forward_primer, reverse_primer, num_keys=total_keys_needed)
    
    result = sequence
    
    # Apply each system in order
    for i, sys in enumerate(systems):
        key_offset = i * 3
        system_keys = all_keys[key_offset:key_offset + 3]
        result = randomize_dna_single(result, system_keys, sys)
    
    return result


def derandomize_dna(sequence: str, forward_primer: str, reverse_primer: str,
                    system: ChaosSystem = ChaosSystem.HENON,
                    systems: Optional[List[ChaosSystem]] = None) -> str:
    """
    Reverse the randomization of a DNA sequence.
    
    Must use the same system(s) in the same order as randomization.
    
    Args:
        sequence: Randomized DNA sequence
        forward_primer: Forward primer sequence (key part 1)
        reverse_primer: Reverse primer sequence (key part 2)
        system: Single chaotic system used (ignored if systems is provided)
        systems: List of chaotic systems that were chained
    
    Returns:
        Original DNA sequence
    """
    if not sequence or not forward_primer or not reverse_primer:
        return sequence
    
    sequence = sequence.upper()
    
    # Determine which systems were used
    if systems is None or len(systems) == 0:
        systems = [system]
    
    # Derive same keys
    total_keys_needed = len(systems) * 3
    all_keys = derive_multiple_keys(forward_primer, reverse_primer, num_keys=total_keys_needed)
    
    result = sequence
    
    # Reverse each system in REVERSE order
    for i in range(len(systems) - 1, -1, -1):
        sys = systems[i]
        key_offset = i * 3
        system_keys = all_keys[key_offset:key_offset + 3]
        result = derandomize_dna_single(result, system_keys, sys)
    
    return result


def verify_randomization(original: str, randomized: str, 
                         forward_primer: str, reverse_primer: str,
                         system: ChaosSystem = ChaosSystem.HENON,
                         systems: Optional[List[ChaosSystem]] = None) -> bool:
    """
    Verify that randomization/derandomization works correctly.
    """
    derandomized = derandomize_dna(randomized, forward_primer, reverse_primer, 
                                    system=system, systems=systems)
    return derandomized == original.upper()


def get_chain_description(systems: List[ChaosSystem]) -> str:
    """Get a human-readable description of a chaos system chain."""
    if not systems:
        return "None"
    
    names = [get_chaos_system_info(s)['name'] for s in systems]
    return " → ".join(names)


def get_chain_complexity(systems: List[ChaosSystem]) -> dict:
    """Calculate the total complexity of a chaos system chain."""
    if not systems:
        return {'total_dimensions': 0, 'total_layers': 0, 'description': 'None'}
    
    total_dims = sum(get_chaos_system_info(s)['dimensions'] for s in systems)
    total_layers = len(systems) * 3  # 3 layers per system
    
    if len(systems) == 1:
        complexity = get_chaos_system_info(systems[0])['complexity']
    elif len(systems) == 2:
        complexity = 'High'
    else:
        complexity = 'Maximum'
    
    return {
        'total_dimensions': total_dims,
        'total_layers': total_layers,
        'num_systems': len(systems),
        'complexity': complexity,
        'description': get_chain_description(systems)
    }


def calculate_randomization_improvement(original_chars: dict, 
                                        randomized_chars: dict) -> dict:
    """
    Calculate how much the randomization improved sequence characteristics.
    """
    improvements = {}
    
    # Lower max homopolymer is better
    if original_chars['max_homopolymer'] > 0:
        homo_improvement = ((original_chars['max_homopolymer'] - 
                            randomized_chars['max_homopolymer']) / 
                           original_chars['max_homopolymer'] * 100)
        improvements['homopolymer_reduction'] = homo_improvement
    
    # GC ratio closer to 0.5 is better
    original_gc_deviation = abs(original_chars['gc_ratio'] - 0.5)
    randomized_gc_deviation = abs(randomized_chars['gc_ratio'] - 0.5)
    if original_gc_deviation > 0:
        gc_improvement = ((original_gc_deviation - randomized_gc_deviation) / 
                         original_gc_deviation * 100)
        improvements['gc_balance_improvement'] = gc_improvement
    
    # Higher entropy is better (max is 2.0 for 4 symbols)
    if original_chars['shannon_entropy'] > 0:
        entropy_improvement = ((randomized_chars['shannon_entropy'] - 
                               original_chars['shannon_entropy']) / 
                              original_chars['shannon_entropy'] * 100)
        improvements['entropy_improvement'] = entropy_improvement
    
    return improvements


# =============================================================================
# CHAOS SYSTEM INFO
# =============================================================================

def get_chaos_system_info(system: ChaosSystem) -> dict:
    """Get information about a chaos system."""
    info = {
        ChaosSystem.LOGISTIC: {
            'name': 'Logistic Map',
            'dimensions': 1,
            'complexity': 'Simple',
            'equation': 'x_{n+1} = r·x_n·(1 - x_n)',
            'description': 'One-dimensional discrete map. Simple but effective for basic randomization.',
            'parameters': ['r: growth rate (3.7-3.99)', 'x₀: initial value (0.1-0.9)']
        },
        ChaosSystem.HENON: {
            'name': 'Hénon Map',
            'dimensions': 2,
            'complexity': 'Medium',
            'equation': 'x_{n+1} = 1 - a·x_n² + y_n, y_{n+1} = b·x_n',
            'description': 'Two-dimensional discrete map with strange attractor. Good balance of security and speed.',
            'parameters': ['a: quadratic term (1.2-1.4)', 'b: linear term (0.2-0.4)', 'x₀, y₀: initial values']
        },
        ChaosSystem.LORENZ: {
            'name': 'Lorenz System',
            'dimensions': 3,
            'complexity': 'High',
            'equation': 'dx/dt = σ(y-x), dy/dt = x(ρ-z)-y, dz/dt = xy-βz',
            'description': 'Three-dimensional continuous system (butterfly attractor). Highest complexity and security.',
            'parameters': ['σ: Prandtl number (9-11)', 'ρ: Rayleigh number (26-30)', 'β: geometric factor (2.5-3.0)', 'x₀, y₀, z₀: initial values']
        }
    }
    return info.get(system, {})


def list_chaos_systems() -> List[dict]:
    """List all available chaos systems with their info."""
    return [
        {'system': ChaosSystem.LOGISTIC, **get_chaos_system_info(ChaosSystem.LOGISTIC)},
        {'system': ChaosSystem.HENON, **get_chaos_system_info(ChaosSystem.HENON)},
        {'system': ChaosSystem.LORENZ, **get_chaos_system_info(ChaosSystem.LORENZ)},
    ]
