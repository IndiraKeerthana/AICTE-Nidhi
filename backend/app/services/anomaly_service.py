import re
from pathlib import Path
from PIL import Image
import imagehash
from rapidfuzz import fuzz
import fitz

def compute_image_phash(image_path: str) -> str | None:
    """Computes a 64-bit DCT perceptual hash for an image file."""
    try:
        with Image.open(image_path) as img:
            h = imagehash.phash(img)
            return str(h)
    except Exception:
        return None

def inspect_pdf_metadata_and_updates(storage_path: str) -> dict:
    """
    Inspects PDF metadata and counts incremental update markers (%%EOF).
    Multiple %%EOF markers can indicate post-issuance modification.

    Structural Revision vs Cryptographic Signatures:
    - This check inspects trailer %%EOF marker counts and metadata creation/modification dates.
    - It detects incremental updates appended after original PDF compilation.
    - LIMITATION: This is a file structure / revision detection heuristic. It does NOT
      perform cryptographic digital signature validation (PKI / X.509 / PAdES verification).
    """
    result = {
        "creation_date": None,
        "mod_date": None,
        "producer": None,
        "incremental_updates_count": 0,
        "is_suspicious_modification": False,
        "explanation": "Standard single-pass PDF structure."
    }

    try:
        # Check raw bytes for %%EOF trailer count
        with open(storage_path, "rb") as f:
            content = f.read()
            eof_count = content.count(b"%%EOF")
            result["incremental_updates_count"] = max(0, eof_count - 1)
            if eof_count > 2:
                result["is_suspicious_modification"] = True
                result["explanation"] = f"Detected {eof_count} %%EOF trailer blocks, indicating post-issuance file modifications or appended incremental updates. (Structural revision inspection only; not cryptographic digital signature verification.)"

        # PyMuPDF metadata inspection
        doc = fitz.open(storage_path)
        meta = doc.metadata or {}
        result["creation_date"] = meta.get("creationDate")
        result["mod_date"] = meta.get("modDate")
        result["producer"] = meta.get("producer")
        doc.close()

    except Exception as e:
        result["explanation"] = f"Metadata extraction failed: {str(e)}"

    return result

def _normalize_institution_name(text: str) -> str:
    """Normalizes standard institutional abbreviations for robust comparison."""
    s = text.lower()
    abbreviations = {
        r'\bgovt\.?\b': 'government',
        r'\bengg\.?\b': 'engineering',
        r'\binst\.?\b': 'institute',
        r'\btech\.?\b': 'technology',
        r'\bcoll\.?\b': 'college',
        r'\bdept\.?\b': 'department',
        r'\bpoly\.?\b': 'polytechnic',
        r'\bmgmt\.?\b': 'management',
        r'\buniv\.?\b': 'university',
    }
    for pattern, rep in abbreviations.items():
        s = re.sub(pattern, rep, s)
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return ' '.join(s.split())


def evaluate_institution_name_similarity(declared_name: str, candidate_text: str) -> tuple[float, bool]:
    """
    Compares declared institution name against candidate text.
    Handles abbreviations (e.g. Govt. vs Government) and line-level certificate text.
    Returns (similarity_score_pct, is_acceptable_match).
    Threshold: >= 75.0% is acceptable; < 75.0% flags discrepancy.
    """
    if not candidate_text or not declared_name:
        return 100.0, True

    norm_declared = _normalize_institution_name(declared_name)
    if not norm_declared:
        return 100.0, True

    best_score = 0.0
    for raw_line in candidate_text.splitlines():
        line = raw_line.strip()
        if len(line) < 5:
            continue
        norm_line = _normalize_institution_name(line)
        if not norm_line:
            continue
        ts_score = float(fuzz.token_set_ratio(norm_declared, norm_line))
        p_score = float(fuzz.partial_ratio(norm_declared, norm_line))
        best_score = max(best_score, ts_score, p_score)

    norm_candidate = _normalize_institution_name(candidate_text[:1000])
    if norm_candidate:
        block_score = float(fuzz.partial_ratio(norm_declared, norm_candidate))
        best_score = max(best_score, block_score)

    is_acceptable = best_score >= 75.0
    return float(best_score), is_acceptable

def compare_perceptual_hashes(hash1: str, hash2: str) -> int:
    """Returns Hamming distance between two hex perceptual hashes."""
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 999
