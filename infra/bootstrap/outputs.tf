# ==============================================================================
# infra/bootstrap/outputs.tf
# ==============================================================================
# PURPOSE
#   Values this layer publishes after an apply.
#
#   An output has two distinct jobs, and bootstrap uses both:
#     1. PRINT a value to the human running the command
#     2. EXPOSE a value for another layer to read via terraform_remote_state
#
# ------------------------------------------------------------------------------
# 🔴 THE REASON THESE EXIST AT ALL  -  you need them to write backend.tf
# ------------------------------------------------------------------------------
#   This layer is unusual: its outputs are consumed by a HUMAN, immediately,
#   as the next manual step.
#
#   `apply` finishes and prints the bucket name. You copy it into backend.tf
#   here, and later into the backend block of 10-foundation, 20-platform and
#   30-web. Without the output you would be reading it out of the console or
#   out of the state file.
#
#   ⚠ So this is the ONE layer whose outputs are not mainly for other layers.
#   The others publish for terraform_remote_state; bootstrap publishes for you.
#
# ------------------------------------------------------------------------------
# WHY THE ACCOUNT ID IS NOT AN OUTPUT
# ------------------------------------------------------------------------------
#   It would be trivial to add:
#       output "account_id" { value = data.aws_caller_identity.current.account_id }
#
#   ⛔ Not doing it. `terraform output` is frequently piped, logged, screenshotted
#   and pasted into chat. The bucket name already embeds the account id for the
#   one purpose that needs it; a second, BARE, copy-paste-friendly surface is
#   avoidable exposure for zero benefit.
#
#   ⚠ Note the honest limit of that reasoning: the account id is NOT a secret -
#   it appears in every ARN and AWS does not treat it as sensitive. This is
#   defence in depth, not a vulnerability being closed. But the repository is
#   public, and the cost of omitting it is nil.
#
# ------------------------------------------------------------------------------
# A NOTE ON `sensitive = true`
# ------------------------------------------------------------------------------
#   Marking an output sensitive redacts it from CLI output - and that is ALL it
#   does. The value is still plaintext in state, and `terraform output -json`
#   still returns it in full.
#
#   Nothing in this layer warrants the flag. It is noted here because the
#   mistake it invites - treating it as encryption - is common and expensive.
# ==============================================================================


output "state_bucket_name" {
  description = "Name of the S3 bucket holding Terraform state for every layer. Copy this into the `bucket` field of each layer's backend.tf."
  value       = aws_s3_bucket.this.id
}


output "state_bucket_arn" {
  description = "ARN of the state bucket. Needed at step 5 to scope the CI role's IAM policy by key prefix, e.g. <arn>/prod/30-web/*"
  value       = aws_s3_bucket.this.arn
}


output "state_bucket_region" {
  description = "Region the state bucket lives in. Must match the `region` field in every backend.tf - a mismatch reports 'bucket does not exist' in a region where it genuinely does not."
  value       = var.aws_region
}


# ------------------------------------------------------------------------------
# A READY-TO-PASTE BACKEND BLOCK
#
# Four layers will each need a backend.tf, and a backend block CANNOT use
# variables - every value must be a literal (it is read before any expression
# is evaluated). So the bucket name gets transcribed by hand four times.
#
# A typo there fails in a genuinely confusing way: Terraform reports that the
# bucket does not exist, which is true of the misspelled name, and says nothing
# about the one that does. This output removes that error class entirely -
# change the `key` line, paste the rest.
#
# ⚠ It prints the account id, as part of the bucket name. That is unavoidable:
# the bucket name IS the thing you need. Note this is not a new exposure - the
# state_bucket_name output above prints exactly the same string. What is still
# avoided is a BARE account_id output (see the header).
# ------------------------------------------------------------------------------
output "backend_config_snippet" {
  description = "Paste into each layer's backend.tf, changing only the `key` line to that layer's path."

  value = <<-EOT

    terraform {
      backend "s3" {
        bucket       = "${aws_s3_bucket.this.id}"
        key          = "CHANGE-ME/terraform.tfstate"
        region       = "${var.aws_region}"
        encrypt      = true
        use_lockfile = true
      }
    }

    # key values, one per layer:
    #   bootstrap/terraform.tfstate
    #   prod/10-foundation/terraform.tfstate
    #   prod/20-platform/terraform.tfstate
    #   prod/30-web/terraform.tfstate
  EOT
}
