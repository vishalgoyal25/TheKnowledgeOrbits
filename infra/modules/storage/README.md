# `modules/storage/` — S3 buckets

**Used by:** `live/prod/30-web/` · **Step:** §11 step 4 · **Cost:** <$1/month
**Status:** ☐ not yet implemented

---

## What it owns

Application S3 buckets. ⛔ **Not** the Terraform state bucket — that belongs to `bootstrap/` and is
deliberately outside any reusable module, because it must exist before modules can be used at all.

| Bucket | Purpose | Step |
|---|---|---|
| `tko-prod-static-<account-id>` | the step-4 **placeholder page**, then Django's `collectstatic` output | 4 |

## 🔴 Every bucket here is PRIVATE

Public Access Block on, all four settings, always. **CloudFront reads the bucket through an Origin
Access Control (OAC)** — the bucket itself is never world-readable.

⚠️ **Two traps that catch people, both avoided by the above:**

1. **`AWS_DEFAULT_ACL = "public-read"` will FAIL.** Since April 2023 buckets default to
   *Bucket owner enforced*, which disables ACLs entirely — setting a public-read ACL raises
   `AccessControlListNotSupported`. Copy-pasted Django/S3 snippets still contain this line.
2. **A "static website hosting" bucket is not needed and not wanted.** That feature serves over
   **HTTP only** and bypasses CloudFront. OAC + a private bucket is the modern pattern.

## ⚠️ An ordering issue to resolve before step 4

Plan §5's tree places S3 under `20-platform/` (step 5), but **step 4 needs the placeholder bucket
and runs first.** Three ways out, to be decided at step 4:

| Option | Trade |
|---|---|
| Bucket lives in `30-web/` | simplest; couples a storage resource to the app layer |
| Bucket lives in `10-foundation/` | foundation is meant to change yearly — a static bucket qualifies |
| Split `20-platform/` and run its storage half early | most correct, most moving parts |

🔴 **Recorded, not decided.** Picking it here would be guessing before the step that owns it.

## Contract

| Inputs | `name_prefix` · `account_id` · `enable_versioning` |
|---|---|
| **Outputs** | `bucket_id` · `bucket_arn` · `bucket_regional_domain_name` (CloudFront needs the *regional* name, not the plain one) |
