# ==============================================================================
# infra/bootstrap/versions.tf
# ==============================================================================
# Tooling constraints for the bootstrap layer.
#
# This file creates NOTHING. It answers one question, before any resource is
# read: "is the tooling running this code the tooling it was written for?"
# Terraform evaluates it first and refuses to continue on a mismatch.
#
# NOTE: there is deliberately NO `backend` block here yet. Bootstrap creates
# the S3 bucket that every other layer stores its state in, so it must first
# run with LOCAL state. `backend.tf` is added AFTER the bucket exists, and the
# local state is then migrated into it. See bootstrap/README.md.
# ==============================================================================

terraform {
  # The CLI version gate.
  #
  # `~> 1.16.6` means >= 1.16.6 and < 1.17.0 - patch fixes are allowed, a minor
  # bump is not. This is the ENFORCED pin; infra/.terraform-version records the
  # same number for version managers (tfenv / tenv) but nothing checks that file
  # on a winget-installed CLI.
  required_version = "~> 1.16.6"

  required_providers {
    # A "provider" is the plugin that turns HCL into one vendor's API calls.
    # Without it, `aws_s3_bucket` is an unrecognised word. `terraform init`
    # downloads this into .terraform/ (gitignored - it is a disposable binary).
    #
    # `~> 6.0` means >= 6.0 and < 7.0: features and fixes, never a major version
    # that could change resource syntax under us.
    #
    # The EXACT resolved version is pinned by .terraform.lock.hcl, which `init`
    # writes and which IS committed - the Terraform equivalent of
    # package-lock.json. This constraint only sets the acceptable range.
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
