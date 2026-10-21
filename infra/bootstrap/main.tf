# ==============================================================================
# infra/bootstrap/main.tf
# ==============================================================================
# PURPOSE
#   The only file in this layer that creates anything: ONE S3 bucket, the one
#   that every other layer stores its Terraform state in.
#
#   ⚠ This is the layer that solves the catch-22 - state needs a bucket, and
#   the bucket needs state. It runs with LOCAL state, creates the bucket, and
#   then its own state is migrated INTO that bucket. See README.md.
#
# ------------------------------------------------------------------------------
# 🔴 WHY FIVE BLOCKS AND NOT ONE  -  the idiom worth internalising
# ------------------------------------------------------------------------------
#   In the AWS console, "Versioning" and "Encryption" look like CHECKBOXES on a
#   bucket. In the AWS API they are SEPARATE SUB-RESOURCES with their own
#   endpoints - PutBucketVersioning, PutBucketEncryption, PutPublicAccessBlock.
#
#   Terraform mirrors the API, not the console. So one conceptual "secure
#   bucket" is four resource blocks plus a data lookup.
#
#   ⚠ Older guides show `versioning { }` as an inline block inside
#   aws_s3_bucket. That was deprecated and then REMOVED in AWS provider v4.
#   Any snippet using it is pre-2022 and will not apply.
#
# ------------------------------------------------------------------------------
# WHAT IS DELIBERATELY ABSENT
# ------------------------------------------------------------------------------
#   ⛔ No DynamoDB lock table. S3 native locking (use_lockfile = true) replaced
#      it as of Terraform 1.11. Most tutorials still show the table - that is a
#      reliable signal the material predates 2025.
#
#   ⛔ No lifecycle rule expiring old versions. State objects are kilobytes;
#      the storage cost is noise, and old versions are the recovery path.
#
#   ⛔ No bucket policy. Access is granted by IAM on the identity side. A
#      resource policy here would be a second place to look when something is
#      denied, for no gain at single-account scale.
#
#   ⛔ No aws_s3_bucket_ownership_controls. Since April 2023 every new bucket
#      defaults to "BucketOwnerEnforced", which disables ACLs entirely - which
#      is exactly what we want. Declaring it would restate the default.
# ==============================================================================


# ------------------------------------------------------------------------------
# A `data` block READS. It never creates and never destroys.
#
# This one asks the live session "whose credentials am I running as?" and
# returns, among other things, the account id.
#
# 🔴 This is what keeps the account id out of every tracked file. The bucket
# name needs it (S3 names are globally unique across all of AWS), but reading
# it at plan time means the value enters the PLAN, never git - and the code
# stays portable to any account.
# ------------------------------------------------------------------------------
data "aws_caller_identity" "current" {}


# ------------------------------------------------------------------------------
# `locals` are computed once and reused. Not strictly required here, but the
# composed name is referenced by outputs.tf too, and naming it once means the
# convention is stated in exactly one place.
# ------------------------------------------------------------------------------
locals {
  # -> tko-tfstate-<account-id>
  state_bucket_name = "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"
}


# ==============================================================================
# 1. THE BUCKET ITSELF
# ==============================================================================
resource "aws_s3_bucket" "this" {
  # Label "this" because there is exactly one - the house convention for a
  # singleton resource (§5.2).
  bucket = local.state_bucket_name

  # Explicit, although false is already the default.
  #
  # With force_destroy = false, AWS REFUSES to delete a bucket that still
  # contains objects. Terraform would have to empty it first, which it will
  # not do. That is the behaviour we want for the one bucket holding every
  # layer's state, and stating it makes the intent reviewable rather than
  # inherited.
  force_destroy = false

  # ----------------------------------------------------------------------------
  # 🔴 THE GUARD AGAINST YOUR OWN `terraform destroy`
  #
  # Understand precisely what this does: it makes `destroy` FAIL WITH AN ERROR
  # rather than prompting. To genuinely remove this bucket you must edit this
  # file first, remove the block, apply, and only then destroy.
  #
  # That friction is the entire point. Deleting this bucket orphans the state
  # of EVERY other layer. The AWS resources would survive and the website would
  # keep running - but Terraform would forget it owns them, and recovery means
  # `terraform import` on dozens of resources by hand.
  #
  # ⚠ Honest limit: this is a SPEED BUMP, not a lock. Anyone who edits this
  # file can remove it. It defends against accident, not intent.
  #
  # ⚠ Also note: §14's "rehearse a teardown" exit criterion applies to the
  # 30-web layer, NOT this one. Bootstrap is the single layer that is never
  # destroyed - it runs once and is then inert.
  # ----------------------------------------------------------------------------
  lifecycle {
    prevent_destroy = true
  }

  # No `tags` block: the four default_tags on the provider are applied
  # automatically to every taggable resource in this layer (providers.tf).
}


# ==============================================================================
# 2. VERSIONING  -  the single most important setting here
# ==============================================================================
# State is REWRITTEN on every apply. If a push is interrupted, or two applies
# race, or a file is corrupted, versioning is the ONLY way back: you restore
# the previous object version.
#
# Without it, a corrupt state file means reconstructing by hand which of ~40
# resources Terraform still believes it owns.
# ==============================================================================
resource "aws_s3_bucket_versioning" "this" {
  # Referencing aws_s3_bucket.this.id rather than local.state_bucket_name is
  # deliberate: it creates an explicit DEPENDENCY EDGE in Terraform's graph, so
  # the bucket is guaranteed to exist before this is applied. Using the local
  # would produce the same string but no ordering guarantee.
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = "Enabled"
  }
}


# ==============================================================================
# 3. ENCRYPTION AT REST
# ==============================================================================
# State is plaintext JSON containing every value Terraform has read. SSE-S3 is
# free and removes a whole class of exposure.
#
# ⚠ AES256 (SSE-S3), not SSE-KMS: a customer-managed key costs ~$1/month plus
# a per-request charge, for benefits this project does not need yet (key policy
# control, cross-account grants, revocation). Revisit only if a compliance
# requirement names it.
# ==============================================================================
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }

    # Irrelevant for SSE-S3 (it is a KMS cost optimisation), so omitted rather
    # than set to a value that does nothing.
  }
}


# ==============================================================================
# 4. PUBLIC ACCESS BLOCK  -  all four, non-negotiable
# ==============================================================================
# A public state bucket would expose the entire infrastructure, including every
# value that has ever passed through a resource. There is no scenario in which
# this bucket should be readable by anyone outside the account.
#
# The four settings are genuinely different controls, which is why AWS exposes
# four booleans rather than one:
# ==============================================================================
resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  # Reject any PUT that carries a public ACL.
  block_public_acls = true

  # Reject any bucket POLICY that would grant public access.
  block_public_policy = true

  # Ignore public ACLs that somehow already exist, rather than honouring them.
  ignore_public_acls = true

  # Restrict access to the bucket policy's own principals - blocks cross-account
  # and anonymous access even if a policy would otherwise permit it.
  restrict_public_buckets = true
}
