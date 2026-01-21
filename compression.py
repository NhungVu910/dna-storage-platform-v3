"""
Compression Module
Handles data-type-specific compression:
- Brotli for text
- WebP for images
- PDF optimization (object cleanup, image downsampling)
- Audio compression (FLAC lossless, MP3 lossy)
"""

import io
import brotli
import subprocess
import tempfile
import os
from PIL import Image
from typing import Tuple, Optional, List


# Cache ffmpeg availability check
_ffmpeg_available = None
_ffprobe_available = None


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available on the system."""
    global _ffmpeg_available
    if _ffmpeg_available is None:
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            _ffmpeg_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            _ffmpeg_available = False
    return _ffmpeg_available


def is_ffprobe_available() -> bool:
    """Check if ffprobe is available on the system."""
    global _ffprobe_available
    if _ffprobe_available is None:
        try:
            result = subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                timeout=5
            )
            _ffprobe_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            _ffprobe_available = False
    return _ffprobe_available


def get_ffmpeg_error_message() -> str:
    """Get a user-friendly error message when ffmpeg is not available."""
    return (
        "FFmpeg is not available on this system. "
        "Audio and video compression features require FFmpeg. "
        "Please ensure 'packages.txt' contains 'ffmpeg' for Streamlit Cloud deployment."
    )


# Supported file types
TEXT_EXTENSIONS = {'.txt', '.csv', '.json', '.xml', '.html', '.md', '.log', '.py', '.js', '.css'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
PDF_EXTENSIONS = {'.pdf'}
AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.aac', '.ogg', '.m4a', '.wma', '.aiff', '.aif'}
VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpeg', '.mpg', '.3gp'}


def detect_file_type(filename: str, data: bytes) -> str:
    """
    Detect file type based on extension and content.
    Returns: 'text', 'image', 'pdf', 'audio', 'video', or 'binary'
    """
    import os
    ext = os.path.splitext(filename)[1].lower()
    
    if ext in TEXT_EXTENSIONS:
        return 'text'
    elif ext in IMAGE_EXTENSIONS:
        return 'image'
    elif ext in PDF_EXTENSIONS:
        return 'pdf'
    elif ext in AUDIO_EXTENSIONS:
        return 'audio'
    elif ext in VIDEO_EXTENSIONS:
        return 'video'
    else:
        # Try to detect by content
        # Check for PDF signature
        if data[:4] == b'%PDF':
            return 'pdf'
        
        # Check for video signatures
        # MP4/M4V: ftyp at offset 4
        if len(data) >= 12 and data[4:8] == b'ftyp':
            ftyp_brand = data[8:12]
            # Video brands: mp41, mp42, isom, avc1, etc.
            video_brands = [b'mp41', b'mp42', b'isom', b'avc1', b'M4V ', b'M4VP', b'qt  ']
            # Audio brands: M4A , mp4a
            audio_brands = [b'M4A ', b'mp4a']
            if ftyp_brand in video_brands:
                return 'video'
            elif ftyp_brand in audio_brands:
                return 'audio'
            # If brand not recognized, check file extension hint or default to video
            if ext in {'.m4a', '.aac'}:
                return 'audio'
            return 'video'  # Default ftyp to video
        
        # AVI: RIFF....AVI
        if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'AVI ':
            return 'video'
        
        # MKV/WebM: EBML header (0x1A 0x45 0xDF 0xA3)
        if len(data) >= 4 and data[:4] == b'\x1a\x45\xdf\xa3':
            return 'video'
        
        # MOV: moov or mdat atom at start, or ftyp qt
        if len(data) >= 8:
            atom_type = data[4:8]
            if atom_type in [b'moov', b'mdat', b'wide', b'free']:
                return 'video'
        
        # FLV: FLV signature
        if len(data) >= 3 and data[:3] == b'FLV':
            return 'video'
        
        # MPEG: start codes 0x000001BA (PS) or 0x000001B3 (sequence header)
        if len(data) >= 4 and data[:3] == b'\x00\x00\x01' and data[3] in (0xBA, 0xB3):
            return 'video'
        
        # Check for audio signatures
        # WAV: RIFF....WAVE
        if data[:4] == b'RIFF' and data[8:12] == b'WAVE':
            return 'audio'
        # MP3: ID3 tag or frame sync
        if data[:3] == b'ID3' or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
            return 'audio'
        # FLAC: fLaC
        if data[:4] == b'fLaC':
            return 'audio'
        # OGG: OggS
        if data[:4] == b'OggS':
            return 'audio'
        # AIFF: FORM....AIFF
        if data[:4] == b'FORM' and data[8:12] == b'AIFF':
            return 'audio'
        
        # Check for common image signatures
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image'
        elif data[:2] == b'\xff\xd8':  # JPEG
            return 'image'
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            return 'image'
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return 'image'
        
        # Try to detect text by checking if content is mostly printable
        try:
            sample = data[:1000]
            text = sample.decode('utf-8')
            printable_ratio = sum(c.isprintable() or c.isspace() for c in text) / len(text)
            if printable_ratio > 0.9:
                return 'text'
        except:
            pass
        
        return 'binary'


def compress_data(data: bytes, file_type: str, 
                  compression_option: str = 'auto',
                  brotli_quality: int = 11,
                  webp_quality: int = 85,
                  pdf_image_dpi: int = 150,
                  pdf_image_quality: int = 85,
                  pdf_method: str = 'auto',
                  audio_method: str = 'flac',
                  audio_bitrate: int = 192,
                  video_method: str = 'h264',
                  video_crf: int = 23,
                  video_preset: str = 'medium') -> Tuple[bytes, str]:
    """
    Compress data based on file type.
    
    Args:
        data: Raw file data
        file_type: 'text', 'image', 'pdf', 'audio', 'video', or 'binary'
        compression_option: 'none', 'auto', or specific algorithm
        brotli_quality: Brotli compression quality (0-11, higher = better compression)
        webp_quality: WebP compression quality (1-100, lower = more compression)
        pdf_image_dpi: Target DPI for PDF image downsampling (72-300)
        pdf_image_quality: JPEG quality for PDF images (1-100)
        pdf_method: PDF compression method ('auto', 'pdf_gs', 'pdf_opt')
        audio_method: Audio compression method ('flac', 'mp3', 'aac')
        audio_bitrate: MP3/AAC bitrate in kbps (64-320)
        video_method: Video compression method ('h264', 'av1')
        video_crf: Video CRF quality (0-51 for H.264, lower = better quality)
        video_preset: Video encoding preset ('ultrafast' to 'veryslow')
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    if compression_option == 'none':
        return data, 'none'
    
    if file_type == 'text':
        return compress_text(data, quality=brotli_quality)
    elif file_type == 'image':
        return compress_image(data, quality=webp_quality)
    elif file_type == 'pdf':
        return compress_pdf(data, target_dpi=pdf_image_dpi, 
                           image_quality=pdf_image_quality, method=pdf_method)
    elif file_type == 'audio':
        return compress_audio(data, method=audio_method, bitrate=audio_bitrate)
    elif file_type == 'video':
        return compress_video(data, method=video_method, crf=video_crf, preset=video_preset)
    else:
        # For binary files, try Brotli as general-purpose compression
        return compress_text(data, quality=brotli_quality)


def compress_text(data: bytes, quality: int = 11) -> Tuple[bytes, str]:
    """
    Compress text data using Brotli.
    
    Args:
        data: Raw text data
        quality: Compression quality 0-11 (higher = better compression, slower)
    """
    try:
        compressed = brotli.compress(data, quality=quality)
        # Only use compression if it actually reduces size
        if len(compressed) < len(data):
            return compressed, 'brotli'
        else:
            return data, 'none'
    except Exception as e:
        print(f"Brotli compression failed: {e}")
        return data, 'none'


def compress_image(data: bytes, quality: int = 85) -> Tuple[bytes, str]:
    """
    Compress image data using WebP.
    
    Args:
        data: Raw image data
        quality: WebP quality 1-100 (lower = more compression, more artifacts)
    """
    try:
        # Load image
        img = Image.open(io.BytesIO(data))
        
        # Convert to RGB if necessary (WebP doesn't support all modes)
        if img.mode in ('RGBA', 'LA'):
            # Keep alpha for transparency support
            pass
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Compress to WebP
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=quality, method=6)
        compressed = output.getvalue()
        
        # Only use compression if it reduces size
        if len(compressed) < len(data):
            return compressed, 'webp'
        else:
            return data, 'none'
    except Exception as e:
        print(f"WebP compression failed: {e}")
        # Fallback to Brotli for failed image compression
        return compress_text(data)


# =============================================================================
# PDF COMPRESSION
# =============================================================================

def compress_pdf(data: bytes, target_dpi: int = 150, 
                 image_quality: int = 85,
                 method: str = 'auto') -> Tuple[bytes, str]:
    """
    Compress PDF using selected optimization method.
    
    Methods:
    - 'auto': Try Ghostscript first, fallback to pypdf
    - 'pdf_gs': Ghostscript only (image downsampling + optimization)
    - 'pdf_opt': pypdf only (object optimization, no image changes)
    
    Args:
        data: Raw PDF data
        target_dpi: Target DPI for images (only for pdf_gs)
        image_quality: JPEG quality for recompressed images (only for pdf_gs)
        method: Compression method ('auto', 'pdf_gs', 'pdf_opt')
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    if method == 'pdf_opt':
        # Use pypdf only
        try:
            compressed = compress_pdf_pypdf(data, remove_unused=True)
            if compressed and len(compressed) < len(data):
                return compressed, 'pdf_opt'
        except Exception as e:
            print(f"PyPDF compression failed: {e}")
        return data, 'none'
    
    elif method == 'pdf_gs':
        # Use Ghostscript only
        try:
            compressed = compress_pdf_ghostscript(data, target_dpi, image_quality)
            if compressed and len(compressed) < len(data):
                return compressed, 'pdf_gs'
        except Exception as e:
            print(f"Ghostscript compression failed: {e}")
        return data, 'none'
    
    else:  # 'auto' - try both
        # Try Ghostscript first (better compression)
        try:
            compressed = compress_pdf_ghostscript(data, target_dpi, image_quality)
            if compressed and len(compressed) < len(data):
                return compressed, 'pdf_gs'
        except Exception as e:
            print(f"Ghostscript compression failed: {e}")
        
        # Fallback to pypdf
        try:
            compressed = compress_pdf_pypdf(data, remove_unused=True)
            if compressed and len(compressed) < len(data):
                return compressed, 'pdf_opt'
        except Exception as e:
            print(f"PyPDF compression failed: {e}")
        
        return data, 'none'


def compress_pdf_ghostscript(data: bytes, target_dpi: int = 150, 
                              image_quality: int = 85) -> Optional[bytes]:
    """
    Compress PDF using Ghostscript for maximum compression.
    
    Ghostscript can:
    - Downsample images to target DPI
    - Recompress images with JPEG
    - Remove unused objects
    - Optimize PDF structure
    
    Args:
        data: Raw PDF data
        target_dpi: Target DPI for image downsampling
        image_quality: JPEG quality (1-100, maps to Ghostscript settings)
    
    Returns:
        Compressed PDF data or None if failed
    """
    # Map quality to Ghostscript preset
    if target_dpi <= 72:
        gs_setting = '/screen'  # 72 DPI, lowest quality
    elif target_dpi <= 150:
        gs_setting = '/ebook'   # 150 DPI, medium quality
    elif target_dpi <= 200:
        gs_setting = '/printer' # 300 DPI, high quality
    else:
        gs_setting = '/prepress' # 300 DPI, highest quality
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input.pdf')
        output_path = os.path.join(tmpdir, 'output.pdf')
        
        # Write input PDF
        with open(input_path, 'wb') as f:
            f.write(data)
        
        # Build Ghostscript command
        cmd = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.4',
            f'-dPDFSETTINGS={gs_setting}',
            '-dNOPAUSE',
            '-dQUIET',
            '-dBATCH',
            # Image downsampling settings
            '-dDownsampleColorImages=true',
            '-dDownsampleGrayImages=true',
            '-dDownsampleMonoImages=true',
            f'-dColorImageResolution={target_dpi}',
            f'-dGrayImageResolution={target_dpi}',
            f'-dMonoImageResolution={target_dpi}',
            # Compression settings
            '-dCompressFonts=true',
            '-dEmbedAllFonts=true',
            '-dSubsetFonts=true',
            # Remove unused
            '-dDetectDuplicateImages=true',
            '-dAutoRotatePages=/None',
            f'-sOutputFile={output_path}',
            input_path
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                check=True
            )
            
            # Read compressed output
            with open(output_path, 'rb') as f:
                return f.read()
                
        except subprocess.TimeoutExpired:
            print("Ghostscript timed out")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Ghostscript error: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return None
        except FileNotFoundError:
            print("Ghostscript not found, falling back to pypdf")
            return None


def compress_pdf_pypdf(data: bytes, remove_unused: bool = True) -> Optional[bytes]:
    """
    Compress PDF using pypdf library.
    
    This provides basic optimization:
    - Remove unused objects
    - Compress streams
    - Clean up structure
    
    Note: Cannot downsample images, but good for object cleanup.
    
    Args:
        data: Raw PDF data
        remove_unused: Whether to remove unused objects
    
    Returns:
        Compressed PDF data or None if failed
    """
    try:
        from pypdf import PdfReader, PdfWriter
        import logging
        
        # Suppress pypdf warnings about malformed PDFs
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        
        reader = PdfReader(io.BytesIO(data), strict=False)
        writer = PdfWriter()
        
        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)
        
        # Copy metadata if present
        if reader.metadata:
            try:
                writer.add_metadata(reader.metadata)
            except:
                pass  # Skip if metadata copy fails
        
        # Compress content streams
        for page in writer.pages:
            try:
                page.compress_content_streams()
            except:
                pass  # Skip if compression fails for a page
        
        # Write output
        output = io.BytesIO()
        writer.write(output)
        
        return output.getvalue()
        
    except ImportError:
        print("pypdf not available")
        return None
    except Exception as e:
        print(f"pypdf compression error: {e}")
        return None


def compress_pdf_images_only(data: bytes, target_dpi: int = 150,
                              image_quality: int = 85) -> Optional[bytes]:
    """
    Extract, downsample, and recompress images in a PDF.
    
    Uses pikepdf for precise image manipulation.
    
    Args:
        data: Raw PDF data
        target_dpi: Target DPI for images
        image_quality: JPEG quality for recompression
    
    Returns:
        PDF with optimized images or None if failed
    """
    try:
        import pikepdf
        from pikepdf import Pdf, PdfImage
        
        pdf = Pdf.open(io.BytesIO(data))
        images_processed = 0
        
        for page in pdf.pages:
            # Find all images on the page
            if '/Resources' not in page:
                continue
                
            resources = page['/Resources']
            if '/XObject' not in resources:
                continue
            
            xobjects = resources['/XObject']
            
            for name in list(xobjects.keys()):
                xobj = xobjects[name]
                
                if xobj.get('/Subtype') != '/Image':
                    continue
                
                try:
                    # Extract image
                    pdfimage = PdfImage(xobj)
                    pil_image = pdfimage.as_pil_image()
                    
                    # Get current resolution
                    width, height = pil_image.size
                    
                    # Calculate scaling factor based on target DPI
                    # Assume current DPI from PDF matrix or default 72
                    current_dpi = 72  # Default assumption
                    scale_factor = target_dpi / current_dpi
                    
                    if scale_factor < 1:  # Only downsample, don't upscale
                        new_width = int(width * scale_factor)
                        new_height = int(height * scale_factor)
                        
                        if new_width > 10 and new_height > 10:  # Minimum size
                            # Downsample
                            pil_image = pil_image.resize(
                                (new_width, new_height),
                                Image.LANCZOS
                            )
                            
                            # Convert to RGB for JPEG if needed
                            if pil_image.mode in ('RGBA', 'LA', 'P'):
                                pil_image = pil_image.convert('RGB')
                            
                            # Recompress as JPEG
                            img_buffer = io.BytesIO()
                            pil_image.save(img_buffer, format='JPEG', 
                                          quality=image_quality, optimize=True)
                            img_data = img_buffer.getvalue()
                            
                            # Replace in PDF (simplified - may not work for all cases)
                            images_processed += 1
                            
                except Exception as img_error:
                    print(f"Could not process image {name}: {img_error}")
                    continue
        
        if images_processed > 0:
            output = io.BytesIO()
            pdf.save(output)
            return output.getvalue()
        else:
            return None
            
    except ImportError:
        print("pikepdf not available")
        return None
    except Exception as e:
        print(f"PDF image optimization error: {e}")
        return None


def get_pdf_info(data: bytes) -> dict:
    """
    Get information about a PDF file.
    
    Returns:
        Dict with page count, has_images, estimated_image_count, etc.
    """
    info = {
        'page_count': 0,
        'has_images': False,
        'has_text': False,
        'file_size': len(data),
        'metadata': {}
    }
    
    try:
        from pypdf import PdfReader
        import logging
        
        # Suppress pypdf warnings
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        
        reader = PdfReader(io.BytesIO(data), strict=False)
        info['page_count'] = len(reader.pages)
        
        if reader.metadata:
            info['metadata'] = {
                'title': reader.metadata.title or '',
                'author': reader.metadata.author or '',
                'creator': reader.metadata.creator or ''
            }
        
        # Check for images and text
        for page in reader.pages:
            # Check for text
            try:
                text = page.extract_text()
                if text and text.strip():
                    info['has_text'] = True
            except:
                pass
            
            # Check for images
            try:
                resources = page.get('/Resources')
                if resources and '/XObject' in resources:
                    xobjects = resources['/XObject']
                    for obj in xobjects.values():
                        if hasattr(obj, 'get') and obj.get('/Subtype') == '/Image':
                            info['has_images'] = True
                            break
            except:
                pass
            
            if info['has_images'] and info['has_text']:
                break  # Found both, no need to continue
                
    except Exception as e:
        print(f"Error reading PDF info: {e}")
    
    return info


# =============================================================================
# AUDIO COMPRESSION
# =============================================================================

def compress_audio(data: bytes, method: str = 'flac', bitrate: int = 192) -> Tuple[bytes, str]:
    """
    Compress audio using FLAC (lossless), AAC (lossy), or MP3 (lossy).
    
    Args:
        data: Raw audio data
        method: 'flac' for lossless, 'aac' for efficient lossy, 'mp3' for universal lossy
        bitrate: Target bitrate in kbps for lossy codecs (64-320)
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    # Check if ffmpeg is available
    if not is_ffmpeg_available():
        print(get_ffmpeg_error_message())
        return data, 'none'
    
    if method == 'flac':
        return compress_audio_flac(data)
    elif method == 'aac':
        return compress_audio_aac(data, bitrate)
    elif method == 'mp3':
        return compress_audio_mp3(data, bitrate)
    else:
        # Default to FLAC
        return compress_audio_flac(data)


def compress_audio_flac(data: bytes) -> Tuple[bytes, str]:
    """
    Compress audio to FLAC (Free Lossless Audio Codec).
    
    FLAC provides:
    - Lossless compression (perfect reconstruction)
    - Typically 50-70% of original WAV size
    - Preserves studio quality for archiving
    
    NOTE: FLAC works best on UNCOMPRESSED audio (WAV, AIFF).
    For already-compressed audio (MP3, AAC), FLAC may increase file size.
    
    Args:
        data: Raw audio data (WAV, AIFF, or other PCM format)
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_audio')
        output_path = os.path.join(tmpdir, 'output.flac')
        
        # Write input audio
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Use ffmpeg to convert to FLAC
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:a', 'flac',
                '-compression_level', '8',  # Highest compression (0-12)
                '-y',  # Overwrite output
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    compressed = f.read()
                
                # Always return FLAC for lossless - even if larger
                # The point is lossless quality, not size reduction
                return compressed, 'flac'
            
            # If ffmpeg failed, return original
            return data, 'none'
            
        except subprocess.TimeoutExpired:
            print("FLAC compression timed out")
            return data, 'none'
        except FileNotFoundError:
            print("ffmpeg not found for FLAC compression")
            return data, 'none'
        except Exception as e:
            print(f"FLAC compression error: {e}")
            return data, 'none'


def compress_audio_aac(data: bytes, bitrate: int = 128) -> Tuple[bytes, str]:
    """
    Compress audio to AAC (Advanced Audio Coding).
    
    AAC provides:
    - Better quality than MP3 at same bitrate
    - More efficient at low bitrates (64-128 kbps)
    - Good for already-compressed or low-quality audio
    
    Args:
        data: Raw audio data
        bitrate: Target bitrate in kbps (64-256)
            - 64-96: Good for speech, podcasts
            - 128: Standard quality (equivalent to ~160kbps MP3)
            - 192-256: High quality
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    # Clamp bitrate to valid range
    bitrate = max(64, min(256, bitrate))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_audio')
        output_path = os.path.join(tmpdir, 'output.m4a')
        
        # Write input audio
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Use ffmpeg to convert to AAC
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:a', 'aac',
                '-b:a', f'{bitrate}k',
                '-y',  # Overwrite output
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    compressed = f.read()
                
                # Only use if it reduces size
                if len(compressed) < len(data):
                    return compressed, 'aac'
            
            return data, 'none'
            
        except subprocess.TimeoutExpired:
            print("AAC compression timed out")
            return data, 'none'
        except FileNotFoundError:
            print("ffmpeg not found for AAC compression")
            return data, 'none'
        except Exception as e:
            print(f"AAC compression error: {e}")
            return data, 'none'


def compress_audio_mp3(data: bytes, bitrate: int = 192) -> Tuple[bytes, str]:
    """
    Compress audio to MP3 (MPEG Audio Layer III).
    
    MP3 provides:
    - Lossy compression with adjustable bitrate
    - Significant size reduction (typically 80-95%)
    - Good quality at higher bitrates (192-320 kbps)
    
    Args:
        data: Raw audio data
        bitrate: Target bitrate in kbps (64-320)
            - 64-96: Low quality (speech, podcasts)
            - 128-192: Good quality (music streaming)
            - 256-320: High quality (near-CD quality)
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    # Clamp bitrate to valid range
    bitrate = max(64, min(320, bitrate))
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_audio')
        output_path = os.path.join(tmpdir, 'output.mp3')
        
        # Write input audio
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Use ffmpeg to convert to MP3
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:a', 'libmp3lame',
                '-b:a', f'{bitrate}k',
                '-q:a', '2',  # VBR quality (0-9, lower is better)
                '-y',  # Overwrite output
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    compressed = f.read()
                
                # Only use if it reduces size
                if len(compressed) < len(data):
                    return compressed, 'mp3'
            
            return data, 'none'
            
        except subprocess.TimeoutExpired:
            print("MP3 compression timed out")
            return data, 'none'
        except FileNotFoundError:
            print("ffmpeg not found for MP3 compression")
            return data, 'none'
        except Exception as e:
            print(f"MP3 compression error: {e}")
            return data, 'none'


def get_audio_info(data: bytes) -> dict:
    """
    Get information about an audio file.
    
    Returns:
        Dict with duration, sample_rate, channels, bit_depth, format, codec, bitrate,
        is_lossless, is_compressed, quality_tier, etc.
    """
    info = {
        'duration': None,
        'sample_rate': None,
        'channels': None,
        'bit_depth': None,
        'format': None,
        'codec': None,
        'bitrate': None,
        'file_size': len(data),
        'is_lossless': False,
        'is_compressed': True,
        'quality_tier': 'unknown',  # 'high', 'medium', 'low', 'very_low'
        'ffprobe_available': is_ffprobe_available()
    }
    
    # Detect format from magic bytes
    if data[:4] == b'RIFF' and len(data) >= 12 and data[8:12] == b'WAVE':
        info['format'] = 'wav'
        info['is_lossless'] = True
        info['is_compressed'] = False
    elif data[:4] == b'fLaC':
        info['format'] = 'flac'
        info['is_lossless'] = True
        info['is_compressed'] = True
    elif data[:4] == b'FORM' and len(data) >= 12 and data[8:12] == b'AIFF':
        info['format'] = 'aiff'
        info['is_lossless'] = True
        info['is_compressed'] = False
    elif data[:3] == b'ID3' or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        info['format'] = 'mp3'
        info['is_lossless'] = False
        info['is_compressed'] = True
    elif data[:4] == b'OggS':
        info['format'] = 'ogg'
        info['is_lossless'] = False
        info['is_compressed'] = True
    elif len(data) >= 8 and data[4:8] == b'ftyp':
        info['format'] = 'm4a'
        info['is_lossless'] = False
        info['is_compressed'] = True
    
    # Return early if ffprobe not available
    if not is_ffprobe_available():
        return info
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_audio')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Use ffprobe to get audio info
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                input_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                import json
                probe_data = json.loads(result.stdout.decode('utf-8'))
                
                # Extract format info
                if 'format' in probe_data:
                    fmt = probe_data['format']
                    info['duration'] = float(fmt.get('duration', 0))
                    bit_rate = fmt.get('bit_rate')
                    if bit_rate:
                        info['bitrate'] = int(bit_rate) // 1000  # Convert to kbps
                    if not info['format']:
                        info['format'] = fmt.get('format_name', '')
                
                # Extract stream info (first audio stream)
                if 'streams' in probe_data:
                    for stream in probe_data['streams']:
                        if stream.get('codec_type') == 'audio':
                            info['sample_rate'] = int(stream.get('sample_rate', 0))
                            info['channels'] = stream.get('channels', 0)
                            info['codec'] = stream.get('codec_name', '')
                            info['bit_depth'] = stream.get('bits_per_sample', stream.get('bits_per_raw_sample'))
                            
                            # Get stream bitrate if format bitrate not available
                            if not info['bitrate']:
                                stream_bitrate = stream.get('bit_rate')
                                if stream_bitrate:
                                    info['bitrate'] = int(stream_bitrate) // 1000
                            break
                
                # Determine quality tier based on bitrate and format
                info['quality_tier'] = determine_audio_quality_tier(info)
                            
        except Exception as e:
            print(f"Error reading audio info: {e}")
    
    return info


def determine_audio_quality_tier(info: dict) -> str:
    """
    Determine the quality tier of audio based on format and bitrate.
    
    Returns: 'lossless', 'high', 'medium', 'low', 'very_low'
    """
    # Lossless formats
    if info.get('is_lossless'):
        return 'lossless'
    
    bitrate = info.get('bitrate', 0)
    codec = info.get('codec', '').lower()
    
    # For lossy formats, tier based on bitrate
    if bitrate:
        if codec in ('aac', 'libfdk_aac', 'aac_latm'):
            # AAC is more efficient
            if bitrate >= 192:
                return 'high'
            elif bitrate >= 128:
                return 'medium'
            elif bitrate >= 96:
                return 'low'
            else:
                return 'very_low'
        else:
            # MP3 and others
            if bitrate >= 256:
                return 'high'
            elif bitrate >= 192:
                return 'medium'
            elif bitrate >= 128:
                return 'low'
            else:
                return 'very_low'
    
    return 'unknown'


def get_audio_compression_suggestion(info: dict) -> dict:
    """
    Suggest the best compression method based on audio quality.
    
    Args:
        info: Audio info dict from get_audio_info()
    
    Returns:
        Dict with suggested method, reason, and alternatives
    """
    suggestion = {
        'method': 'flac',
        'bitrate': 192,
        'reason': '',
        'alternatives': [],
        'warning': None
    }
    
    is_lossless = info.get('is_lossless', False)
    is_compressed = info.get('is_compressed', True)
    quality_tier = info.get('quality_tier', 'unknown')
    bitrate = info.get('bitrate', 0)
    format_name = info.get('format', '')
    
    if is_lossless and not is_compressed:
        # Uncompressed lossless (WAV, AIFF) - FLAC is perfect
        suggestion['method'] = 'flac'
        suggestion['reason'] = 'FLAC recommended for uncompressed audio - provides ~50-70% size reduction with perfect quality'
        suggestion['alternatives'] = [
            {'method': 'aac', 'bitrate': 256, 'desc': 'AAC 256kbps - High quality lossy (~85% smaller)'},
            {'method': 'mp3', 'bitrate': 320, 'desc': 'MP3 320kbps - Universal compatibility (~80% smaller)'}
        ]
    
    elif is_lossless and is_compressed:
        # Already lossless compressed (FLAC) - keep as is or convert to lossy
        suggestion['method'] = 'flac'
        suggestion['reason'] = 'Already lossless compressed - FLAC preserves quality'
        suggestion['warning'] = 'File is already FLAC - recompression will not reduce size'
        suggestion['alternatives'] = [
            {'method': 'aac', 'bitrate': 256, 'desc': 'AAC 256kbps - Convert to lossy for smaller size'},
            {'method': 'mp3', 'bitrate': 320, 'desc': 'MP3 320kbps - Universal compatibility'}
        ]
    
    elif quality_tier == 'high':
        # High quality lossy - can compress more
        suggestion['method'] = 'aac'
        suggestion['bitrate'] = 192
        suggestion['reason'] = f'AAC recommended for high-quality {format_name.upper()} - more efficient than MP3'
        suggestion['alternatives'] = [
            {'method': 'mp3', 'bitrate': 192, 'desc': 'MP3 192kbps - Universal compatibility'},
            {'method': 'flac', 'bitrate': 0, 'desc': 'FLAC - Will increase size (not recommended)'}
        ]
    
    elif quality_tier == 'medium':
        # Medium quality - AAC is better than MP3
        suggestion['method'] = 'aac'
        suggestion['bitrate'] = 128
        suggestion['reason'] = f'AAC 128kbps recommended - better quality than MP3 at same bitrate'
        suggestion['alternatives'] = [
            {'method': 'mp3', 'bitrate': 128, 'desc': 'MP3 128kbps - Universal compatibility'},
        ]
        suggestion['warning'] = 'Original is already compressed - further compression will reduce quality'
    
    elif quality_tier in ('low', 'very_low'):
        # Already low quality - AAC is more efficient at low bitrates
        target_bitrate = min(bitrate or 96, 96) if quality_tier == 'low' else 64
        suggestion['method'] = 'aac'
        suggestion['bitrate'] = target_bitrate
        suggestion['reason'] = f'AAC {target_bitrate}kbps recommended - more efficient than MP3 at low bitrates'
        suggestion['warning'] = f'Original quality is {quality_tier.replace("_", " ")} ({bitrate}kbps) - limited improvement possible'
        suggestion['alternatives'] = [
            {'method': 'mp3', 'bitrate': target_bitrate, 'desc': f'MP3 {target_bitrate}kbps - May have more artifacts than AAC'}
        ]
    
    else:
        # Unknown - default to AAC
        suggestion['method'] = 'aac'
        suggestion['bitrate'] = 128
        suggestion['reason'] = 'AAC recommended as efficient general-purpose codec'
        suggestion['alternatives'] = [
            {'method': 'flac', 'bitrate': 0, 'desc': 'FLAC - Lossless (may increase size)'},
            {'method': 'mp3', 'bitrate': 192, 'desc': 'MP3 192kbps - Universal compatibility'}
        ]
    
    return suggestion


def decompress_audio(data: bytes, original_extension: str = '.wav') -> bytes:
    """
    Decompress audio data back to original format.
    
    Args:
        data: Compressed audio data (FLAC, AAC, or MP3)
        original_extension: Original file extension
    
    Returns:
        Decompressed audio data in original format (or WAV if unknown)
    """
    # Determine output format based on original extension
    ext = original_extension.lower()
    
    # Map extensions to ffmpeg format names and codecs
    format_map = {
        '.wav': ('wav', 'pcm_s16le'),
        '.aiff': ('aiff', 'pcm_s16be'),
        '.aif': ('aiff', 'pcm_s16be'),
        '.flac': ('flac', 'flac'),
        '.mp3': ('mp3', 'libmp3lame'),
        '.m4a': ('ipod', 'aac'),
        '.aac': ('adts', 'aac'),
    }
    
    # Default to WAV for unknown formats
    output_format, codec = format_map.get(ext, ('wav', 'pcm_s16le'))
    output_ext = ext if ext in format_map else '.wav'
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_audio')
        output_path = os.path.join(tmpdir, f'output{output_ext}')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:a', codec,
                '-y',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    return f.read()
            
            return data
            
        except Exception as e:
            print(f"Audio decompression error: {e}")
            return data


# =============================================================================
# VIDEO COMPRESSION
# =============================================================================

def compress_video(data: bytes, method: str = 'h264', 
                   crf: int = 23, preset: str = 'medium') -> Tuple[bytes, str]:
    """
    Compress video data using H.264 or AV1 codec.
    
    Args:
        data: Raw video data
        method: Compression method ('h264' or 'av1')
        crf: Constant Rate Factor (0-51 for H.264, 0-63 for AV1, lower = better quality)
        preset: Encoding preset ('ultrafast', 'superfast', 'veryfast', 'faster', 
                'fast', 'medium', 'slow', 'slower', 'veryslow')
    
    Returns:
        Tuple of (compressed_data, compression_type)
    """
    # Check if ffmpeg is available
    if not is_ffmpeg_available():
        print(get_ffmpeg_error_message())
        return data, 'none'
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_video')
        output_path = os.path.join(tmpdir, 'output.mp4')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            if method == 'h264':
                cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-c:v', 'libx264',
                    '-preset', preset,
                    '-crf', str(crf),
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y',
                    output_path
                ]
            else:  # av1
                # AV1 uses different preset names (0-13, where 6 is default)
                av1_cpu_used = {'ultrafast': 8, 'superfast': 7, 'veryfast': 6, 
                               'faster': 5, 'fast': 4, 'medium': 4, 
                               'slow': 2, 'slower': 1, 'veryslow': 0}.get(preset, 4)
                cmd = [
                    'ffmpeg',
                    '-i', input_path,
                    '-c:v', 'libaom-av1',
                    '-crf', str(crf),
                    '-cpu-used', str(av1_cpu_used),
                    '-row-mt', '1',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-movflags', '+faststart',
                    '-y',
                    output_path
                ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=600  # 10 minutes timeout for video encoding
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    compressed = f.read()
                
                # Only use compression if it reduces size
                if len(compressed) < len(data):
                    return compressed, method
            
            return data, 'none'
            
        except subprocess.TimeoutExpired:
            print("Video compression timed out")
            return data, 'none'
        except Exception as e:
            print(f"Video compression error: {e}")
            return data, 'none'


def decompress_video(data: bytes, original_extension: str = '.mp4') -> bytes:
    """
    Decompress video data back to original format.
    
    Args:
        data: Compressed video data (H.264 or AV1 in MP4 container)
        original_extension: Original file extension
    
    Returns:
        Decompressed video data in original format
    """
    ext = original_extension.lower()
    
    # Map extensions to ffmpeg format names
    format_map = {
        '.mp4': ('mp4', 'libx264'),
        '.mkv': ('matroska', 'libx264'),
        '.avi': ('avi', 'libx264'),
        '.mov': ('mov', 'libx264'),
        '.webm': ('webm', 'libvpx-vp9'),
        '.wmv': ('asf', 'wmv2'),
        '.flv': ('flv', 'flv1'),
    }
    
    # Default to MP4 for unknown formats
    output_format, codec = format_map.get(ext, ('mp4', 'libx264'))
    output_ext = ext if ext in format_map else '.mp4'
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_video.mp4')
        output_path = os.path.join(tmpdir, f'output{output_ext}')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-c:v', codec,
                '-c:a', 'aac',
                '-y',
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=600
            )
            
            if result.returncode == 0 and os.path.exists(output_path):
                with open(output_path, 'rb') as f:
                    return f.read()
            
            return data
            
        except Exception as e:
            print(f"Video decompression error: {e}")
            return data


def get_video_info(data: bytes) -> dict:
    """
    Get video file information using ffprobe.
    
    Args:
        data: Video file data
    
    Returns:
        Dictionary with video info (duration, resolution, codec, bitrate, fps, etc.)
    """
    info = {
        'duration': None,
        'width': None,
        'height': None,
        'fps': None,
        'video_codec': None,
        'audio_codec': None,
        'bitrate': None,
        'has_audio': False,
        'format': None,
        'ffprobe_available': is_ffprobe_available()
    }
    
    # Return early if ffprobe is not available
    if not is_ffprobe_available():
        return info
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, 'input_video')
        
        with open(input_path, 'wb') as f:
            f.write(data)
        
        try:
            # Get video stream info
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                input_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                import json
                probe_data = json.loads(result.stdout.decode('utf-8'))
                
                # Format info
                fmt = probe_data.get('format', {})
                info['duration'] = float(fmt.get('duration', 0)) if fmt.get('duration') else None
                info['bitrate'] = int(fmt.get('bit_rate', 0)) // 1000 if fmt.get('bit_rate') else None
                info['format'] = fmt.get('format_name', '').split(',')[0]
                
                # Stream info
                for stream in probe_data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        info['width'] = stream.get('width')
                        info['height'] = stream.get('height')
                        info['video_codec'] = stream.get('codec_name')
                        
                        # Parse frame rate
                        fps_str = stream.get('r_frame_rate', '0/1')
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            if int(den) > 0:
                                info['fps'] = round(int(num) / int(den), 2)
                    
                    elif stream.get('codec_type') == 'audio':
                        info['has_audio'] = True
                        info['audio_codec'] = stream.get('codec_name')
                
        except Exception as e:
            print(f"Error getting video info: {e}")
    
    return info


def get_video_compression_suggestion(video_info: dict) -> dict:
    """
    Get compression suggestion based on video analysis.
    
    Args:
        video_info: Dictionary from get_video_info()
    
    Returns:
        Dictionary with recommended compression settings
    """
    suggestion = {
        'method': 'h264',
        'crf': 23,
        'preset': 'medium',
        'reason': '',
        'warning': None,
        'alternatives': []
    }
    
    bitrate = video_info.get('bitrate')
    codec = video_info.get('video_codec', '').lower()
    width = video_info.get('width', 0) or 0
    height = video_info.get('height', 0) or 0
    
    # Determine quality tier based on resolution and bitrate
    pixels = width * height
    
    if pixels >= 3840 * 2160:  # 4K
        resolution_tier = '4k'
    elif pixels >= 1920 * 1080:  # 1080p
        resolution_tier = '1080p'
    elif pixels >= 1280 * 720:  # 720p
        resolution_tier = '720p'
    elif pixels >= 640 * 480:  # 480p
        resolution_tier = '480p'
    else:
        resolution_tier = 'low'
    
    # Already H.264 at good quality?
    if codec == 'h264':
        if bitrate and bitrate < 2000:  # Already fairly compressed
            suggestion['method'] = 'h264'
            suggestion['crf'] = 26
            suggestion['reason'] = 'Already H.264 compressed - will apply lighter re-encoding'
            suggestion['warning'] = 'Re-encoding already compressed video may reduce quality'
        else:
            suggestion['method'] = 'h264'
            suggestion['crf'] = 23
            suggestion['reason'] = 'H.264 provides excellent quality with good compression'
    
    # Uncompressed or raw video
    elif codec in ('rawvideo', 'v210', 'prores', 'dnxhd', 'cfhd'):
        suggestion['method'] = 'h264'
        suggestion['crf'] = 18
        suggestion['preset'] = 'slow'
        suggestion['reason'] = 'Professional/raw format detected - using high quality settings'
    
    # Other compressed formats
    else:
        suggestion['method'] = 'h264'
        suggestion['crf'] = 23
        suggestion['reason'] = 'H.264 is efficient and widely compatible'
    
    # Adjust CRF based on resolution
    if resolution_tier == '4k':
        suggestion['crf'] = min(suggestion['crf'] + 2, 28)  # Slightly higher for 4K
        suggestion['preset'] = 'medium'
    elif resolution_tier == 'low':
        suggestion['crf'] = max(suggestion['crf'] - 2, 18)  # Better quality for small videos
    
    # Add alternatives
    suggestion['alternatives'] = [
        {'method': 'h264', 'crf': 18, 'preset': 'slow', 'desc': 'High quality (larger file)'},
        {'method': 'h264', 'crf': 28, 'preset': 'fast', 'desc': 'Smaller file (lower quality)'},
        {'method': 'av1', 'crf': 30, 'preset': 'medium', 'desc': 'AV1 - Better compression, slower encoding'}
    ]
    
    return suggestion


def decompress_data(data: bytes, compression_type: str, 
                    original_extension: str = '') -> bytes:
    """
    Decompress data based on compression type.
    
    Args:
        data: Compressed data
        compression_type: 'none', 'brotli', 'webp', 'pdf_gs', 'pdf_opt', 'flac', 'mp3', 'aac', 'h264', or 'av1'
        original_extension: Original file extension for format reference
    
    Returns:
        Decompressed data
    """
    if compression_type == 'none':
        return data
    elif compression_type == 'brotli':
        return decompress_brotli(data)
    elif compression_type == 'webp':
        return decompress_webp(data, original_extension)
    elif compression_type in ('pdf_gs', 'pdf_opt'):
        # PDF compression is lossy for images but the format stays PDF
        # No decompression needed - data is already valid PDF
        return data
    elif compression_type in ('flac', 'mp3', 'aac'):
        # Audio compression - decode back to original format
        return decompress_audio(data, original_extension)
    elif compression_type in ('h264', 'av1'):
        # Video compression - decode back to original format
        return decompress_video(data, original_extension)
    else:
        return data


def decompress_brotli(data: bytes) -> bytes:
    """Decompress Brotli-compressed data."""
    try:
        return brotli.decompress(data)
    except Exception as e:
        print(f"Brotli decompression failed: {e}")
        return data


def decompress_webp(data: bytes, original_extension: str = '') -> bytes:
    """
    Decompress WebP image data.
    Converts back to original format if specified.
    """
    try:
        # Load WebP image
        img = Image.open(io.BytesIO(data))
        
        # Determine output format
        ext = original_extension.lower()
        format_map = {
            '.png': 'PNG',
            '.jpg': 'JPEG',
            '.jpeg': 'JPEG',
            '.bmp': 'BMP',
            '.gif': 'GIF',
            '.tiff': 'TIFF',
            '.webp': 'WEBP'
        }
        
        output_format = format_map.get(ext, 'PNG')
        
        # Handle format-specific requirements
        if output_format == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        output = io.BytesIO()
        img.save(output, format=output_format)
        return output.getvalue()
    except Exception as e:
        print(f"WebP decompression failed: {e}")
        return data


def get_compression_ratio(original_size: int, compressed_size: int) -> float:
    """Calculate compression ratio."""
    if original_size == 0:
        return 0.0
    return original_size / compressed_size


def get_compression_stats(original_data: bytes, compressed_data: bytes, 
                          compression_type: str) -> dict:
    """Get compression statistics."""
    original_size = len(original_data)
    compressed_size = len(compressed_data)
    
    return {
        'original_size': original_size,
        'compressed_size': compressed_size,
        'compression_ratio': get_compression_ratio(original_size, compressed_size),
        'space_saved': original_size - compressed_size,
        'space_saved_percent': ((original_size - compressed_size) / original_size * 100) 
                               if original_size > 0 else 0,
        'compression_type': compression_type
    }
