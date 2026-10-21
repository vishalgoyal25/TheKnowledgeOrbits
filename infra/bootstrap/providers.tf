# ==============================================================================
# infra/bootstrap/providers.tf
# ==============================================================================
# PURPOSE
#   versions.tf says WHICH plugin. This file says HOW IT IS CONFIGURED.
#
#   That split is not cosmetic. `required_providers` is a dependency
#   constraint - it is read by `terraform init` to decide what to download.
#   A `provider` block is runtime configuration - region, credentials,
#   default tags - and it is read on every plan and apply. Different jobs,
#   different lifecycles, different files.
#
# ------------------------------------------------------------------------------
# WHERE CREDENTIALS COME FROM  (and why they are NOT in this file)
# ------------------------------------------------------------------------------
#   Nothing here names a key. The AWS provider resolves credentials itself, in
#   order: environment variables -> shared config (~/.aws/credentials) ->
#   container role -> EC2 instance profile.
#
#   On this laptop it finds the [default] profile. In CI it will find the
#   short-lived credentials from the OIDC role assumption (step 5).
#
#   The same code therefore works in both places with NO change. That is the
#   whole point, and it is why hardcoding `access_key` in a provider block -
#   which tutorials still show - is both unnecessary and a leak into state.
#
# ------------------------------------------------------------------------------
# default_tags  -  applied to EVERY resource this layer creates
# ------------------------------------------------------------------------------
#   This is a COST tool, not a tidiness tool. It is how "what is costing me
#   money?" gets answered in "Cost Explorer" later, grouped by Layer.
#   Some AWS resources cannot be tagged after creation, so retrofitting is
#   partly impossible - setting them now costs nothing.
#
# ------------------------------------------------------------------------------
# ONE PROVIDER ONLY
# ------------------------------------------------------------------------------
#   Bootstrap creates one S3 bucket in ap-south-1. It needs no second provider.
#   The `us-east-1` alias that CloudFront's certificate requires belongs to
#   modules/cdn/ at step 4 - NOT here. Adding it now would be scaffolding for
#   a problem this layer does not have.
# ==============================================================================


provider "aws" {
  # Resolved from variables.tf. The SAME value must later appear as a literal
  # in every backend.tf `region` field - a mismatch produces "bucket does not
  # exist", in a region where it genuinely does not.
  region = var.aws_region

  # ----------------------------------------------------------------------------
  # Four tags, on every taggable resource this layer creates, automatically.
  #
  # ⚠ TWO LIMITS WORTH KNOWING:
  #   1. Not every AWS resource supports tags. default_tags silently skips
  #      those - it does not error.
  #   2. A resource-level `tags = {}` block MERGES with these rather than
  #      replacing them. If the same key appears in both, the resource-level
  #      value wins.
  # ----------------------------------------------------------------------------
  default_tags {
    tags = {
      Project   = "TheKnowledgeOrbits"
      ManagedBy = "terraform"
      Layer     = "bootstrap"

      # 🔴 "shared", NOT "prod" - and this is deliberate.
      #
      # The state bucket is not a production resource. It stores state for
      # every layer in every environment this account will ever hold. Tagging
      # it Environment=prod would become wrong the moment a live/dev/ appears.
      #
      # Every OTHER layer declares an `environment` variable and passes "prod".
      # Bootstrap is the one exception, so the value is a literal here and no
      # variable is declared for it (see variables.tf).
      Environment = "shared"
    }
  }
}


# ==============================================================================
# CONSIDERED AND DELIBERATELY OMITTED: allowed_account_ids
# ==============================================================================
#   The AWS provider accepts a guardrail that refuses to run against the wrong
#   account:
#
#       provider "aws" {
#         allowed_account_ids = ["<account-id>"]
#       }
#
#   It is a genuinely good safety feature - it would catch "my credentials
#   changed and I just applied production infrastructure into a different
#   account", which is a real and expensive mistake.
#
#   ⛔ Not used here, for one reason: it requires the account id as a LITERAL,
#   and infra/ is tracked in a PUBLIC repository. Everywhere else we go out of
#   our way to keep the account id out of git (variables.tf explains how).
#   Adding it back for a guardrail against a single-account mistake is the
#   wrong trade.
#
#   ⚠ If that trade ever changes - a second account, a shared credential - the
#   clean way is a variable with NO default, supplied at runtime:
#       TF_VAR_allowed_account_id=...  terraform plan
#   The value then never touches a file.
# ==============================================================================
