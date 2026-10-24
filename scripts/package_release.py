import os
import sys
import re
import zipfile
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("genius.release_packager")

# Directories to strictly exclude from the deliverable package
EXCLUDED_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "dist_release",
    ".agents",
    ".system_generated",
    ".idea",
    ".vscode",
}

# File names / patterns to strictly exclude
EXCLUDED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".DS_Store",
    "Thumbs.db",
}

EXCLUDED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".log",
    ".tmp",
    ".zip",
    ".tar",
    ".gz",
    ".db",
    ".sqlite",
    ".sqlite3",
}

# Comprehensive regex patterns for pre-packaging secret checks
SUSPICIOUS_SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA|EC|DSA|PGP|OPENSSH) PRIVATE KEY-----"), "Private Key Header"),
    (re.compile(r"sk-or-v1-[a-f0-9]{64}"), "OpenRouter Live API Key"),
    (re.compile(r"sk-(?:proj-|live-)?[a-zA-Z0-9_-]{32,}"), "OpenAI Secret Key"),
    (re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}"), "Anthropic Secret Key"),
    (re.compile(r"hf_[a-zA-Z0-9]{34}"), "HuggingFace Access Token"),
    (re.compile(r"gh[pousr]_[0-9a-zA-Z]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"), "AWS Access Key ID"),
    (re.compile(r"AIza[0-9A-Za-z\\-_]{35}"), "Google API Key"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}"), "Committed JWT Bearer Token"),
]


def audit_file_for_secrets(file_path: Path) -> list[str]:
    """Scans text files for unintended committed credentials or private keys."""
    # Skip binary files by extension
    if file_path.suffix.lower() in {".pkl", ".woff", ".woff2", ".ttf", ".eot", ".png", ".jpg", ".jpeg", ".ico", ".bin"}:
        return []

    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for pattern, desc in SUSPICIOUS_SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(desc)
    except Exception as exc:
        logger.warning(f"Could not read {file_path} for secret scan: {exc}")
    return findings


def should_include(rel_path: Path) -> bool:
    """Evaluates whether a relative path should be included in the release bundle."""
    parts = rel_path.parts

    # Check directory exclusion
    for part in parts[:-1]:
        if part in EXCLUDED_DIRS or part.startswith("."):
            return False

    file_name = parts[-1]
    if file_name in EXCLUDED_FILES:
        return False

    suffix = rel_path.suffix.lower()
    if suffix in EXCLUDED_EXTENSIONS:
        return False

    return True


def create_release_package(
    project_root: Path,
    output_zip: Path,
) -> int:
    """Builds a pristine release archive containing only verified production code."""
    logger.info(f"Initiating clean release packaging from root: {project_root}")
    logger.info(f"Target archive destination: {output_zip}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    files_to_pack: list[tuple[Path, str]] = []
    total_uncompressed_bytes = 0
    security_violations: list[str] = []

    for root, dirs, files in os.walk(project_root):
        # Prune excluded directories in-place during traversal
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            full_path = Path(root) / file
            rel_path = full_path.relative_to(project_root)

            if not should_include(rel_path):
                continue

            # Secret audit
            findings = audit_file_for_secrets(full_path)
            if findings:
                security_violations.append(f"{rel_path}: {', '.join(findings)}")

            size = full_path.stat().st_size
            total_uncompressed_bytes += size
            files_to_pack.append((full_path, str(rel_path).replace("\\", "/")))

    if security_violations:
        logger.error("RELEASE PACKAGING ABORTED: Potential secrets detected:")
        for violation in security_violations:
            logger.error(f"  - {violation}")
        return 1

    logger.info(f"Discovered {len(files_to_pack)} clean files ({total_uncompressed_bytes / (1024*1024):.2f} MB uncompressed).")

    # Build the ZIP archive
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
        for full_path, arcname in files_to_pack:
            zipf.write(full_path, arcname=arcname)

    compressed_size = output_zip.stat().st_size
    logger.info(f"Release package generated successfully: {output_zip}")
    logger.info(f"Package Size: {compressed_size / (1024*1024):.2f} MB ({compressed_size:,} bytes)")
    logger.info(f"Compression Ratio: {(1 - (compressed_size / total_uncompressed_bytes)) * 100:.1f}%")

    # Deep self-verification: audit contents of the generated archive
    logger.info("Performing deep security audit of generated release archive...")
    archive_errors: list[str] = []
    with zipfile.ZipFile(output_zip, "r") as zipf:
        namelist = zipf.namelist()
        for name in namelist:
            # 1. Prohibited directory / cache check
            for bad_prefix in [".git/", ".venv/", "node_modules/", "__pycache__/", ".idea/", ".vscode/"]:
                if bad_prefix in name:
                    archive_errors.append(f"Illegal path '{name}' detected in release archive.")

            # 2. Strict .env check (only .env.example allowed)
            file_name = Path(name).name
            if file_name.startswith(".env") and file_name != ".env.example":
                archive_errors.append(f"Unsanitized environment file '{name}' detected in archive.")

            # 3. Prohibited database extensions
            if Path(name).suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                archive_errors.append(f"Prohibited database file '{name}' detected in archive.")

            # 4. Secret scan of text files in archive
            if Path(name).suffix.lower() not in {".pkl", ".woff", ".woff2", ".ttf", ".eot", ".png", ".jpg", ".jpeg", ".ico", ".bin"}:
                try:
                    file_bytes = zipf.read(name)
                    text_content = file_bytes.decode("utf-8", errors="ignore")
                    for pattern, desc in SUSPICIOUS_SECRET_PATTERNS:
                        if pattern.search(text_content):
                            archive_errors.append(f"Secret detected in archive entry '{name}': {desc}")
                except Exception as exc:
                    logger.warning(f"Could not inspect archive entry {name}: {exc}")

    if archive_errors:
        logger.error("ARCHIVE AUDIT FAILED: Security violations found in output package:")
        for err in archive_errors:
            logger.error(f"  - {err}")
        return 1

    logger.info("Verification passed: Archive is 100% free of .git, .venv, node_modules, .env, and sensitive tokens.")
    return 0


if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent.parent
    target_zip = root_dir / "dist_release" / "Genius_AI_Assistant_Release.zip"
    exit_code = create_release_package(root_dir, target_zip)
    sys.exit(exit_code)
