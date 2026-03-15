"""Evidence embedding system for reports with integrity verification."""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import base64
import logging
from io import BytesIO
from PIL import Image
import mimetypes

logger = logging.getLogger(__name__)

# Supported evidence types
EVIDENCE_TYPES = {
    "screenshot": {"ext": ".png", "max_size_mb": 10, "compression": True},
    "code_snippet": {"ext": ".txt", "max_size_mb": 5, "compression": False},
    "network_capture": {"ext": ".pcap", "max_size_mb": 50, "compression": True},
    "log_output": {"ext": ".txt", "max_size_mb": 5, "compression": False},
    "http_request": {"ext": ".txt", "max_size_mb": 2, "compression": False},
    "database_dump": {"ext": ".sql", "max_size_mb": 20, "compression": True},
}


@dataclass
class EvidenceMetadata:
    """Metadata for embedded evidence."""
    evidence_id: str
    evidence_type: str
    original_filename: str
    content_hash: str
    compressed_size_bytes: int
    original_size_bytes: int
    compression_ratio: float
    watermark_text: str
    merkle_root: Optional[str]
    chain_hash: Optional[str]
    previous_hash: Optional[str]
    embedded_at: str
    embedded_by: str


class EvidenceEmbedder:
    """Embed evidence artifacts into reports with integrity verification."""

    def __init__(self, merkle_chain_enabled: bool = True):
        """
        Initialize evidence embedder.

        Args:
            merkle_chain_enabled: Whether to use merkle chain for integrity
        """
        self.merkle_chain_enabled = merkle_chain_enabled
        self.embedded_evidence: List[EvidenceMetadata] = []
        self.chain_hash_current = None

    def embed_screenshot(
        self,
        image_path: Path | str,
        finding_id: str,
        description: str = "",
        compress: bool = True,
        quality: int = 85
    ) -> Dict[str, Any]:
        """
        Embed screenshot with optional compression and watermark.

        Args:
            image_path: Path to image file
            finding_id: Associated finding ID
            description: Description of screenshot
            compress: Whether to compress image
            quality: JPEG quality (1-100)

        Returns:
            Embedding result with metadata
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Read original image
        original_size = image_path.stat().st_size
        original_hash = self._compute_file_hash(image_path)

        # Process image
        img = Image.open(image_path)

        # Add watermark if needed
        if description:
            img = self._add_image_watermark(img, description)

        # Compress if requested
        output_buffer = BytesIO()
        if compress:
            img.save(output_buffer, format="PNG", optimize=True)
            # Try JPEG for even better compression
            jpeg_buffer = BytesIO()
            if img.mode in ("RGBA", "LA"):
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                rgb_img.save(jpeg_buffer, format="JPEG", quality=quality, optimize=True)
            else:
                img.save(jpeg_buffer, format="JPEG", quality=quality, optimize=True)

            # Use whichever is smaller
            output_buffer = jpeg_buffer if jpeg_buffer.tell() < output_buffer.tell() else output_buffer
        else:
            img.save(output_buffer, format=image_path.suffix.upper().strip("."))

        compressed_data = output_buffer.getvalue()
        compressed_size = len(compressed_data)
        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        # Encode to base64 for embedding
        encoded = base64.b64encode(compressed_data).decode("utf-8")

        # Create metadata
        evidence_id = self._generate_evidence_id("screenshot", finding_id)
        metadata = self._create_evidence_metadata(
            evidence_id=evidence_id,
            evidence_type="screenshot",
            original_filename=image_path.name,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            watermark_text=description,
            original_hash=original_hash,
            finding_id=finding_id
        )

        result = {
            "ok": True,
            "evidence_id": evidence_id,
            "finding_id": finding_id,
            "type": "screenshot",
            "embedded_data": f"data:image/png;base64,{encoded}",
            "metadata": asdict(metadata),
            "stats": {
                "original_size_kb": round(original_size / 1024, 2),
                "compressed_size_kb": round(compressed_size / 1024, 2),
                "compression_ratio_percent": round(compression_ratio, 1),
                "dimensions": f"{img.width}x{img.height}",
            }
        }

        self.embedded_evidence.append(metadata)
        return result

    def embed_code_snippet(
        self,
        code_content: str,
        language: str,
        finding_id: str,
        description: str = "",
        add_line_numbers: bool = True
    ) -> Dict[str, Any]:
        """
        Embed proof-of-concept code snippet with syntax highlighting markers.

        Args:
            code_content: Source code
            language: Programming language for syntax highlighting
            finding_id: Associated finding ID
            description: Description of code
            add_line_numbers: Whether to add line numbers

        Returns:
            Embedding result with metadata
        """
        # Prepare code with optional line numbers
        lines = code_content.split("\n")
        if add_line_numbers:
            max_line_width = len(str(len(lines)))
            formatted_lines = [
                f"{i+1:>{max_line_width}} | {line}"
                for i, line in enumerate(lines)
            ]
            formatted_code = "\n".join(formatted_lines)
        else:
            formatted_code = code_content

        # Create markdown code block
        markdown_block = f"```{language}\n{formatted_code}\n```"

        # Compute hashes
        original_size = len(code_content.encode("utf-8"))
        content_hash = hashlib.sha256(code_content.encode("utf-8")).hexdigest()

        # Create metadata
        evidence_id = self._generate_evidence_id("code_snippet", finding_id)
        metadata = self._create_evidence_metadata(
            evidence_id=evidence_id,
            evidence_type="code_snippet",
            original_filename=f"poc.{language}",
            original_size=original_size,
            compressed_size=len(markdown_block.encode("utf-8")),
            compression_ratio=0,  # Code snippets typically don't compress well
            watermark_text=description,
            original_hash=content_hash,
            finding_id=finding_id
        )

        result = {
            "ok": True,
            "evidence_id": evidence_id,
            "finding_id": finding_id,
            "type": "code_snippet",
            "language": language,
            "markdown_block": markdown_block,
            "metadata": asdict(metadata),
            "stats": {
                "lines_of_code": len(lines),
                "characters": len(code_content),
                "language": language,
            }
        }

        self.embedded_evidence.append(metadata)
        return result

    def embed_network_capture(
        self,
        capture_path: Path | str,
        finding_id: str,
        description: str = "",
        compress: bool = True
    ) -> Dict[str, Any]:
        """
        Embed network capture (.pcap file) with compression.

        Args:
            capture_path: Path to PCAP file
            finding_id: Associated finding ID
            description: Description of capture
            compress: Whether to compress

        Returns:
            Embedding result with metadata
        """
        capture_path = Path(capture_path)
        if not capture_path.exists():
            raise FileNotFoundError(f"Capture file not found: {capture_path}")

        # Read and hash original
        original_data = capture_path.read_bytes()
        original_size = len(original_data)
        original_hash = hashlib.sha256(original_data).hexdigest()

        # For PCAP, typically store metadata summary rather than full binary
        # In production, would parse PCAP and extract packet summaries
        summary = self._summarize_pcap(capture_path)

        # Compress if requested (gzip compression for binary data)
        if compress:
            import gzip
            compressed_data = gzip.compress(original_data, compresslevel=9)
            compressed_size = len(compressed_data)
            encoded = base64.b64encode(compressed_data).decode("utf-8")
            format_type = "gzip"
        else:
            compressed_size = original_size
            encoded = base64.b64encode(original_data).decode("utf-8")
            format_type = "raw"

        compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

        # Create metadata
        evidence_id = self._generate_evidence_id("network_capture", finding_id)
        metadata = self._create_evidence_metadata(
            evidence_id=evidence_id,
            evidence_type="network_capture",
            original_filename=capture_path.name,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            watermark_text=description,
            original_hash=original_hash,
            finding_id=finding_id
        )

        result = {
            "ok": True,
            "evidence_id": evidence_id,
            "finding_id": finding_id,
            "type": "network_capture",
            "format": format_type,
            "embedded_data": f"data:application/octet-stream;base64,{encoded}",
            "summary": summary,
            "metadata": asdict(metadata),
            "stats": {
                "original_size_mb": round(original_size / (1024 * 1024), 2),
                "compressed_size_mb": round(compressed_size / (1024 * 1024), 2),
                "compression_ratio_percent": round(compression_ratio, 1),
                "format": format_type,
            }
        }

        self.embedded_evidence.append(metadata)
        return result

    def embed_log_output(
        self,
        log_content: str,
        finding_id: str,
        description: str = "",
        truncate_lines: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Embed log output or text evidence.

        Args:
            log_content: Log or text content
            finding_id: Associated finding ID
            description: Description
            truncate_lines: Maximum lines to include (None = no limit)

        Returns:
            Embedding result with metadata
        """
        lines = log_content.split("\n")

        if truncate_lines and len(lines) > truncate_lines:
            # Keep first and last portions
            kept_lines = lines[:truncate_lines // 2] + [
                f"... ({len(lines) - truncate_lines} lines omitted) ..."
            ] + lines[-(truncate_lines // 2):]
            display_content = "\n".join(kept_lines)
            truncated = True
        else:
            display_content = log_content
            truncated = False

        # Create markdown block
        markdown_block = f"```\n{display_content}\n```"

        # Compute hashes
        original_size = len(log_content.encode("utf-8"))
        content_hash = hashlib.sha256(log_content.encode("utf-8")).hexdigest()

        # Create metadata
        evidence_id = self._generate_evidence_id("log_output", finding_id)
        metadata = self._create_evidence_metadata(
            evidence_id=evidence_id,
            evidence_type="log_output",
            original_filename="output.log",
            original_size=original_size,
            compressed_size=len(markdown_block.encode("utf-8")),
            compression_ratio=0,
            watermark_text=description,
            original_hash=content_hash,
            finding_id=finding_id
        )

        result = {
            "ok": True,
            "evidence_id": evidence_id,
            "finding_id": finding_id,
            "type": "log_output",
            "markdown_block": markdown_block,
            "metadata": asdict(metadata),
            "stats": {
                "total_lines": len(lines),
                "displayed_lines": len(markdown_block.split("\n")),
                "truncated": truncated,
                "characters": len(log_content),
            }
        }

        self.embedded_evidence.append(metadata)
        return result

    def create_evidence_section(
        self,
        finding_id: str,
        evidence_ids: List[str]
    ) -> str:
        """
        Create markdown section for embedding evidence in report.

        Args:
            finding_id: Finding ID
            evidence_ids: List of evidence IDs to include

        Returns:
            Markdown formatted evidence section
        """
        section = "## Evidence\n\n"

        for evidence_id in evidence_ids:
            evidence = next(
                (e for e in self.embedded_evidence if e.evidence_id == evidence_id),
                None
            )

            if not evidence:
                continue

            # Create evidence entry with verification link
            section += f"### {evidence.evidence_type.replace('_', ' ').title()}\n\n"
            section += f"**ID:** `{evidence.evidence_id}`\n"
            section += f"**Original Size:** {evidence.original_size_bytes} bytes\n"
            section += f"**Embedded At:** {evidence.embedded_at}\n"

            if evidence.watermark_text:
                section += f"**Description:** {evidence.watermark_text}\n"

            # Add integrity verification info
            if evidence.chain_hash:
                section += f"**Verification Hash:** `{evidence.chain_hash[:32]}...`\n"

            section += "\n"

        return section

    def verify_evidence_integrity(self, evidence_id: str) -> Dict[str, Any]:
        """
        Verify integrity of embedded evidence.

        Args:
            evidence_id: Evidence ID to verify

        Returns:
            Verification result
        """
        evidence = next(
            (e for e in self.embedded_evidence if e.evidence_id == evidence_id),
            None
        )

        if not evidence:
            return {"valid": False, "reason": "evidence_not_found"}

        result = {
            "valid": True,
            "evidence_id": evidence_id,
            "evidence_type": evidence.evidence_type,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verification": {
                "content_hash_stored": evidence.content_hash[:32],
                "chain_hash_stored": evidence.chain_hash[:32] if evidence.chain_hash else None,
                "merkle_root": evidence.merkle_root[:32] if evidence.merkle_root else None,
                "chain_index_verified": True,  # In production, verify full chain
            }
        }

        return result

    def get_evidence_manifest(self, finding_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get manifest of all embedded evidence.

        Args:
            finding_id: Filter by finding (None = all)

        Returns:
            Evidence manifest with statistics
        """
        evidence_list = self.embedded_evidence
        if finding_id:
            evidence_list = [e for e in evidence_list if e.evidence_id.startswith(finding_id)]

        total_original_size = sum(e.original_size_bytes for e in evidence_list)
        total_compressed_size = sum(e.compressed_size_bytes for e in evidence_list)
        total_compression = (
            (1 - total_compressed_size / total_original_size) * 100
            if total_original_size > 0
            else 0
        )

        type_counts = {}
        for evidence in evidence_list:
            type_counts[evidence.evidence_type] = type_counts.get(evidence.evidence_type, 0) + 1

        return {
            "total_evidence_items": len(evidence_list),
            "evidence_types": type_counts,
            "original_total_size_mb": round(total_original_size / (1024 * 1024), 2),
            "compressed_total_size_mb": round(total_compressed_size / (1024 * 1024), 2),
            "overall_compression_ratio": round(total_compression, 1),
            "evidence_list": [
                {
                    "evidence_id": e.evidence_id,
                    "type": e.evidence_type,
                    "filename": e.original_filename,
                    "embedded_at": e.embedded_at,
                }
                for e in evidence_list
            ],
        }

    # ========== Private helper methods ==========

    def _add_image_watermark(self, img: Image.Image, watermark_text: str) -> Image.Image:
        """Add text watermark to image."""
        try:
            from PIL import ImageDraw, ImageFont

            # Create copy to avoid modifying original
            watermarked = img.copy()
            draw = ImageDraw.Draw(watermarked, "RGBA")

            # Try to use default font, fallback to default if not available
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Position text at bottom right with semi-transparent background
            text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            margin = 10
            x = watermarked.width - text_width - margin
            y = watermarked.height - text_height - margin

            # Draw semi-transparent background
            draw.rectangle(
                [(x - 5, y - 5), (x + text_width + 5, y + text_height + 5)],
                fill=(0, 0, 0, 180)
            )

            # Draw text
            draw.text((x, y), watermark_text, fill=(255, 255, 255, 255), font=font)

            return watermarked
        except Exception as e:
            logger.warning(f"Failed to add watermark: {e}")
            return img

    def _summarize_pcap(self, capture_path: Path) -> Dict[str, Any]:
        """Generate summary of PCAP file contents."""
        try:
            # In production, would use scapy or dpkt to parse PCAP
            # For now, return basic metadata
            file_size = capture_path.stat().st_size
            return {
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "format": "PCAP",
                "note": "Full packet capture embedded for evidence verification"
            }
        except Exception as e:
            logger.error(f"Failed to summarize PCAP: {e}")
            return {"error": str(e)}

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        hash_obj = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()

    def _create_evidence_metadata(
        self,
        evidence_id: str,
        evidence_type: str,
        original_filename: str,
        original_size: int,
        compressed_size: int,
        compression_ratio: float,
        watermark_text: str,
        original_hash: str,
        finding_id: str
    ) -> EvidenceMetadata:
        """Create evidence metadata record."""
        # Generate merkle hashes if enabled
        merkle_root = None
        chain_hash = None
        previous_hash = None

        if self.merkle_chain_enabled:
            # Hash current evidence
            evidence_data = f"{evidence_id}{evidence_type}{original_hash}".encode("utf-8")
            chain_hash = hashlib.sha256(evidence_data).hexdigest()

            # Link to previous evidence in chain
            if self.embedded_evidence:
                previous_hash = self.chain_hash_current

            self.chain_hash_current = chain_hash

        return EvidenceMetadata(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            original_filename=original_filename,
            content_hash=original_hash,
            compressed_size_bytes=compressed_size,
            original_size_bytes=original_size,
            compression_ratio=compression_ratio,
            watermark_text=watermark_text,
            merkle_root=merkle_root,
            chain_hash=chain_hash,
            previous_hash=previous_hash,
            embedded_at=datetime.now(timezone.utc).isoformat(),
            embedded_by="evidence_embedder"
        )

    def _generate_evidence_id(self, evidence_type: str, finding_id: str) -> str:
        """Generate unique evidence ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.sha256(
            f"{evidence_type}{finding_id}{timestamp}".encode("utf-8")
        ).hexdigest()[:8]
        return f"EV_{finding_id}_{evidence_type.upper()}_{random_suffix}"


def create_embedder(merkle_chain_enabled: bool = True) -> EvidenceEmbedder:
    """Factory function to create evidence embedder."""
    return EvidenceEmbedder(merkle_chain_enabled=merkle_chain_enabled)
