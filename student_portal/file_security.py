"""
File Upload Security for CODE-IT Student Portal.

Validates uploaded files against:
1. File extension whitelist
2. File size limit (5 MB)
3. Magic bytes (actual file content signature) — prevents renaming
   a .exe or .php to .jpg and uploading it
4. Double-extension tricks (e.g. photo.php.jpg)
5. Null-byte injection in filenames
"""

import os

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # 5 MB

ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}

# Magic byte signatures for allowed image formats
# Each entry is (offset, bytes_sequence)
MAGIC_SIGNATURES = {
    '.jpg':  [(0, b'\xff\xd8\xff')],
    '.jpeg': [(0, b'\xff\xd8\xff')],
    '.png':  [(0, b'\x89PNG\r\n\x1a\n')],
    '.webp': [(0, b'RIFF'), (8, b'WEBP')],
}

# Dangerous extensions that should never be allowed even as secondary
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.msi', '.scr', '.pif',  # Executables
    '.php', '.py', '.rb', '.pl', '.cgi', '.asp', '.aspx',     # Server scripts
    '.js', '.jsx', '.ts', '.tsx', '.vbs', '.wsf',              # Script files
    '.html', '.htm', '.svg', '.xml', '.xhtml',                 # Can contain JS/XSS
    '.sh', '.bash', '.ps1', '.psm1',                           # Shell scripts
    '.jar', '.class', '.war',                                   # Java
    '.dll', '.so', '.dylib',                                    # Libraries
    '.iso', '.img',                                             # Disk images
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_upload(uploaded_file):
    """
    Validate an uploaded file for security.

    Args:
        uploaded_file: Django UploadedFile (from request.FILES)

    Returns:
        (is_valid: bool, error_message: str | None)
        If is_valid is True, error_message is None.
    """

    if uploaded_file is None:
        return False, 'No file was uploaded.'

    filename = uploaded_file.name or ''

    # ── 1. Null-byte injection ──────────────────────────────────────────
    if '\x00' in filename:
        return False, 'Invalid filename detected.'

    # ── 2. Sanitise and check extension ─────────────────────────────────
    basename = os.path.basename(filename)
    _, ext = os.path.splitext(basename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f'File type "{ext}" is not allowed. '
            f'Only PNG, JPG, JPEG, and WebP images are accepted.'
        )

    # ── 3. Double-extension check (e.g. "photo.php.jpg") ───────────────
    name_without_ext = os.path.splitext(basename)[0]
    for part in name_without_ext.split('.'):
        test_ext = f'.{part.lower()}'
        if test_ext in DANGEROUS_EXTENSIONS:
            return False, (
                'Filename contains a suspicious secondary extension. '
                'Please rename your file and try again.'
            )

    # ── 4. File size check ──────────────────────────────────────────────
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        return False, (
            f'File is too large ({uploaded_file.size / (1024*1024):.1f} MB). '
            f'Maximum allowed size is {MAX_FILE_SIZE_MB} MB.'
        )

    # ── 5. Magic bytes — verify file content matches claimed type ──────
    # Read the first 16 bytes (enough for all our signatures)
    header = uploaded_file.read(16)
    uploaded_file.seek(0)  # Reset pointer so Django can save it later

    if len(header) < 4:
        return False, 'File is empty or too small to be a valid image.'

    signatures = MAGIC_SIGNATURES.get(ext, [])
    if signatures:
        for offset, magic in signatures:
            if header[offset:offset + len(magic)] != magic:
                return False, (
                    'File content does not match its extension. '
                    'The file may be corrupted or is not a real image.'
                )

    return True, None
