#!/usr/bin/env python3
"""
SSD Rescue Tool - Generate dd commands for extracting data from unreliable SSDs

This tool operates in two modes:
1. Generate Mode: Creates dd commands for chunk-based extraction
2. Update Manifest Mode: Updates manifest with actual extracted chunk sizes
"""

import argparse
import os
import pathlib
import re
import sys


class SizeParser:
    """Utility class for parsing and formatting human-readable sizes."""
    
    # Binary suffixes (base 1024)
    SUFFIXES = {
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4
    }
    
    @classmethod
    def parse(cls, size_str):
        """
        Parse human-readable size string to bytes.
        
        Supports formats: 512K, 1M, 512M, 1G, 1T
        Uses binary suffixes (base 1024): K=1024, M=1048576, G=1073741824, T=1099511627776
        
        Args:
            size_str: Size string (e.g., "512M", "1G", "1T")
            
        Returns:
            int: Size in bytes
            
        Raises:
            ValueError: If format is invalid
        """
        match = re.match(r'^(\d+)([KMGT])$', size_str)
        if not match:
            raise ValueError(f"Invalid size format: {size_str}")
        value, suffix = match.groups()
        return int(value) * cls.SUFFIXES[suffix]
    
    @classmethod
    def format(cls, bytes_value):
        """
        Format bytes to human-readable size with largest whole-number suffix.
        
        Args:
            bytes_value: Number of bytes
            
        Returns:
            str: Formatted size (e.g., "512M", "1G")
        """
        for suffix in reversed(cls.SUFFIXES):
            suffix_value = cls.SUFFIXES[suffix]
            if bytes_value >= suffix_value and bytes_value % suffix_value == 0:
                return f"{bytes_value // suffix_value}{suffix}"
        return str(bytes_value)  # Return as-is if no suffix matches

    @classmethod
    def format_for_dd(cls, bytes_value):
        """
        Format bytes for dd command (e.g., "512MiB", "1GiB").
        
        Uses binary suffixes (base 1024).
        
        Args:
            bytes_value: Number of bytes
            
        Returns:
            str: Formatted size for dd (e.g., "512MiB", "1GiB")
        """
        for suffix in reversed(cls.SUFFIXES):
            suffix_value = cls.SUFFIXES[suffix]
            if bytes_value >= suffix_value and bytes_value % suffix_value == 0:
                return f"{bytes_value // suffix_value}{suffix}iB"
        return f"{bytes_value}B"  # Return as-is if no suffix matches

class DeviceValidator:
    """Handles device validation and size detection."""
    
    def __init__(self, device_path):
        """
        Initialize device validator.
        
        Args:
            device_path: Path to device (e.g., /dev/sdb)
        """
        self.device_path = device_path
        self._size = None
    
    def validate(self):
        """
        Validate that device exists and is a block device.
        
        Raises:
            SystemExit: If device is invalid
        """
        # TODO: Implement device validation
        pass
    
    def get_size(self):
        """
        Get device size in bytes.
        
        Returns:
            int: Device size in bytes
        """
        # TODO: Implement device size detection
        pass

class Chunk(object):
    """Represents a chunk of data to be extracted."""
    
    def __init__(self, start, end):
        """
        Initialize chunk with start and end offsets.
        
        Args:
            start: Start offset in bytes
            end: End offset in bytes
        """
        self.start = start
        self.end = end
    
    @property
    def size(self):
        """Calculate size of the chunk in bytes."""
        return self.end - self.start
    
    def __str__(self):
        """String representation of the chunk."""
        return f"Chunk(start={self.start}, end={self.end}, size={self.size})"


class ManifestManager:
    """Manages manifest file creation and updates."""
    
    def __init__(self, manifest_path):
        """
        Initialize manifest manager.
        
        Args:
            manifest_path: Path to manifest file
        """
        self.chunks = []
        if manifest_path and os.path.exists(manifest_path):
            self._load_manifest(manifest_path)
    
    def write(self):
        """
        Create manifest file with chunk metadata.
        
        Manifest format: START_HEX ACTUAL_END_HEX (one per line)
        
        Args:
            chunks: List of (start, end) offset tuples
        """
        lines = []
        for chunk in self.chunks:
            start_hex = hex(chunk.start)
            actual_end_hex = hex(chunk.end)
            print(f"{start_hex} {actual_end_hex}")

    def _load_manifest(self, manifest_path):
        """
        Load manifest from file.
        
        Args:
            manifest_path: Path to manifest file
        """
        with open(manifest_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                chunk = self._parse_manifest_line(line)
                if chunk:
                    self.chunks.append(chunk)

    def _parse_manifest_line(self, line):
        """Parse a line from the manifest file.
        Args:
            line: A line from the manifest file
        Returns:
            Chunk: Chunk object with start and end offsets, or None if line is empty
        """
        data = line.split("#", maxsplit=1)[0].strip()  # Remove comments and whitespace
        if not data:
            return None # Skip empty lines
        (start_hex, actual_end_hex) = data.split()
        start = int(start_hex, 16)
        actual_end = int(actual_end_hex, 16)
        return Chunk(start, actual_end)

    def update_from_chunks(self, output_dir):
        """
        Update manifest based on actual extracted chunk files.
        
        Scans output_dir for disk-*.img files and updates manifest
        with actual file sizes (accounts for incomplete reads).
        
        Args:
            output_dir: Directory containing chunk files
            
        Returns:
            str: Updated manifest content
        """
        p = pathlib.Path(output_dir)
        print(f"Updating manifest from chunk files in: {output_dir}", file=sys.stderr)
        new_chunks = []
        for x in p.iterdir():
            if x.is_file() and re.match(r'^disk-[0-9]+[KMGT]?-[0-9]+[KMGT]?\.img$', x.name):
                print(f"Processing chunk file: {x.name}", file=sys.stderr)
                (start_offset, ) = re.match(r'^disk-([0-9]+[KMGT]?)-[0-9]+[KMGT]?\.img$', x.name).groups()
                start_offset = SizeParser.parse(start_offset)
                file_info = x.stat()
                size = file_info.st_size
                if size == 0:
                    print(f"Warning: Chunk file {x.name} has size 0, skipping", file=sys.stderr)
                    continue
                chunk = Chunk(start_offset, start_offset + size)
                new_chunks.append(chunk)
        self.chunks = self.chunks + new_chunks
        self.chunks.sort(key=lambda c: (c.start, c.end))
        self.chunks = self._merge_chunks()

    def get_manifest_gaps_size(self):
        """Calculate the total size of gaps in the manifest."""
        if not self.chunks:
            return 0
        total_gaps = 0
        for i in range(1, len(self.chunks)):
            gap = self.chunks[i].start - self.chunks[i - 1].end
            if gap > 0:
                total_gaps += gap
        return total_gaps

    def _merge_chunks(self):
        """Merge overlapping or contiguous chunks in self.chunks."""
        if not self.chunks:
            return []
        merged = []
        current = self.chunks[0]
        for next_chunk in self.chunks[1:]:
            if current.end >= next_chunk.start:  # Overlapping or contiguous
                current.end = max(current.end, next_chunk.end)  # Merge
            else:
                merged.append(current)
                current = next_chunk
        merged.append(current)  # Add the last chunk
        return merged


class ChunkGenerator:
    """Generates chunks and dd commands for extraction."""
    
    def __init__(self, device_path, output_dir, chunk_size, start_offset=0, end_offset=0):
        """
        Initialize chunk generator.
        
        Args:
            device_path: Path to the device
            output_dir: Output directory path
            chunk_size: Chunk size in bytes
            start_offset: Start offset in bytes (default: 0)
            end_offset: End offset in bytes (default: 0, uses device size)
        """
        self.device_path = device_path
        self.output_dir = output_dir
        self.chunk_size = chunk_size
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.device_size = None
    
    def validate_chunk_size(self):
        """
        Validate that chunk size is a power of 2.
        
        Raises:
            SystemExit: If not a power of 2
        """
        if self.chunk_size <= 0 or (self.chunk_size & (self.chunk_size - 1)) != 0:
            print(f"Error: Chunk size must be a power of 2, got {self.chunk_size} bytes", file=sys.stderr)
            raise RuntimeError("Invalid chunk size")
    
    def validate_offsets(self):
        """
        Validate start and end offsets against device size.
        
        Raises:
            SystemExit: If offsets are invalid
        """
        # TODO: Implement offset validation
        pass
    
    def calculate_chunks(self, manifest_chunks=None):
        """
        Calculate chunk offsets for extraction.

        Args:
            manifest_chunks: Optional list of existing chunks from manifest to avoid re-extracting
        
        Returns:
            list: List of (start, end) tuples for each chunk
        """
        self.end_offset = self.end_offset if self.end_offset > 0 else self.device_size
        chunks_it = iter(manifest_chunks) if manifest_chunks else iter([])
        current_offset = self.start_offset
        chunks = []
        current_manifest_chunk = next(chunks_it, None)
        while current_offset < self.end_offset:
            if current_manifest_chunk:
                if current_manifest_chunk.start <= current_offset and current_offset < current_manifest_chunk.end:
                    # Skip existing chunk
                    current_offset +=  self.chunk_size
                elif current_manifest_chunk.start >= current_offset + self.chunk_size:
                    # No overlap, create new chunk
                    chunk_end = min(current_offset + self.chunk_size, self.end_offset)
                    chunks.append(Chunk(current_offset, chunk_end))
                    current_offset = chunk_end
                else:
                    # Manifest chunk is before current offset, load next manifest chunk
                    current_manifest_chunk = next(chunks_it, None)
            else:
                print(f"No more manifest chunks, creating new chunk at offset {current_offset}", file=sys.stderr)
                # Create new chunk
                chunk_end = min(current_offset + self.chunk_size, self.end_offset)
                chunks.append(Chunk(current_offset, chunk_end))
                current_offset = chunk_end
        return chunks
    
    def generate_dd_commands(self, chunks):
        """
        Generate dd commands for each chunk.
        
        Args:
            chunks: List of (start, end) offset tuples
            
        Returns:
            list: List of dd command strings
        """
        # TODO: Implement dd command generation
        for chunk in chunks:
            yield self._get_dd_command(chunk)

    def _get_dd_command(self, chunk: Chunk):
        """
        Generate dd command for a single chunk.
        
        Args:
            chunk: Chunk object with start and end offsets
        """
        start_dd = SizeParser.format_for_dd(chunk.start)
        start_file = SizeParser.format(chunk.start)
        end_file = SizeParser.format(chunk.end)
        size_dd = SizeParser.format_for_dd(chunk.size)
        out_path = os.path.join(self.output_dir, f"disk-{start_file}-{end_file}.img")
        dd_command = f"dd if={self.device_path} of={out_path} bs=512 count={size_dd} skip={start_dd} status=progress"
        return dd_command


class SSDRescue:
    """Main class orchestrating SSD rescue operations."""
    
    def __init__(self, args):
        """
        Initialize SSD rescue tool.
        
        Args:
            args: Parsed command-line arguments
        """
        self.args = args
        self.data_dir = args.data_dir
        self.manifest_path = args.manifest or 'manifest.txt'
    
    def run_generate_mode(self):
        """
        Execute generate mode: create dd commands and manifest.
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        # Validate device
        device_validator = DeviceValidator(self.args.device)
        device_validator.validate()
        
        # Use manually specified device size if provided, otherwise detect it
        if self.args.device_size:
            device_size = SizeParser.parse(self.args.device_size)
        else:
            device_size = device_validator.get_size()

        # Load existing manifest if it exists (to preserve existing chunks)
        manifest = ManifestManager(self.manifest_path)
        
        # Parse and validate parameters
        chunk_size = SizeParser.parse(self.args.chunk_size)
        start_offset = SizeParser.parse(self.args.start_offset) if self.args.start_offset else 0
        end_offset = SizeParser.parse(self.args.end_offset) if self.args.end_offset else device_size
        
        # Ensure output directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Initialize chunk generator
        chunk_gen = ChunkGenerator(
            self.args.device,
            self.data_dir,
            chunk_size,
            start_offset,
            end_offset
        )
        chunk_gen.device_size = device_size
        
        # Validate chunk size and offsets
        chunk_gen.validate_chunk_size()
        chunk_gen.validate_offsets()
        
        # Calculate chunks and generate commands
        chunks = chunk_gen.calculate_chunks(manifest.chunks)
        commands = chunk_gen.generate_dd_commands(chunks)
        
        # Output commands to stdout
        for cmd in commands:
            print(cmd)
        
        # Create manifest file
        
        return 0
    
    def run_update_manifest_mode(self):
        """
        Execute update manifest mode: update manifest from actual chunk files.
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        # Validate output directory exists
        if not os.path.isdir(self.data_dir):
            print(f"Error: Output directory does not exist: {self.data_dir}", file=sys.stderr)
            return 1
        
        # Update manifest and output to stdout
        manifest = ManifestManager(self.manifest_path)
        manifest.update_from_chunks(self.data_dir)
        manifest.write()
        
        return 0

    def run_statistics_mode(self):
        """
        Execute manifest statistics mode: output statistics about manifest chunks.
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        manifest = ManifestManager(self.manifest_path)
        total_chunks = len(manifest.chunks)
        total_size = sum(chunk.size for chunk in manifest.chunks)
        total_gaps = manifest.get_manifest_gaps_size()
        print(f"Total chunks: {total_chunks}")
        print(f"Total size extracted: {SizeParser.format(total_size)}")
        print(f"Total gaps: {SizeParser.format(total_gaps)}")
        return 0
    
    def run(self):
        """
        Run the tool in the appropriate mode.
        
        Returns:
            int: Exit code (0 for success, 1 for error)
        """
        if self.args.update_manifest:
            return self.run_update_manifest_mode()
        elif self.args.generate:
            return self.run_generate_mode()
        else:
            return self.run_statistics_mode()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='SSD Rescue Tool - Generate dd commands for extracting data from unreliable SSDs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 4GB chunks from full device
  %(prog)s /dev/sdb --chunk-size 4G --data-dir /mnt/storage/chunks
  
  # Extract specific range in 256MB chunks
  %(prog)s /dev/sdb --chunk-size 256M --start-offset 1G --end-offset 5G --data-dir /mnt/storage/chunks
  
  # Update manifest after extraction
  %(prog)s --update-manifest --data-dir /mnt/storage/chunks
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--generate',
        action='store_true',
        help='Generate dd commands for extraction (default mode)'
    )
    mode_group.add_argument(
        '--update-manifest',
        action='store_true',
        help='Update manifest from actual extracted chunk files'
    )
    mode_group.add_argument(
        '--manifest-statistics',
        action='store_true',
        help='Output statistics about manifest chunks'
    )
    
    # Common arguments
    parser.add_argument(
        'device',
        nargs='?',
        help='Device path (e.g., /dev/sdb) - required for generate mode'
    )
    parser.add_argument(
        '--data-dir',
        default='.',
        help='Directory to store chunks or read chunk files from'
    )
    parser.add_argument(
        '--manifest',
        help='Path to manifest file (default: manifest.txt in current directory)'
    )

    # Generate mode specific arguments
    parser.add_argument(
        '--chunk-size',
        default='4G',
        help='Chunk size (must be power of 2). Accepts: 512K, 1M, 512M, 1G, etc. Default: 4G'
    )
    parser.add_argument(
        '--start-offset',
        help='Start offset (default: 0). Accepts same formats as chunk-size'
    )
    parser.add_argument(
        '--end-offset',
        help='End offset (default: full device size). Accepts same formats as chunk-size'
    )
    parser.add_argument(
        '--device-size',
        help='Manually specify device size (overrides automatic detection). Accepts same formats as chunk-size'
    )
    
    args = parser.parse_args()
    
    # Validate mode and arguments
    if args.generate and not args.device:
        parser.error('device argument is required for generate mode')
    
    # Create and run SSDRescue instance
    rescue = SSDRescue(args)
    return rescue.run()


if __name__ == '__main__':
    sys.exit(main())
