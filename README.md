# 🧬 DNA Data Storage Platform v3.0

A comprehensive, user-friendly platform for encoding, encrypting, preparing, and decoding digital data using synthetic DNA sequences. Built with Streamlit for accessible deployment and research collaboration.

## ✨ Features

| Feature | Description | Status |
|---------|-------------|--------|
| **Multi-format Encoding** | Convert text, images, audio, video, PDF to DNA | ✅ |
| **Chaos Encryption** | Secure with Logistic/Hénon/Lorenz chaos systems | ✅ |
| **NGS Fragment Generation** | Prepare sequences for DNA synthesis | ✅ |
| **Quality Verification** | Compare original and reconstructed data | ✅ |
| **Cloud Deployment** | One-click deployment to Streamlit Cloud | ✅ |

## ⚙️ Installation

### **Local Setup**
```bash
# 1. Clone repository
git clone https://github.com/username/dna-storage-platform.git
cd dna-storage-platform

# 2. Create virtual environment
python -m venv venv

# 3. Activate environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Install FFmpeg (required for audio/video)
# On Ubuntu/Debian:
sudo apt-get install ffmpeg
# On Mac:
brew install ffmpeg
# On Windows:
# Download from https://ffmpeg.org/download.html

# 6. Run application
streamlit run app.py
```

### **Streamlit Cloud Deployment**

For Streamlit Cloud deployment, ensure you have these files in your repository root:

1. **`packages.txt`** - System-level dependencies:
   ```
   ffmpeg
   ```

2. **`requirements.txt`** - Python dependencies:
   ```
   streamlit>=1.28.0
   brotli>=1.0.9
   Pillow>=10.0.0
   numpy>=1.24.0
   pandas>=2.0.0
   scikit-image>=0.21.0
   PyPDF2>=3.0.0
   ```

⚠️ **Important:** The `packages.txt` file is **required** for audio and video compression to work on Streamlit Cloud. Without it, FFmpeg will not be available and audio/video features will be disabled.

## File Structure
```
dna_storage/
├── app.py              # Main Streamlit application
├── dna_codec.py        # DNA encoding/decoding logic
├── compression.py      # Compression algorithms (with FFmpeg checks)
├── randomization.py    # Henon chaos map implementation
├── comparison.py       # Quality metrics calculation
├── requirements.txt    # Python dependencies
├── packages.txt        # System dependencies (for Streamlit Cloud)
└── README.md           # This file
```

## Usage Examples

### Complete Workflow
1. **Encode**: Upload file → Select compression → Encode to DNA
2. **Randomize**: Load DNA → Select chaos system → Enter primers → Randomize
3. **NGS Prep**: Load DNA → Set fragment length → Generate fragments
4. **Decode**: Load randomized DNA → Enter primers → Decode to file
5. **Compare**: Load original and decoded → Verify integrity

## Troubleshooting

### Audio/Video Not Working on Streamlit Cloud

If you see "FFmpeg not available" errors:

1. Ensure `packages.txt` exists in your repository root
2. The file should contain only: `ffmpeg`
3. Redeploy your app after adding the file

### Local FFmpeg Issues

If FFmpeg is not found locally:
- **Ubuntu/Debian:** `sudo apt-get install ffmpeg`
- **macOS:** `brew install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

## License
MIT License

## Author
DNA Data Storage Platform v2.0
