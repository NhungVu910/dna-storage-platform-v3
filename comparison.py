"""
Comparison Module
Calculate quality metrics for comparing original and reconstructed data.
"""

import io
import math
import numpy as np
from PIL import Image
from typing import Tuple, Optional


def detect_comparison_type(filename: str, data: bytes) -> str:
    """
    Detect the type of comparison to perform based on file.
    Returns: 'text', 'image', 'pdf', 'audio', 'video', or 'binary'
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    
    text_extensions = {'.txt', '.csv', '.json', '.xml', '.html', '.md', '.log', '.py', '.js', '.css'}
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
    pdf_extensions = {'.pdf'}
    audio_extensions = {'.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.aif'}
    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'}
    
    if ext in text_extensions:
        return 'text'
    elif ext in image_extensions:
        return 'image'
    elif ext in pdf_extensions:
        return 'pdf'
    elif ext in audio_extensions:
        return 'audio'
    elif ext in video_extensions:
        return 'video'
    
    # Try content-based detection
    if data[:4] == b'%PDF':
        return 'pdf'
    
    # Video signatures
    # MP4/M4V: ftyp at offset 4
    if len(data) >= 12 and data[4:8] == b'ftyp':
        ftyp_brand = data[8:12]
        video_brands = [b'mp41', b'mp42', b'isom', b'avc1', b'M4V ', b'M4VP', b'qt  ']
        audio_brands = [b'M4A ', b'mp4a']
        if ftyp_brand in video_brands:
            return 'video'
        elif ftyp_brand in audio_brands:
            return 'audio'
        return 'video'  # Default ftyp to video
    
    # AVI: RIFF....AVI
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'AVI ':
        return 'video'
    
    # MKV/WebM
    if len(data) >= 4 and data[:4] == b'\x1a\x45\xdf\xa3':
        return 'video'
    
    # MOV atoms
    if len(data) >= 8 and data[4:8] in [b'moov', b'mdat', b'wide', b'free']:
        return 'video'
    
    # FLV
    if len(data) >= 3 and data[:3] == b'FLV':
        return 'video'
    
    # Audio signatures
    if data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WAVE':
        return 'audio'
    if data[:3] == b'ID3' or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return 'audio'
    if data[:4] == b'fLaC':
        return 'audio'
    if data[:4] == b'OggS':
        return 'audio'
    
    # Image signatures
    if data[:8] == b'\x89PNG\r\n\x1a\n' or data[:2] == b'\xff\xd8':
        return 'image'
    
    try:
        data.decode('utf-8')
        return 'text'
    except:
        return 'binary'


def compare_text(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed text data.
    
    Metrics:
    - Accuracy (%): Percentage of matching characters
    - Bit Error Rate (BER): Proportion of differing bits
    """
    # Decode as text
    try:
        orig_text = original.decode('utf-8')
        recon_text = reconstructed.decode('utf-8')
    except:
        # Fall back to binary comparison
        orig_text = original.decode('latin-1')
        recon_text = reconstructed.decode('latin-1')
    
    # Character accuracy
    max_len = max(len(orig_text), len(recon_text))
    if max_len == 0:
        return {'accuracy': 100.0, 'bit_error_rate': 0.0, 'match': True}
    
    # Pad shorter string
    orig_padded = orig_text.ljust(max_len, '\x00')
    recon_padded = recon_text.ljust(max_len, '\x00')
    
    matching_chars = sum(1 for a, b in zip(orig_padded, recon_padded) if a == b)
    accuracy = (matching_chars / max_len) * 100
    
    # Bit Error Rate
    total_bits = 0
    error_bits = 0
    
    for a, b in zip(original, reconstructed):
        total_bits += 8
        xor = a ^ b
        error_bits += bin(xor).count('1')
    
    # Account for length difference
    len_diff = abs(len(original) - len(reconstructed))
    total_bits += len_diff * 8
    error_bits += len_diff * 8  # Assume all bits differ for missing bytes
    
    ber = error_bits / total_bits if total_bits > 0 else 0.0
    
    return {
        'accuracy': accuracy,
        'bit_error_rate': ber,
        'character_matches': matching_chars,
        'total_characters': max_len,
        'original_length': len(orig_text),
        'reconstructed_length': len(recon_text),
        'match': original == reconstructed
    }


def compare_binary(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed binary data.
    
    Metrics:
    - Accuracy (%): Percentage of matching bytes
    - Bit Error Rate (BER): Proportion of differing bits
    """
    max_len = max(len(original), len(reconstructed))
    if max_len == 0:
        return {'accuracy': 100.0, 'bit_error_rate': 0.0, 'match': True}
    
    # Byte accuracy
    min_len = min(len(original), len(reconstructed))
    matching_bytes = sum(1 for i in range(min_len) if original[i] == reconstructed[i])
    accuracy = (matching_bytes / max_len) * 100
    
    # Bit Error Rate
    total_bits = 0
    error_bits = 0
    
    for i in range(min_len):
        total_bits += 8
        xor = original[i] ^ reconstructed[i]
        error_bits += bin(xor).count('1')
    
    # Account for length difference
    len_diff = abs(len(original) - len(reconstructed))
    total_bits += len_diff * 8
    error_bits += len_diff * 8
    
    ber = error_bits / total_bits if total_bits > 0 else 0.0
    
    return {
        'accuracy': accuracy,
        'bit_error_rate': ber,
        'byte_matches': matching_bytes,
        'total_bytes': max_len,
        'original_size': len(original),
        'reconstructed_size': len(reconstructed),
        'match': original == reconstructed
    }


def compare_image(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed image data.
    
    Metrics:
    - SSIM (Structural Similarity Index): -1 to 1, 1 is perfect
    - PSNR (Peak Signal-to-Noise Ratio): dB, higher is better
    - MSE (Mean Squared Error): 0 is perfect
    """
    try:
        # Load images
        orig_img = Image.open(io.BytesIO(original))
        recon_img = Image.open(io.BytesIO(reconstructed))
        
        # Convert to same mode and size for comparison
        if orig_img.mode != recon_img.mode:
            # Convert both to RGB for fair comparison
            if orig_img.mode in ('RGBA', 'LA', 'P'):
                orig_img = orig_img.convert('RGBA')
            else:
                orig_img = orig_img.convert('RGB')
            
            if recon_img.mode in ('RGBA', 'LA', 'P'):
                recon_img = recon_img.convert('RGBA')
            else:
                recon_img = recon_img.convert('RGB')
        
        # Resize if dimensions differ
        if orig_img.size != recon_img.size:
            recon_img = recon_img.resize(orig_img.size, Image.Resampling.LANCZOS)
        
        # Convert to numpy arrays
        orig_arr = np.array(orig_img, dtype=np.float64)
        recon_arr = np.array(recon_img, dtype=np.float64)
        
        # Calculate MSE
        mse = np.mean((orig_arr - recon_arr) ** 2)
        
        # Calculate PSNR
        if mse == 0:
            psnr = float('inf')
        else:
            max_pixel = 255.0
            psnr = 10 * math.log10((max_pixel ** 2) / mse)
        
        # Calculate SSIM
        ssim = calculate_ssim(orig_arr, recon_arr)
        
        return {
            'ssim': ssim,
            'psnr': psnr,
            'mse': mse,
            'original_size': orig_img.size,
            'reconstructed_size': recon_img.size,
            'original_mode': orig_img.mode,
            'reconstructed_mode': recon_img.mode,
            'match': mse == 0
        }
    
    except Exception as e:
        return {
            'error': str(e),
            'ssim': None,
            'psnr': None,
            'mse': None,
            'match': False
        }


# =============================================================================
# PDF COMPARISON
# =============================================================================

def compare_pdf(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed PDF data.
    
    Metrics:
    - Text Preservation: Percentage of text preserved
    - Character Error Rate (CER): Proportion of character errors
    - Visual Similarity (SSIM): Structural similarity of rendered pages
    
    Returns:
        Dictionary with comparison metrics
    """
    result = {
        'text_preservation': None,
        'cer': None,
        'visual_ssim': None,
        'page_count_original': 0,
        'page_count_reconstructed': 0,
        'has_images': False,
        'match': False
    }
    
    try:
        # Extract text from both PDFs
        orig_text, orig_pages, orig_has_images = extract_pdf_text(original)
        recon_text, recon_pages, recon_has_images = extract_pdf_text(reconstructed)
        
        result['page_count_original'] = orig_pages
        result['page_count_reconstructed'] = recon_pages
        result['has_images'] = orig_has_images or recon_has_images
        
        # Calculate text metrics
        if orig_text or recon_text:
            cer = calculate_character_error_rate(orig_text, recon_text)
            text_preservation = (1 - cer) * 100
            result['cer'] = cer
            result['text_preservation'] = text_preservation
        
        # Calculate visual similarity if PDFs have images or graphical content
        if result['has_images'] or orig_pages > 0:
            visual_ssim = compare_pdf_pages_visually(original, reconstructed)
            result['visual_ssim'] = visual_ssim
        
        # Check for exact match
        result['match'] = (original == reconstructed)
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def extract_pdf_text(pdf_data: bytes) -> tuple:
    """
    Extract text content from a PDF.
    
    Returns:
        Tuple of (text_content, page_count, has_images)
    """
    import logging
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    
    try:
        from pypdf import PdfReader
        
        reader = PdfReader(io.BytesIO(pdf_data), strict=False)
        page_count = len(reader.pages)
        
        text_parts = []
        has_images = False
        
        for page in reader.pages:
            # Extract text
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except:
                pass
            
            # Check for images
            try:
                resources = page.get('/Resources')
                if resources and '/XObject' in resources:
                    xobjects = resources['/XObject']
                    for obj in xobjects.values():
                        if hasattr(obj, 'get') and obj.get('/Subtype') == '/Image':
                            has_images = True
                            break
            except:
                pass
        
        full_text = '\n'.join(text_parts)
        return full_text, page_count, has_images
        
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return '', 0, False


def calculate_character_error_rate(original_text: str, reconstructed_text: str) -> float:
    """
    Calculate Character Error Rate (CER) between two texts.
    
    CER = (Substitutions + Insertions + Deletions) / Total Characters in Original
    
    Uses Levenshtein distance for accurate error calculation.
    
    Args:
        original_text: Original text content
        reconstructed_text: Reconstructed text content
    
    Returns:
        CER as a float between 0 and 1 (0 = perfect, 1 = completely different)
    """
    if not original_text and not reconstructed_text:
        return 0.0
    
    if not original_text:
        return 1.0
    
    if not reconstructed_text:
        return 1.0
    
    # Normalize whitespace for fair comparison
    orig_normalized = ' '.join(original_text.split())
    recon_normalized = ' '.join(reconstructed_text.split())
    
    # Calculate Levenshtein distance
    distance = levenshtein_distance(orig_normalized, recon_normalized)
    
    # CER = edit distance / length of original
    cer = distance / len(orig_normalized) if len(orig_normalized) > 0 else 0.0
    
    # Cap at 1.0 (can be higher if reconstructed is much longer)
    return min(cer, 1.0)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.
    
    Uses dynamic programming for efficiency.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def compare_pdf_pages_visually(original: bytes, reconstructed: bytes, 
                                max_pages: int = 5) -> Optional[float]:
    """
    Compare PDF pages visually by rendering them as images.
    
    Args:
        original: Original PDF data
        reconstructed: Reconstructed PDF data
        max_pages: Maximum number of pages to compare
    
    Returns:
        Average SSIM across compared pages, or None if comparison fails
    """
    try:
        # Try using pdf2image (requires poppler)
        from pdf2image import convert_from_bytes
        
        # Convert PDFs to images
        orig_images = convert_from_bytes(original, dpi=72, first_page=1, last_page=max_pages)
        recon_images = convert_from_bytes(reconstructed, dpi=72, first_page=1, last_page=max_pages)
        
        if not orig_images or not recon_images:
            return None
        
        # Compare each page
        ssim_scores = []
        num_pages = min(len(orig_images), len(recon_images))
        
        for i in range(num_pages):
            orig_img = orig_images[i].convert('RGB')
            recon_img = recon_images[i].convert('RGB')
            
            # Resize if needed
            if orig_img.size != recon_img.size:
                recon_img = recon_img.resize(orig_img.size, Image.Resampling.LANCZOS)
            
            # Calculate SSIM
            orig_arr = np.array(orig_img, dtype=np.float64)
            recon_arr = np.array(recon_img, dtype=np.float64)
            
            ssim = calculate_ssim(orig_arr, recon_arr)
            ssim_scores.append(ssim)
        
        # Return average SSIM
        return sum(ssim_scores) / len(ssim_scores) if ssim_scores else None
        
    except ImportError:
        # pdf2image not available, try alternative method
        return compare_pdf_pages_alternative(original, reconstructed, max_pages)
    except Exception as e:
        print(f"Visual PDF comparison error: {e}")
        return None


def compare_pdf_pages_alternative(original: bytes, reconstructed: bytes,
                                   max_pages: int = 5) -> Optional[float]:
    """
    Alternative PDF visual comparison without pdf2image.
    
    Uses pypdf to compare page content streams as a proxy for visual similarity.
    """
    try:
        from pypdf import PdfReader
        import logging
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        
        orig_reader = PdfReader(io.BytesIO(original), strict=False)
        recon_reader = PdfReader(io.BytesIO(reconstructed), strict=False)
        
        num_pages = min(len(orig_reader.pages), len(recon_reader.pages), max_pages)
        
        if num_pages == 0:
            return None
        
        similarity_scores = []
        
        for i in range(num_pages):
            orig_page = orig_reader.pages[i]
            recon_page = recon_reader.pages[i]
            
            # Compare extracted text as proxy
            try:
                orig_text = orig_page.extract_text() or ''
                recon_text = recon_page.extract_text() or ''
                
                if orig_text or recon_text:
                    # Use text similarity as proxy for visual similarity
                    cer = calculate_character_error_rate(orig_text, recon_text)
                    similarity = 1 - cer
                    similarity_scores.append(similarity)
            except:
                pass
        
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else None
        
    except Exception as e:
        print(f"Alternative PDF comparison error: {e}")
        return None


# =============================================================================
# AUDIO COMPARISON
# =============================================================================

def compare_audio(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed audio data.
    
    Metrics:
    - SNR (Signal-to-Noise Ratio): Higher is better, ∞ for identical
    - Correlation: 0-1, 1 is perfect correlation
    - Sample accuracy: Percentage of matching samples (for lossless)
    
    Returns:
        Dictionary with comparison metrics
    """
    result = {
        'snr': None,
        'correlation': None,
        'sample_accuracy': None,
        'duration_original': None,
        'duration_reconstructed': None,
        'sample_rate_match': None,
        'is_lossless': None,
        'match': False
    }
    
    try:
        # Get audio info for both files
        orig_info = get_audio_info_for_comparison(original)
        recon_info = get_audio_info_for_comparison(reconstructed)
        
        result['duration_original'] = orig_info.get('duration')
        result['duration_reconstructed'] = recon_info.get('duration')
        result['sample_rate_match'] = (orig_info.get('sample_rate') == recon_info.get('sample_rate'))
        
        # Extract raw audio samples for comparison
        orig_samples = extract_audio_samples(original)
        recon_samples = extract_audio_samples(reconstructed)
        
        if orig_samples is not None and recon_samples is not None:
            # Ensure same length for comparison
            min_len = min(len(orig_samples), len(recon_samples))
            if min_len > 0:
                orig_samples = orig_samples[:min_len]
                recon_samples = recon_samples[:min_len]
                
                # Calculate SNR
                result['snr'] = calculate_audio_snr(orig_samples, recon_samples)
                
                # Calculate correlation
                result['correlation'] = calculate_audio_correlation(orig_samples, recon_samples)
                
                # Calculate sample accuracy (for lossless comparison)
                matching = np.sum(orig_samples == recon_samples)
                result['sample_accuracy'] = (matching / len(orig_samples)) * 100
                
                # Check if lossless (perfect match)
                result['is_lossless'] = np.array_equal(orig_samples, recon_samples)
                result['match'] = result['is_lossless']
        
        # If raw comparison failed, check byte-level
        if result['snr'] is None:
            result['match'] = (original == reconstructed)
            if result['match']:
                result['sample_accuracy'] = 100.0
                result['is_lossless'] = True
                
    except Exception as e:
        result['error'] = str(e)
    
    return result


def get_audio_info_for_comparison(data: bytes) -> dict:
    """Get basic audio info for comparison purposes."""
    import subprocess
    import tempfile
    import os
    import json
    
    info = {'duration': None, 'sample_rate': None, 'channels': None}
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'audio_file')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams',
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode == 0:
                probe_data = json.loads(result.stdout.decode('utf-8'))
                
                if 'format' in probe_data:
                    info['duration'] = float(probe_data['format'].get('duration', 0))
                
                if 'streams' in probe_data:
                    for stream in probe_data['streams']:
                        if stream.get('codec_type') == 'audio':
                            info['sample_rate'] = int(stream.get('sample_rate', 0))
                            info['channels'] = stream.get('channels', 0)
                            break
        except:
            pass
    
    return info


def extract_audio_samples(data: bytes) -> Optional[np.ndarray]:
    """Extract raw audio samples from audio file."""
    import subprocess
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'audio_file')
        output_path = os.path.join(tmpdir, 'output.raw')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Convert to raw PCM samples
            cmd = [
                'ffmpeg', '-i', input_path,
                '-f', 's16le',  # 16-bit signed little-endian
                '-ac', '1',     # Mono (for simpler comparison)
                '-ar', '44100', # Standard sample rate
                '-y', output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(output_path):
                # Read raw samples
                raw_data = np.fromfile(output_path, dtype=np.int16)
                return raw_data.astype(np.float64)
                
        except Exception as e:
            print(f"Error extracting audio samples: {e}")
    
    return None


def calculate_audio_snr(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """
    Calculate Signal-to-Noise Ratio between original and reconstructed audio.
    
    SNR = 10 * log10(signal_power / noise_power)
    
    Returns:
        SNR in dB, or infinity if signals are identical
    """
    # Calculate signal power
    signal_power = np.mean(original ** 2)
    
    # Calculate noise (difference) power
    noise = original - reconstructed
    noise_power = np.mean(noise ** 2)
    
    if noise_power == 0:
        return float('inf')  # Perfect match
    
    if signal_power == 0:
        return 0.0
    
    snr = 10 * np.log10(signal_power / noise_power)
    return float(snr)


def calculate_audio_correlation(original: np.ndarray, reconstructed: np.ndarray) -> float:
    """
    Calculate Pearson correlation coefficient between audio signals.
    
    Returns:
        Correlation coefficient between -1 and 1, where 1 is perfect positive correlation
    """
    if len(original) == 0 or len(reconstructed) == 0:
        return 0.0
    
    # Normalize signals
    orig_mean = np.mean(original)
    recon_mean = np.mean(reconstructed)
    
    orig_centered = original - orig_mean
    recon_centered = reconstructed - recon_mean
    
    # Calculate correlation
    numerator = np.sum(orig_centered * recon_centered)
    denominator = np.sqrt(np.sum(orig_centered ** 2) * np.sum(recon_centered ** 2))
    
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
    
    return float(numerator / denominator)


def calculate_ssim(img1: np.ndarray, img2: np.ndarray, 
                   k1: float = 0.01, k2: float = 0.03) -> float:
    """
    Calculate Structural Similarity Index (SSIM).
    
    Simplified implementation for grayscale or averaged color.
    """
    # Convert to grayscale if color
    if len(img1.shape) == 3:
        img1 = np.mean(img1, axis=2)
    if len(img2.shape) == 3:
        img2 = np.mean(img2, axis=2)
    
    # Constants
    L = 255  # Dynamic range
    c1 = (k1 * L) ** 2
    c2 = (k2 * L) ** 2
    
    # Calculate means
    mu1 = np.mean(img1)
    mu2 = np.mean(img2)
    
    # Calculate variances and covariance
    sigma1_sq = np.var(img1)
    sigma2_sq = np.var(img2)
    sigma12 = np.mean((img1 - mu1) * (img2 - mu2))
    
    # Calculate SSIM
    numerator = (2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)
    denominator = (mu1 ** 2 + mu2 ** 2 + c1) * (sigma1_sq + sigma2_sq + c2)
    
    ssim = numerator / denominator
    
    return float(ssim)


# =============================================================================
# VIDEO COMPARISON
# =============================================================================

def compare_video(original: bytes, reconstructed: bytes) -> dict:
    """
    Compare original and reconstructed video data.
    
    Metrics:
    - PSNR (Peak Signal-to-Noise Ratio): Higher is better, ∞ for identical
    - SSIM (Structural Similarity): 0-1, 1 is perfect
    - Duration difference
    - Frame rate difference
    
    Returns:
        Dictionary with comparison metrics
    """
    import subprocess
    import tempfile
    import os
    import json
    
    result = {
        'psnr': None,
        'ssim': None,
        'duration_original': None,
        'duration_reconstructed': None,
        'resolution_original': None,
        'resolution_reconstructed': None,
        'fps_original': None,
        'fps_reconstructed': None,
        'frame_count_original': None,
        'frame_count_reconstructed': None,
        'is_lossless': False,
        'match': False
    }
    
    # Check for exact match first
    result['match'] = (original == reconstructed)
    if result['match']:
        result['is_lossless'] = True
        result['psnr'] = float('inf')
        result['ssim'] = 1.0
    
    with tempfile.TemporaryDirectory() as tmpdir:
        orig_path = os.path.join(tmpdir, 'original.mp4')
        recon_path = os.path.join(tmpdir, 'reconstructed.mp4')
        
        with open(orig_path, 'wb') as f:
            f.write(original)
        with open(recon_path, 'wb') as f:
            f.write(reconstructed)
        
        try:
            # Get video info for both files
            orig_info = get_video_probe_info(orig_path)
            recon_info = get_video_probe_info(recon_path)
            
            result['duration_original'] = orig_info.get('duration')
            result['duration_reconstructed'] = recon_info.get('duration')
            result['resolution_original'] = f"{orig_info.get('width', '?')}x{orig_info.get('height', '?')}"
            result['resolution_reconstructed'] = f"{recon_info.get('width', '?')}x{recon_info.get('height', '?')}"
            result['fps_original'] = orig_info.get('fps')
            result['fps_reconstructed'] = recon_info.get('fps')
            result['frame_count_original'] = orig_info.get('frame_count')
            result['frame_count_reconstructed'] = recon_info.get('frame_count')
            
            # Skip quality metrics if already matched
            if result['match']:
                return result
            
            # Calculate PSNR and SSIM using ffmpeg
            # Use lavfi filter to compare videos frame by frame
            psnr_log = os.path.join(tmpdir, 'psnr.log')
            ssim_log = os.path.join(tmpdir, 'ssim.log')
            
            # PSNR comparison
            cmd_psnr = [
                'ffmpeg',
                '-i', recon_path,
                '-i', orig_path,
                '-lavfi', f'psnr=stats_file={psnr_log}',
                '-f', 'null', '-'
            ]
            
            psnr_result = subprocess.run(
                cmd_psnr,
                capture_output=True,
                timeout=300
            )
            
            # Parse PSNR from stderr (ffmpeg outputs stats there)
            psnr_output = psnr_result.stderr.decode('utf-8', errors='ignore')
            if 'average:' in psnr_output:
                # Find the PSNR average line
                for line in psnr_output.split('\n'):
                    if 'average:' in line.lower():
                        parts = line.split('average:')
                        if len(parts) > 1:
                            psnr_str = parts[1].split()[0]
                            try:
                                result['psnr'] = float(psnr_str) if psnr_str != 'inf' else float('inf')
                            except:
                                pass
            
            # SSIM comparison
            cmd_ssim = [
                'ffmpeg',
                '-i', recon_path,
                '-i', orig_path,
                '-lavfi', f'ssim=stats_file={ssim_log}',
                '-f', 'null', '-'
            ]
            
            ssim_result = subprocess.run(
                cmd_ssim,
                capture_output=True,
                timeout=300
            )
            
            # Parse SSIM from stderr
            ssim_output = ssim_result.stderr.decode('utf-8', errors='ignore')
            if 'All:' in ssim_output:
                for line in ssim_output.split('\n'):
                    if 'All:' in line:
                        parts = line.split('All:')
                        if len(parts) > 1:
                            ssim_str = parts[1].split()[0]
                            try:
                                result['ssim'] = float(ssim_str)
                            except:
                                pass
            
            # Determine if effectively lossless
            if result['psnr'] and result['psnr'] > 50:
                result['is_lossless'] = True
            elif result['ssim'] and result['ssim'] > 0.99:
                result['is_lossless'] = True
                
        except subprocess.TimeoutExpired:
            result['error'] = 'Video comparison timed out'
        except Exception as e:
            result['error'] = str(e)
    
    return result


def get_video_probe_info(video_path: str) -> dict:
    """
    Get video file information using ffprobe.
    
    Args:
        video_path: Path to video file
    
    Returns:
        Dictionary with video info
    """
    import subprocess
    import json
    
    info = {
        'duration': None,
        'width': None,
        'height': None,
        'fps': None,
        'frame_count': None
    }
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            '-count_frames',
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=60
        )
        
        if result.returncode == 0:
            probe_data = json.loads(result.stdout.decode('utf-8'))
            
            # Format info
            fmt = probe_data.get('format', {})
            info['duration'] = float(fmt.get('duration', 0)) if fmt.get('duration') else None
            
            # Stream info
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info['width'] = stream.get('width')
                    info['height'] = stream.get('height')
                    info['frame_count'] = int(stream.get('nb_read_frames', 0)) if stream.get('nb_read_frames') else None
                    
                    # Parse frame rate
                    fps_str = stream.get('r_frame_rate', '0/1')
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        if int(den) > 0:
                            info['fps'] = round(int(num) / int(den), 2)
                    break
                    
    except Exception as e:
        print(f"Error probing video: {e}")
    
    return info


def compare_data(original: bytes, reconstructed: bytes, 
                 filename: str = '') -> dict:
    """
    Compare original and reconstructed data, auto-detecting type.
    
    Args:
        original: Original file data
        reconstructed: Reconstructed file data
        filename: Optional filename for type detection
    
    Returns:
        Dictionary with comparison metrics
    """
    data_type = detect_comparison_type(filename, original)
    
    result = {
        'data_type': data_type
    }
    
    if data_type == 'text':
        result.update(compare_text(original, reconstructed))
    elif data_type == 'image':
        result.update(compare_image(original, reconstructed))
    elif data_type == 'pdf':
        result.update(compare_pdf(original, reconstructed))
    elif data_type == 'audio':
        result.update(compare_audio(original, reconstructed))
    elif data_type == 'video':
        result.update(compare_video(original, reconstructed))
    else:
        result.update(compare_binary(original, reconstructed))
    
    return result


def format_comparison_results(results: dict) -> str:
    """Format comparison results for display."""
    lines = []
    data_type = results.get('data_type', 'unknown')
    
    lines.append(f"📊 **Comparison Results ({data_type.upper()} Data)**")
    lines.append("")
    
    if data_type == 'text':
        lines.append(f"✅ **Accuracy:** {results.get('accuracy', 0):.4f}%")
        lines.append(f"📉 **Bit Error Rate:** {results.get('bit_error_rate', 0):.6e}")
        lines.append(f"📝 **Character Matches:** {results.get('character_matches', 0)} / {results.get('total_characters', 0)}")
        lines.append(f"📏 **Original Length:** {results.get('original_length', 0)} characters")
        lines.append(f"📏 **Reconstructed Length:** {results.get('reconstructed_length', 0)} characters")
        
    elif data_type == 'image':
        if results.get('error'):
            lines.append(f"❌ **Error:** {results['error']}")
        else:
            ssim = results.get('ssim')
            psnr = results.get('psnr')
            mse = results.get('mse')
            
            if ssim is not None:
                ssim_rating = "Excellent" if ssim > 0.98 else "Very Good" if ssim > 0.95 else "Good" if ssim > 0.90 else "Fair"
                lines.append(f"🎯 **SSIM:** {ssim:.4f} ({ssim_rating})")
            if psnr is not None:
                if psnr == float('inf'):
                    lines.append(f"📊 **PSNR:** ∞ dB (perfect match)")
                else:
                    lines.append(f"📊 **PSNR:** {psnr:.2f} dB")
            if mse is not None:
                lines.append(f"📉 **MSE:** {mse:.6f}")
            
            lines.append(f"📐 **Original Size:** {results.get('original_size', 'N/A')}")
            lines.append(f"📐 **Reconstructed Size:** {results.get('reconstructed_size', 'N/A')}")
    
    elif data_type == 'pdf':
        if results.get('error'):
            lines.append(f"❌ **Error:** {results['error']}")
        else:
            # Page info
            orig_pages = results.get('page_count_original', 0)
            recon_pages = results.get('page_count_reconstructed', 0)
            lines.append(f"📄 **Pages:** {orig_pages} original → {recon_pages} reconstructed")
            lines.append("")
            
            # Text Preservation metrics
            text_pres = results.get('text_preservation')
            cer = results.get('cer')
            
            if text_pres is not None and cer is not None:
                cer_percent = cer * 100
                # Format exactly as requested: "Text Preservation: 99.8% (Character Error Rate (CER): 0.2%)"
                lines.append(f"📝 **Text Preservation: {text_pres:.1f}%** (Character Error Rate (CER): {cer_percent:.1f}%)")
                if cer_percent < 1:
                    lines.append(f"   └─ ✅ Excellent - CER < 1% indicates excellent text fidelity")
                elif cer_percent < 5:
                    lines.append(f"   └─ ⚠️ Good - Minor text differences detected")
                else:
                    lines.append(f"   └─ ⚠️ Fair - Noticeable text differences")
            else:
                lines.append("📝 **Text Preservation:** N/A (no text content)")
            
            lines.append("")
            
            # Visual Similarity metrics (only if page contains images/charts)
            visual_ssim = results.get('visual_ssim')
            has_images = results.get('has_images', False)
            
            if has_images:
                if visual_ssim is not None:
                    # Format exactly as requested: "Visual Similarity (SSIM): 0.92"
                    lines.append(f"🖼️ **Visual Similarity (SSIM): {visual_ssim:.2f}**")
                    if visual_ssim > 0.98:
                        lines.append(f"   └─ ✅ Excellent (>0.98)")
                    elif visual_ssim > 0.95:
                        lines.append(f"   └─ ✅ Very Good (>0.95)")
                    elif visual_ssim > 0.90:
                        lines.append(f"   └─ ⚠️ Good (>0.90)")
                    else:
                        lines.append(f"   └─ ⚠️ Fair - Noticeable visual differences")
                else:
                    lines.append("🖼️ **Visual Similarity:** Could not compute (missing dependencies)")
            else:
                lines.append("🖼️ **Visual Similarity:** N/A (page contains no images/charts)")
    
    elif data_type == 'audio':
        if results.get('error'):
            lines.append(f"❌ **Error:** {results['error']}")
        else:
            # Duration info
            dur_orig = results.get('duration_original')
            dur_recon = results.get('duration_reconstructed')
            if dur_orig and dur_recon:
                orig_mins, orig_secs = int(dur_orig // 60), int(dur_orig % 60)
                recon_mins, recon_secs = int(dur_recon // 60), int(dur_recon % 60)
                lines.append(f"⏱️ **Duration:** {orig_mins}:{orig_secs:02d} original → {recon_mins}:{recon_secs:02d} reconstructed")
            lines.append("")
            
            # Check if lossless
            is_lossless = results.get('is_lossless', False)
            if is_lossless:
                lines.append("🎼 **Compression Type: LOSSLESS**")
                lines.append("   └─ ✅ Perfect reconstruction - All audio data preserved")
            else:
                lines.append("🎧 **Compression Type: LOSSY**")
            lines.append("")
            
            # SNR
            snr = results.get('snr')
            if snr is not None:
                if snr == float('inf'):
                    lines.append(f"📊 **Signal-to-Noise Ratio (SNR): ∞ dB** (identical)")
                    lines.append("   └─ ✅ Perfect - No noise introduced")
                else:
                    snr_rating = "Excellent" if snr > 60 else "Very Good" if snr > 40 else "Good" if snr > 20 else "Fair"
                    lines.append(f"📊 **Signal-to-Noise Ratio (SNR): {snr:.1f} dB**")
                    lines.append(f"   └─ {snr_rating} - {'Imperceptible difference' if snr > 40 else 'Minor audible differences' if snr > 20 else 'Noticeable differences'}")
            
            lines.append("")
            
            # Correlation
            corr = results.get('correlation')
            if corr is not None:
                corr_rating = "Excellent" if corr > 0.99 else "Very Good" if corr > 0.95 else "Good" if corr > 0.90 else "Fair"
                lines.append(f"🎯 **Waveform Correlation: {corr:.4f}**")
                lines.append(f"   └─ {corr_rating} - {'>0.99 is excellent, >0.95 is very good' if corr > 0.95 else 'Some waveform differences'}")
    
    elif data_type == 'video':
        if results.get('error'):
            lines.append(f"❌ **Error:** {results['error']}")
        else:
            # Duration info
            dur_orig = results.get('duration_original')
            dur_recon = results.get('duration_reconstructed')
            if dur_orig and dur_recon:
                orig_mins, orig_secs = int(dur_orig // 60), int(dur_orig % 60)
                recon_mins, recon_secs = int(dur_recon // 60), int(dur_recon % 60)
                lines.append(f"⏱️ **Duration:** {orig_mins}:{orig_secs:02d} original → {recon_mins}:{recon_secs:02d} reconstructed")
            
            # Resolution info
            res_orig = results.get('resolution_original', '?x?')
            res_recon = results.get('resolution_reconstructed', '?x?')
            lines.append(f"📐 **Resolution:** {res_orig} original → {res_recon} reconstructed")
            
            # FPS info
            fps_orig = results.get('fps_original')
            fps_recon = results.get('fps_reconstructed')
            if fps_orig and fps_recon:
                lines.append(f"🎬 **Frame Rate:** {fps_orig} fps original → {fps_recon} fps reconstructed")
            
            lines.append("")
            
            # Check if lossless
            is_lossless = results.get('is_lossless', False)
            if is_lossless:
                lines.append("🎥 **Compression Type: VISUALLY LOSSLESS**")
                lines.append("   └─ ✅ Excellent quality - No visible differences")
            else:
                lines.append("📹 **Compression Type: LOSSY**")
            lines.append("")
            
            # PSNR
            psnr = results.get('psnr')
            if psnr is not None:
                if psnr == float('inf'):
                    lines.append(f"📊 **PSNR: ∞ dB** (identical)")
                    lines.append("   └─ ✅ Perfect - No quality loss")
                else:
                    psnr_rating = "Excellent" if psnr > 40 else "Very Good" if psnr > 35 else "Good" if psnr > 30 else "Fair"
                    lines.append(f"📊 **PSNR: {psnr:.1f} dB**")
                    lines.append(f"   └─ {psnr_rating} - {'Imperceptible difference' if psnr > 40 else 'Minor visual differences' if psnr > 30 else 'Noticeable differences'}")
            
            # SSIM
            ssim = results.get('ssim')
            if ssim is not None:
                ssim_rating = "Excellent" if ssim > 0.98 else "Very Good" if ssim > 0.95 else "Good" if ssim > 0.90 else "Fair"
                lines.append(f"🎯 **SSIM: {ssim:.4f}**")
                lines.append(f"   └─ {ssim_rating}")
    
    else:  # binary
        lines.append(f"✅ **Accuracy:** {results.get('accuracy', 0):.4f}%")
        lines.append(f"📉 **Bit Error Rate:** {results.get('bit_error_rate', 0):.6e}")
        lines.append(f"📦 **Byte Matches:** {results.get('byte_matches', 0)} / {results.get('total_bytes', 0)}")
    
    lines.append("")
    if results.get('match', False):
        lines.append("✅ **Perfect Match!** The data is identical.")
    else:
        if data_type == 'pdf':
            # For PDF, check if it's effectively equivalent
            text_pres = results.get('text_preservation', 0)
            visual_ssim = results.get('visual_ssim', 0)
            if text_pres and text_pres > 99 and (visual_ssim is None or visual_ssim > 0.98):
                lines.append("✅ **Effectively Identical** - Text and visual content preserved.")
            else:
                lines.append("⚠️ **Data differs** - Some content changed due to compression.")
        elif data_type == 'audio':
            # For audio, check if quality is preserved
            snr = results.get('snr', 0) or 0
            corr = results.get('correlation', 0) or 0
            if snr > 40 and corr > 0.99:
                lines.append("✅ **Effectively Identical** - Audio quality preserved (imperceptible differences).")
            elif snr > 20 and corr > 0.95:
                lines.append("✅ **Good Quality** - Minor lossy compression artifacts.")
            else:
                lines.append("⚠️ **Data differs** - Audible differences due to compression.")
        elif data_type == 'video':
            # For video, check if quality is preserved
            psnr = results.get('psnr', 0) or 0
            ssim = results.get('ssim', 0) or 0
            if psnr > 40 and ssim > 0.98:
                lines.append("✅ **Effectively Identical** - Video quality preserved (imperceptible differences).")
            elif psnr > 30 and ssim > 0.95:
                lines.append("✅ **Good Quality** - Minor visual compression artifacts.")
            else:
                lines.append("⚠️ **Data differs** - Visible differences due to compression.")
        else:
            lines.append("⚠️ **Data differs** from the original.")
    
    return "\n".join(lines)
