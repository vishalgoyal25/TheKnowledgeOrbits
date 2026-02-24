"""
Hybrid AI Brain - Live Validation Script
=========================================
Verifies that EmbeddingService works correctly in BOTH modes:
  1. LOCAL mode  (USE_EMBEDDING_API=False, uses sentence-transformers)
  2. CLOUD mode  (USE_EMBEDDING_API=True,  uses HuggingFace Inference API)

Run inside Docker:
  docker exec TheKnowledgeOrbits_backend python validate_hybrid_ai.py
"""

import os
import sys

# ---- Django setup ----
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
import django  # noqa: E402

django.setup()

from engines.content.services.embedding_service import EmbeddingService  # noqa: E402

# ── helpers ──────────────────────────────────────────────────────────────────

PASS = "\033[92m✅ PASS\033[0m"
FAIL = "\033[91m❌ FAIL\033[0m"
INFO = "\033[94mℹ️  INFO\033[0m"
results = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    msg = f"  {status}  {label}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((label, condition))
    return condition


TEST_TEXTS = [
    "The Constitution of India was adopted on 26 November 1949.",
    "Article 370 granted special status to Jammu and Kashmir.",
    "The Fundamental Rights are enshrined in Part III of the Constitution.",
]

# =============================================================================
# 1. LOCAL MODE
# =============================================================================
print("\n" + "=" * 60)
print("  TEST 1: LOCAL MODE (sentence-transformers)")
print("=" * 60)

os.environ["USE_EMBEDDING_API"] = "False"
EmbeddingService._local_model = None  # reset singleton

try:
    # Single embedding
    vec = EmbeddingService.generate_embedding(TEST_TEXTS[0])
    check("Single embedding returns list", isinstance(vec, list))
    check("Single embedding is 384-dim", len(vec) == 384, f"got {len(vec)} dims")
    check("Single embedding values are floats", all(isinstance(v, float) for v in vec))

    # Batch embedding
    vecs = EmbeddingService.generate_embeddings_batch(TEST_TEXTS)
    check(
        "Batch returns one vector per text",
        len(vecs) == len(TEST_TEXTS),
        f"got {len(vecs)} vectors",
    )
    check("All batch vectors are 384-dim", all(len(v) == 384 for v in vecs))

    # Empty / zero-length guard
    empty_vec = EmbeddingService.generate_embedding("")
    check("Empty string → zero vector (384-dim)", len(empty_vec) == 384)
    check("Empty string → all zeros", all(x == 0.0 for x in empty_vec))

    # Mixed batch (valid + empty)
    mixed = EmbeddingService.generate_embeddings_batch(["", "Valid text", "  "])
    check("Mixed batch output length = input length", len(mixed) == 3)
    check(
        "Mixed batch empty slots are zero vectors",
        all(x == 0.0 for x in mixed[0]) and all(x == 0.0 for x in mixed[2]),
    )
    check("Mixed batch valid slot is non-zero", any(x != 0.0 for x in mixed[1]))

    # create_embedding_record
    record = EmbeddingService.create_embedding_record(
        content_type="chunk", content_id="test-id-001", text="India's Parliament"
    )
    check(
        "create_embedding_record structure",
        all(
            k in record for k in ["content_type", "content_id", "vector", "model_name"]
        ),
    )
    check("create_embedding_record vector dim", len(record["vector"]) == 384)

    local_sample_val = vec[0]
    print(f"\n  {INFO}  First 5 dims of local embedding: {vec[:5]}")

except Exception as e:
    check("LOCAL MODE — no unhandled exceptions", False, str(e))

# =============================================================================
# 2. CLOUD MODE
# =============================================================================
print("\n" + "=" * 60)
print("  TEST 2: CLOUD MODE (HuggingFace Inference API)")
print("=" * 60)

hf_token = os.getenv("HF_API_TOKEN", "")
if not hf_token:
    print(
        f"  {INFO}  HF_API_TOKEN not set — skipping live cloud test (fallback will be tested instead)."
    )
    CLOUD_LIVE = False
else:
    CLOUD_LIVE = True

os.environ["USE_EMBEDDING_API"] = "True"
EmbeddingService._local_model = None

try:
    if CLOUD_LIVE:
        vec_api = EmbeddingService.generate_embedding(TEST_TEXTS[0])
        check("Cloud single embedding returns list", isinstance(vec_api, list))
        check(
            "Cloud single embedding is 384-dim",
            len(vec_api) == 384,
            f"got {len(vec_api)} dims",
        )
        check(
            "Cloud embedding values are floats",
            all(isinstance(v, float) for v in vec_api),
        )

        vecs_api = EmbeddingService.generate_embeddings_batch(TEST_TEXTS)
        check(
            "Cloud batch returns one vector per text", len(vecs_api) == len(TEST_TEXTS)
        )
        check(
            "Cloud batch all vectors are 384-dim", all(len(v) == 384 for v in vecs_api)
        )

        print(f"\n  {INFO}  First 5 dims of cloud embedding: {vec_api[:5]}")

    else:
        # Token missing → should automatically fall back to local model
        print(
            f"  {INFO}  Testing API-mode FALLBACK (no token → falls back to local)..."
        )
        EmbeddingService._local_model = None
        os.environ.pop("HF_API_TOKEN", None)  # Ensure missing

        fallback_vec = EmbeddingService.generate_embedding(TEST_TEXTS[0])
        check("API fallback → local model, returns 384-dim", len(fallback_vec) == 384)
        check(
            "API fallback values are floats",
            all(isinstance(v, float) for v in fallback_vec),
        )

except Exception as e:
    check("CLOUD MODE — no unhandled exceptions", False, str(e))

# =============================================================================
# 3. RESET to LOCAL for production safety
# =============================================================================
os.environ["USE_EMBEDDING_API"] = "False"
EmbeddingService._local_model = None
print(f"\n  {INFO}  Reset USE_EMBEDDING_API=False (local mode default restored).")

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 60)
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
print(f"  RESULT: {passed}/{total} checks passed  |  {failed} failed")

if failed == 0:
    print(f"  {PASS}  Hybrid AI Brain is verified and production-ready!")
else:
    print(f"  {FAIL}  {failed} check(s) need attention.")
print("=" * 60 + "\n")

sys.exit(0 if failed == 0 else 1)
