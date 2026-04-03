# SSD Rescue Tool - AI Coding Agent Instructions

## Project Overview
**ssddrescue** is a command-line helper utility that generates `dd` commands for extracting data from unreliable SSDs in manageable chunks. It operates on storage-constrained machines without network access, allowing data extraction and composition into a single image later.

## Core Purpose & Constraints
- **Command Generation**: Tool generates safe `dd` commands, doesn't execute them directly
- **Chunk-Based Extraction**: Splits large SSD reads into configurable chunk sizes due to limited storage
- **Offline Operation**: No network dependency; runs on isolated systems
- **Safety First**: Never execute commands without explicit user confirmation; validate device paths rigorously
- **Two-Mode Operation**: Generate dd commands OR update manifest from actual chunk reads
 - **Power-of-2 Chunks**: Chunk sizes must be powers of 2 so smaller passes produce exact subranges of earlier, larger ranges
 - **Intended Workflow**: Start with large chunks (e.g., 4G), then rerun with smaller chunks (e.g., 1G, 256M) to fill gaps after read errors

## Architecture

### Single-File Design
- **ssddrescue.py**: Complete tool in one Python file - fully portable, no additional files needed
- No external dependencies (stdlib only)
- Linux/POSIX systems only (direct `/dev/sdX` access)
- All functions, logic, and utilities contained in this single file

### Two Operational Modes

#### Mode 1: Command Generation (--generate)
1. User specifies device, chunk size, and output directory (with optional start/end offsets)
2. Tool validates parameters: device path, chunk size must be power of 2, offset ranges
3. Tool calculates extraction range and validates device capacity
4. Generate sequential `dd` commands for each chunk within the specified range
5. Output manifest file with chunk metadata (size, offset)
6. User executes generated commands manually or via provided script

#### Mode 2: Manifest Update (--update-manifest)
1. User specifies output directory containing extracted chunk files
2. Tool scans directory for files matching pattern `disk-*.img`
3. For each chunk file, reads actual file size (accounts for incomplete reads on error)
4. Updates manifest with actual end offsets based on real file sizes
5. Ranges in manifest without corresponding chunk files are kept as-is (considered successfully read)
6. Contiguous ranges (where end of one equals start of next) are merged into single lines
7. Outputs updated manifest to standard output for user verification
8. User can redirect output to file once verified

**Manifest Update Algorithm Details:**
- File pattern matching: Filenames are parsed as `disk-STARTOFFSET-ENDOFFSET.img` where offsets use human-readable formats with suffixes (512M, 1G, etc.)
- START offset from filename is the reference key; actual file size on disk provides the ACTUAL_END offset
- Example: if `disk-1G-2G.img` actually contains 0x70000000 bytes (1792M), manifest entry becomes `0x40000000 0x70000000`
- Chunk files missing from disk: Original manifest entries covering their ranges are preserved as-is; no warning unless explicitly requested
- Manifest merging: After updating all entries, consecutive lines where one's END equals the next's START are combined. For example:
  ```
  0x0 0x40000000
  0x40000000 0x70000000
  ```
  becomes:
  ```
  0x0 0x70000000
  ```

### Overall Data Flow
1. Mode 1: Generate dd extraction commands and initial manifest
2. User executes dd commands (may get partial reads on unreliable devices)
3. Mode 2: Update manifest based on actual chunk sizes extracted

## Key Command Patterns

### Command-Line Syntax

**Generate Mode (default if not specified):**
```bash
python3 ssddrescue.py DEVICE [--generate] [--chunk-size SIZE] [--start-offset OFFSET] 
                              [--end-offset OFFSET] [--device-size SIZE] --data-dir DIR [--manifest PATH]
```

**Update Manifest Mode:**
```bash
python3 ssddrescue.py --update-manifest --data-dir DIR [--manifest PATH]
```

**Argument Requirements:**
- `DEVICE`: Required for generate mode (e.g., `/dev/sdb`); not used in update-manifest mode
- `--data-dir`: Required for both modes; directory must exist or be creatable
- `--generate`: Optional flag (default behavior when device is specified)
- `--update-manifest`: Required to switch to update mode (device argument then optional)
- All size parameters (`--chunk-size`, `--start-offset`, `--end-offset`, `--device-size`) are optional with sensible defaults

### Mode Selection
- `--generate` (or default): Generate dd commands for extraction
- `--update-manifest`: Update manifest from actual extracted chunk files

### Parameters for Generation (--generate)
- `--chunk-size`: Size of each extraction chunk (must be power of 2), accepts formats like `512K`, `1M`, `512M`, `1G`. Default: `4G`
- `--start-offset`: Byte offset to start reading from (default: `0`). Accepts same formats as chunk-size
- `--end-offset`: Byte offset to stop reading (default: full device size). Accepts same formats as chunk-size
- `--device-size`: Manually specify device size (overrides automatic detection). Accepts same formats as chunk-size. Useful when device is inaccessible or automatic detection fails
- `--data-dir`: Directory to store generated chunks
- `--manifest`: Path to manifest file (default: `manifest.txt` in current directory). Manifest is a plain-text file listing successfully-read ranges. Each line contains: `START_HEX ACTUAL_END_HEX` (e.g., `0x0 0x40000000`). Used in subsequent update-manifest mode to identify already-read ranges.
- `--device`: Path to device (e.g., `/dev/sdb`)

### Parameters for Manifest Update (--update-manifest)
- `--data-dir`: Directory containing extracted chunk files (`disk-*.img`)
- `--manifest`: Path to manifest file to update (default: `manifest.txt` in current directory)

### Usage Examples

#### Generate Mode
```bash
# Generate extraction script for 4GB chunks from unreliable SSD (full device)
python3 ssddrescue.py /dev/sdb --generate --chunk-size 4G --data-dir /mnt/storage/chunks

# Extract specific range: 1GB to 5GB in 256MB chunks
python3 ssddrescue.py /dev/sdb --generate --chunk-size 256M --start-offset 1G --end-offset 5G --data-dir /mnt/storage/chunks

# Extract last 2GB in 1GB chunks
python3 ssddrescue.py /dev/sdb --generate --chunk-size 1G --start-offset 8G --data-dir /mnt/storage/chunks

# Manually specify device size (useful when device is inaccessible or detection fails)
python3 ssddrescue.py /dev/sdb --generate --chunk-size 4G --device-size 500G --data-dir /mnt/storage/chunks

# Output: manifest file with planned chunk offsets and corresponding dd command list
```

#### Update Manifest Mode
```bash
# After running extraction commands, update manifest with actual file sizes
python3 ssddrescue.py --update-manifest --data-dir /mnt/storage/chunks

# Outputs updated manifest to stdout for verification
# User can redirect to file once satisfied with changes:
python3 ssddrescue.py --update-manifest --data-dir /mnt/storage/chunks > manifest.txt
```

#### Handling Partial Reads and Resume Operations
```bash
# Workflow for unreliable SSD with read errors:

# Step 1: Generate initial 1G chunks
python3 ssddrescue.py /dev/sdb --generate --chunk-size 1G --data-dir /mnt/storage/chunks
# → Creates manifest.txt and outputs dd commands

# Step 2: User executes generated dd commands (some may fail or get stuck)
# Commands can be run interactively, in a script, or with timeout wrappers
# Failed chunks produce incomplete .img files

# Step 3: After running commands, update manifest with actual file sizes
python3 ssddrescue.py --update-manifest --data-dir /mnt/storage/chunks > manifest-updated.txt
# → Shows which chunks completed successfully and which have gaps
# → User reviews output to identify incomplete ranges

# Step 4: Generate smaller chunks to fill the gaps
# For example, if there are gaps at 1G boundaries, try 256M chunks:
python3 ssddrescue.py /dev/sdb --generate --chunk-size 256M --data-dir /mnt/storage/chunks --manifest manifest-updated.txt
# → Tool reads manifest to skip already-read ranges
# → Only generates commands for unread portions

# Step 5: Repeat steps 2-4 with progressively smaller chunk sizes until acceptable coverage
```

**Key Points:**
- Chunk commands can be interrupted; tool tracks actual progress via manifest updates
- Failed chunks result in smaller files (dd shows actual bytes transferred)
- Rerunning generate mode with smaller chunks automatically identifies gaps from previous attempts
- No cleanup needed; tool appends to manifest without overwriting previous successful ranges
- Use manifest to identify final unreadable ranges after exhausting practical chunk sizes

### Typical dd Command Generated (in --generate mode)
```bash
dd if=/dev/sdb of=/mnt/storage/chunks/disk-512M-1G.img bs=512 skip=512MiB count=512MiB status=progress
# bs=512 (smallest standard block size) allows reading as much as possible from corrupted drives
# Smaller blocks increase chance of recovering data before hitting unreadable sectors
# Both skip and count use human-friendly size suffixes (KiB/MiB/GiB) matching the planned chunk size
# skip expresses the start offset (e.g., skip=512MiB for starting at 512MiB)
# count expresses the planned byte length (e.g., count=512MiB)
```

**Note**: The dd command syntax shown is correct and intentional. Do not modify or "improve" this command format.

### Output and Behavior

**Generate Mode Output:**
- **To stdout**: List of sequential `dd` commands, one per chunk, formatted for direct execution or piping to a shell script
- **To files**: Creates manifest file at `manifest.txt` in current directory (or custom path if `--manifest` specified)
- **Exit code**: 0 on success, 1 if validation fails (invalid device, bad offsets, etc.)
- **Error handling**: Prints validation errors to stderr and exits without generating commands

**Update Manifest Mode Output:**
- **To stdout**: Updated manifest content (same format: `START_HEX ACTUAL_END_HEX` per line)
- **To files**: No files written directly; user must redirect stdout if updating file
- **Exit code**: 0 on success, 1 if output directory doesn't exist or manifest unreadable
- **Error handling**: Prints warnings to stderr for missing chunk files; continues processing others

## Coding Conventions

### Function Organization
- Device operations: `_validate_device()`, `_get_device_size()` - safety-critical
- Parameter validation: `_validate_chunk_size()`, `_validate_offsets()` - ensure chunk is multiple of 2, offsets in valid range
- Size parsing: `_parse_size()` ("500M" → bytes), `_format_size()` (bytes → human-readable with largest whole-number suffix)
- Command generation: `_generate_dd_commands()`, `_calculate_chunk_offsets()`
- Manifest creation: `_create_manifest()` with chunk metadata (offset, size)
- Utility functions: path handling, offset validation

### Output Structure
```python
# Manifest format (plain text, one chunk per line)
# Format: START_HEX ACTUAL_END_HEX
#
# There are three related offsets:
# START_HEX       - start offset in manifest and in filename
# END_HEX         - planned end offset in filename only
# ACTUAL_END_HEX  - actual end offset in manifest only (what was successfully read)
#
# Filenames are required for manifest updates (tool scans disk-START-END.img).
# Manifest lines do NOT map back to filenames; they are a reference of what was read.
#
# Filename generation (from planned range):
#   disk-START_HUMAN-END_HUMAN.img
# Conversion rule: for each offset, use the largest suffix where offset/suffix is whole number
# Binary suffixes (base 1024): K=1024 (KiB), M=1048576 (MiB), G=1073741824 (GiB)
# Each boundary uses the largest whole-number suffix independently (mixing is OK)
#
# Example planned range → filename:
#   START_HEX=0x0, END_HEX=0x20000000 → disk-0-512M.img
#   START_HEX=0x20000000, END_HEX=0x40000000 → disk-512M-1G.img
#   START_HEX=0x40000000, END_HEX=0x5FC00000 → disk-1G-1536M.img
#
# Manifest workflow example (multi-pass recovery):
#
# After first pass (1G chunks) with read error on second chunk:
0x0 0x40000000           # Chunk 1: 0-1G read successfully
0x40000000 0x7F800000    # Chunk 2: 1G-2G partial (stopped at 2040M due to error)
0x80000000 0xC0000000    # Chunk 3: 2G-3G read successfully
# Gap identified: [2040M, 2G) = [0x7F800000, 0x80000000) = 8M gap
#
# Second pass (256M chunks) - only generates commands where START is not in manifest:
# Check each 256M-aligned offset against manifest ranges to find gaps
# For example, offset 0x70000000 (1792M) is covered by range [0x40000000, 0x7F800000)
# For example, offset 0x80000000 (2G) is covered by range [0x80000000, 0xC0000000)
# Result: All 256M-aligned offsets fall within covered ranges, SKIP all commands
# → No 256M-aligned chunk starts in the 8M gap [2040M, 2G), need finer granularity
#
# Third pass (64M chunks):
# Check each 64M-aligned offset:
# For example, offset 0x7C000000 (1984M) is covered by [0x40000000, 0x7F800000)
# For example, offset 0x7F000000 (2032M) is covered by [0x40000000, 0x7F800000)
# For example, offset 0x80000000 (2G) is covered by [0x80000000, 0xC0000000)
# Result: Still all covered, SKIP all commands
# → Still no 64M-aligned offset in the 8M gap. Need 8M or smaller chunks.
#
# Example with filename mapping to manifest:
#   Filename: disk-512M-1G.img (represents planned range 0x20000000-0x40000000)
#   Manifest: 0x20000000 0x3F800000 (started at 512M, actually read until 1016M due to error)
#   Note: Filename uses planned END (0x40000000), manifest uses actual END (0x3F800000)
...
```
...
```

### Gap-Filling Strategy

When running subsequent passes with smaller chunk sizes, the tool avoids re-reading ranges already in the manifest:
1. For each potential chunk START offset (aligned to current chunk size), check if any manifest range **covers** it
2. A manifest entry covers an offset if: `START_HEX <= offset < ACTUAL_END_HEX` (note: uses actual end, not planned end)
3. Generate a dd command only if no manifest range covers the START offset
4. This ensures the tool focuses on unread gaps while avoiding redundant reads

**Example: Identifying covered vs. uncovered chunks**

Given manifest after first pass (1G chunks):
```
0x0 0x40000000           # Successfully read 0-1G
0x40000000 0x7F800000    # Partial read: 1G-2040M (error at 2040M)
0x80000000 0xC0000000    # Successfully read 2G-3G
```

Gap identified: offset range [0x7F800000, 0x80000000) = [2040M, 2G) = 8M gap

Second pass with 256M chunks - check these aligned offsets:
- Offset 0x0 (0M): covered by [0x0, 0x40000000) ✓ SKIP
- Offset 0x40000000 (1G): covered by [0x40000000, 0x7F800000) ✓ SKIP
- Offset 0x80000000 (2G): covered by [0x80000000, 0xC0000000) ✓ SKIP
- All other 256M-aligned offsets: similarly covered

**Result**: No 256M-aligned offsets fall in the 8M gap [2040M, 2G). Need finer granularity.

Third pass with 64M chunks - check new aligned offsets:
- Offset 0x7C000000 (1984M): covered by [0x40000000, 0x7F800000) ✓ SKIP
- Offset 0x7F000000 (2032M): covered by [0x40000000, 0x7F800000) ✓ SKIP
- Offset 0x80000000 (2G): covered by [0x80000000, 0xC0000000) ✓ SKIP

Still no gap coverage. Need even smaller chunks (32M, 16M, or 8M) to hit the specific [2040M, 2G) range.

**Key insight**: If a gap exists between power-of-2-aligned ranges, use a chunk size that divides that gap evenly. Gap size = 8M, so try 8M chunks, 4M chunks, etc.

### Error Handling
- Validate device exists before any operations
- Warn if device is mounted (user must ensure device is not mounted before running commands)
- Gracefully handle odd device sizes (chunk rounding)
- Do not generate commands if device appears invalid

**Device Validation Details:**
- Device path must exist in `/dev/` (e.g., `/dev/sdb`, `/dev/nvme0n1`)
- Device must be a block device (checked via `os.path.isblk()` or equivalent)
- No paths are rejected; user has full freedom to specify any device (responsibility is on user to avoid dangerous choices)
- Device size must be readable and greater than 0 bytes
- Start offset must be less than end offset, and end offset must not exceed device size
- If device is mounted, tool prints warning but allows generation (user responsible for ensuring safe unmounting)

**Error Handling Scenarios:**
- **Invalid device path**: Device doesn't exist or is not a block device → Print error to stderr, exit code 1
- **Chunk size not power of 2**: e.g., `--chunk-size 500M` → Print error with clarification, exit code 1
- **Invalid offset parameters**: start > end, or end > device size → Print error with actual device size, exit code 1
- **Device read permission denied**: User lacks read permissions on `/dev/sdX` → Print error suggesting sudo or permissions check, allow generation (user responsible for fixing)
- **Device too small**: Device size less than start offset → Print error with actual device size, exit code 1
- **Output directory not writable**: Manifest file cannot be written → Print error to stderr, exit code 1
- **Manifest file missing in update mode**: `--data-dir` exists but manifest doesn't → Print warning to stderr, create empty manifest or skip update gracefully
- **Chunk files missing in update mode**: Some expected `disk-*.img` files not found → Print warning to stderr per file, continue with other files (chunks are assumed already successfully read)
- **Invalid manifest format**: Existing manifest has malformed entries → Print warning to stderr, attempt to parse valid lines or skip invalid ones

## Important Constraints
- **No external dependencies**: Use only Python stdlib
- **Python 3.8+**: Broad Linux compatibility
- **Command-only**: Tool generates commands; user executes them
- **No root enforcement in tool**: Let user handle permissions
- **Dry-run by default**: Show generated commands without execution
- **Idempotent output**: Same inputs always generate same commands for verification
- **Chunk size validation**: Must be power of 2 so smaller passes subdivide earlier ranges exactly
- **Offset ranges**: Start offset < End offset; End offset ≤ device size

## Code Review Focus Areas
- Does device validation prevent dangerous target paths?
- Are chunk offsets correctly calculated (no gaps/overlaps)?
- Is manifest complete and accurate for reference?
- Can chunks be executed in any order (if desired)?
