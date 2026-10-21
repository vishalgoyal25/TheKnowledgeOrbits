# ==============================================================================
# infra/bootstrap/variables.tf
# ==============================================================================
# PURPOSE
#   The INPUTS to this layer. Every value that could reasonably differ, named
#   once, typed, described, and defaulted.
#
#   A variable is not "a constant with extra steps". It is the layer's public
#   interface: `terraform plan -var=...`, a tfvars file, or an environment
#   variable can all override it. Hardcoded strings scattered through main.tf
#   cannot.
#
# ------------------------------------------------------------------------------
# WHAT IS *NOT* A VARIABLE HERE, AND WHY
# ------------------------------------------------------------------------------
#   The AWS ACCOUNT ID.
#
#   The state bucket must be named `tko-tfstate-<account-id>`, because S3 bucket
#   names are globally unique across every AWS account on earth. So the account
#   id is needed - but it will NOT be a variable and will NOT be written down.
#
#   main.tf reads it from the live session instead:
#
#       data "aws_caller_identity" "current" {}
#       ... "${var.project_name}-tfstate-${data.aws_caller_identity.current.account_id}"
#
#   Why that matters: infra/ is TRACKED and the repository is PUBLIC. An account
#   id in a tracked file enables account enumeration. Reading it at plan time
#   means the value never enters git, and the code stays portable to any account.
#
# ------------------------------------------------------------------------------
# NO terraform.tfvars FOR THIS LAYER  -  deliberate
# ------------------------------------------------------------------------------
#   §5.1's root-module file set lists terraform.tfvars, but bootstrap has no
#   value worth overriding: it runs once, by hand, in one region, for one
#   account. Defaults cover it.
#
#   And tfvars is gitignored as a safety default (it is the file people put
#   secrets in), so skipping it means one less untracked file whose absence
#   could confuse the next reader.
#
#   ⚠ Later layers WILL have one. This exception is specific to bootstrap.
#
# ------------------------------------------------------------------------------
# NO SECRETS. EVER. NOT EVEN AS A VARIABLE WITH sensitive = true.
# ------------------------------------------------------------------------------
#   `sensitive = true` only redacts a value from CLI OUTPUT. It is still stored
#   in PLAINTEXT in the state file, forever, in every historical version.
#
#   That flag is a display convenience, not a security control, and mistaking
#   the two is a classic error. Secrets are created as EMPTY containers by
#   Terraform and filled out-of-band (§7.2). Bootstrap has none at all, which
#   is part of why it is the right first apply.
#
# ------------------------------------------------------------------------------
# ONLY TWO VARIABLES  -  and why `environment` is not one of them
# ------------------------------------------------------------------------------
#   The state bucket is NOT a prod resource. It stores state for every layer in
#   every environment this account will ever hold. Tagging it Environment=prod
#   would be wrong the moment a live/dev/ appears.
#
#   So providers.tf hardcodes Environment = "shared" for this layer only, and
#   no `environment` variable is declared. Every OTHER layer will declare one
#   and pass "prod".
# ==============================================================================


variable "aws_region" {
  description = "AWS region for the Terraform state bucket. Must match the `region` later written into every backend.tf."
  type        = string
  default     = "ap-south-1"
}


variable "project_name" {
  description = "Short project slug. Prefixes every resource name: <project_name>-tfstate-<account-id>, tko-prod-web, etc."
  type        = string
  default     = "tko"

  # ----------------------------------------------------------------------------
  # A `validation` block catches a bad value at PLAN time, with a message you
  # wrote - instead of at APPLY time, with an opaque error from the AWS API.
  #
  # This one exists because project_name becomes part of an S3 BUCKET NAME, and
  # S3 naming rules are stricter than most AWS resources:
  #   - 3 to 63 characters
  #   - lowercase letters, digits and hyphens ONLY
  #   - no underscores, no uppercase, must start/end alphanumeric
  #
  # Note the project uses `data_factory` (underscore) for the Django engine but
  # `tko-data-factory` (hyphen) for the S3 bucket - that difference is exactly
  # this rule, and it is why the check is worth having.
  # ----------------------------------------------------------------------------
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$", var.project_name))
    error_message = "project_name must be lowercase alphanumeric with hyphens, 3-32 chars, and start and end with a letter or digit (S3 bucket naming rules)."
  }
}
