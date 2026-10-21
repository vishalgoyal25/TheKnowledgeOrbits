# ==============================================================================
# infra/bootstrap/backend.tf
# ==============================================================================
#
#   ✅ ACTIVATED 2026-10-21, after `apply` created the bucket.
#
#   ⚠ THIS FILE WAS DELIBERATELY INERT UNTIL NOW - and the reason is worth
#   keeping, because it is the whole shape of this layer:
#
#   Uncommenting it before the bucket existed would have recreated the exact
#   catch-22 bootstrap exists to break. `terraform init` would have tried to
#   reach a bucket that had not been created yet, and failed.
#
# ==============================================================================
# WHAT A `backend` BLOCK IS
# ==============================================================================
#   It answers one question: WHERE DOES THIS LAYER'S STATE FILE LIVE?
#
#   With no backend block  -> LOCAL state, a terraform.tfstate file on disk.
#   With an s3 backend     -> state lives in S3, shared and lockable.
#
#   ⚠ It is NOT a resource. It creates NOTHING in AWS. It configures the TOOL -
#   which is why it sits in `terraform { }` alongside required_version, and why
#   it cannot use variables or interpolation: it is read BEFORE any expression
#   is evaluated. Every value must be a literal.
#
#   ⚠ Two `terraform { }` blocks in one layer is fine and is the normal layout -
#   versions.tf holds the version pins, this file holds the backend. Terraform
#   merges them. (A configuration may contain only ONE `backend` block, though.)
#
# ==============================================================================
# THE DANCE  -  this file was step 2 of 3
# ==============================================================================
#
#   1. ✅ terraform apply       (no backend block -> LOCAL state)
#                               -> bucket tko-tfstate-<account-id> created
#                               -> terraform.tfstate sat on the DISK
#
#   2. ✅ UNCOMMENT the block below, with the real bucket name from
#         `terraform output state_bucket_name`
#
#   3. ⏭ terraform init -migrate-state
#                               -> Terraform notices the backend changed and
#                                  offers to COPY the local state into S3
#                               -> answer "yes"
#                               -> the local .tfstate is then STALE (and
#                                  gitignored). The bucket now stores the state
#                                  that describes the bucket itself.
#
#   After that, this layer is inert. It runs once and is never applied again.
#
# ==============================================================================


terraform {
  backend "s3" {
    # ------------------------------------------------------------------------
    # 🔴 `bucket` IS DELIBERATELY ABSENT  -  partial backend configuration.
    #
    # A backend block cannot interpolate, so a literal bucket name here would
    # publish the AWS account id in a PUBLIC repository. Terraform's answer is
    # PARTIAL CONFIGURATION: omit the argument and supply it at init time.
    #
    #     terraform init -backend-config=backend.hcl
    #
    #   backend.hcl           🔒 gitignored, holds the real bucket name
    #   backend.hcl.example   ✅ committed template, explains the trade-off
    #
    # ⚠ An account id is NOT a secret - it is in every ARN, and AWS does not
    # treat it as sensitive. This is defence in depth, not a vulnerability being
    # closed. But the repo is public and the cost is one CLI flag.
    #
    # ⚠ FORGETTING THE FLAG is the one failure mode: Terraform will prompt for
    # the bucket interactively rather than fail. Annoying, not dangerous.
    # ------------------------------------------------------------------------

    # ------------------------------------------------------------------------
    # 🔴 THE KEY IS THE WHOLE LAYERING MECHANISM.
    #
    # One bucket, one key PER LAYER, four completely independent state objects:
    #
    #     bootstrap/terraform.tfstate            <- this file
    #     prod/10-foundation/terraform.tfstate
    #     prod/20-platform/terraform.tfstate
    #     prod/30-web/terraform.tfstate
    #
    # A `terraform destroy` in 30-web reads ONE object and can only act on what
    # that object lists. The VPC is not in it, so the VPC is untouchable.
    #
    # ⚠ The isolation comes from the KEY, not from having separate buckets.
    # ------------------------------------------------------------------------
    key = "bootstrap/terraform.tfstate"

    # Must match the bucket's actual region. A mismatch reports "bucket does
    # not exist" - which is true, in the region you named.
    region = "ap-south-1"

    # Encrypt the state object from Terraform's side, in addition to the
    # bucket's own SSE-S3 default. Belt and braces, costs nothing.
    encrypt = true

    # ------------------------------------------------------------------------
    # 🟢 S3 NATIVE STATE LOCKING.
    #
    # Terraform writes a .tflock object beside the state while an operation
    # runs, so two concurrent applies cannot corrupt it.
    #
    # ⚠ This REPLACED the DynamoDB lock table, deprecated in Terraform 1.11.
    # Any guide showing `dynamodb_table = "..."` predates 2025. Bootstrap is
    # one bucket, no table - which is why this layer creates exactly one
    # resource family instead of two.
    # ------------------------------------------------------------------------
    use_lockfile = true
  }
}
