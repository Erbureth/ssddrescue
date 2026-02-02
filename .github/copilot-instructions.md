# SSD Rescue Tool - AI Coding Agent Instructions

## Project Overview
**ssddrescue** is a command-line helper utility that generates `dd` commands for extracting data from unreliable SSDs in manageable chunks. It operates on storage-constrained machines without network access, allowing data extraction and composition into a single image later.

## Core Purpose & Constraints
- **Command Generation**: Tool generates safe `dd` commands, doesn't execute them directly
- **Chunk-Based Extraction**: Splits large SSD reads into configurable chunk sizes due to limited storage
- **Offline Operation**: No network dependency; runs on isolated systems
- **Later Composition**: Chunks are extracted separately; reassembly happens in a post-processing step
- **Safety First**: Never execute commands without explicit user confirmation; validate device paths rigorously

## Architecture

### Single-File Design
- **ssddrescue.py**: Complete tool in one Python file - fully portable, no additional files needed
- No external dependencies (stdlib only)
- Linux/POSIX systems only (direct `/dev/sdX` access)
- All functions, logic, and utilities contained in this single file

### Data Flow
1. User specifies device, chunk size, and output directory (with optional start/end offsets)
2. Tool validates parameters: device path, chunk size must be power of 2, offset ranges
3. Tool calculates extraction range and validates device capacity
4. Generate sequential `dd` commands for each chunk within the specified range
5. Output manifest file with chunk metadata (size, offset, checksums)
6. User executes generated commands manually or via provided script
7. (Post-recovery) Chunks combined into single image using manifest

## Key Command Patterns

### Parameters
- `--chunk-size`: Size of each extraction chunk (must be power of 2), accepts formats like `512K`, `1M`, `512M`, `1G`. Default: `4G`
- `--start-offset`: Byte offset to start reading from (default: `0`). Accepts same formats as chunk-size
- `--end-offset`: Byte offset to stop reading (default: full device size). Accepts same formats as chunk-size
- `--output-dir`: Directory to store generated chunks
- `--manifest`: Path to manifest file (default: `<output-dir>/manifest.txt`)
- `--device`: Path to device (e.g., `/dev/sdb`)

### Usage Examples (planned)
```bash
# Generate extraction script for 4GB chunks from unreliable SSD (full device)
python3 ssddrescue.py /dev/sdb --chunk-size 4G --output-dir /mnt/storage/chunks

# Extract specific range: 1GB to 5GB in 256MB chunks
python3 ssddrescue.py /dev/sdb --chunk-size 256M --start-offset 1G --end-offset 5G --output-dir /mnt/storage/chunks

# Extract last 2GB in 1GB chunks
python3 ssddrescue.py /dev/sdb --chunk-size 1G --start-offset 8G --output-dir /mnt/storage/chunks

# Output: single executable script containing:
# - dd commands for each chunk
# - manifest as embedded comment block
# - recovery instructions
```

### Typical dd Command Generated
```bash
dd if=/dev/sdb of=/mnt/storage/chunks/disk-0-512M.img bs=512 skip=0 count=512MiB status=progress
```

## Coding Conventions

### Function Organization
- Device operations: `_validate_device()`, `_get_device_size()` - safety-critical
- Parameter validation: `_validate_chunk_size()`, `_validate_offsets()` - ensure chunk is multiple of 2, offsets in valid range
- Size parsing: `_parse_size()` ("500M" → bytes), `_format_size()` (bytes → human-readable with largest whole-number suffix)
- Command generation: `_generate_dd_commands()`, `_calculate_chunk_offsets()`
- Manifest creation: `_create_manifest()` with chunk metadata (offset, size, hash)
- Utility functions: path handling, offset validation

### Output Structure
```python
# Manifest format (plain text, one chunk per line)
# Format: START_HEX ACTUAL_END_HEX
# Filenames inferred as disk-START-PLANNED_END.img using largest SI suffix that yields whole number
# Binary suffixes: K=1024, M=1048576, G=1073741824
# START is the intended start, ACTUAL_END is where reading actually stopped
# Each range boundary uses largest whole-number suffix independently (mixing is OK)
# 
# Filename examples (using largest suffix yielding whole number):
# - 512MB (536870912 bytes) → disk-0-512M.img (512M is whole number)
# - 1GB (1073741824 bytes) → disk-512M-1G.img (512M and 1G are both whole)
# - 28GB (30064771072 bytes) → disk-24G-28G.img (28G is whole number)
# - 26288250880 bytes → disk-0-25088M.img (25088M is whole, not 24.5G - use M not fractional G)
# - 512MB (536870912 bytes) → disk-0-512M.img (NOT disk-0-0.5G.img - prefer M over fractional G)
# - Mixed prefixes OK: disk-1G-1536M.img (1G and 1536M are both whole numbers)
#
0x0 0x20000000
0x20000000 0x40000000
0x40000000 0x5FC00000
...
```

### Error Handling
- Validate device exists before any operations
- Warn if device is mounted (safety check)
- Gracefully handle odd device sizes (chunk rounding)
- Do not generate commands if device appears invalid

## Important Constraints
- **No external dependencies**: Use only Python stdlib
- **Python 3.8+**: Broad Linux compatibility
- **Command-only**: Tool generates commands; user executes them
- **No root enforcement in tool**: Let user handle permissions
- **Dry-run by default**: Show generated commands without execution
- **Idempotent output**: Same inputs always generate same commands for verification
- **Chunk size validation**: Must be power of 2 (binary alignment for potential subdivision)
- **Offset ranges**: Start offset < End offset; End offset ≤ device size

## Code Review Focus Areas
- Does device validation prevent dangerous target paths?
- Are chunk offsets correctly calculated (no gaps/overlaps)?
- Is manifest complete enough for reassembly without the tool?
- Can chunks be executed in any order (if desired)?
- Are checksums or file sizes sufficient for integrity verification?
