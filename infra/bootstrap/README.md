# `bootstrap/` — the one-time chicken-and-egg layer

**Creates:** the single S3 bucket that holds the Terraform state for every *other* layer.
**Step:** §11 step 2 · **Cost:** ~$0/month
**Status:** ✅ **APPLIED 2026-10-21 — this layer is now INERT. Do not run it again.**

---

## Why this layer is different from every other one

Every other layer stores its state in an S3 bucket. **That bucket has to be created by something,
and it cannot store its own state in itself before it exists.**

So `bootstrap/` is the only directory in this repository that ran with **local state**, once, by
hand — and then migrated its state into the bucket it had just made.

```
1. No `backend` block        -> terraform apply  -> LOCAL terraform.tfstate on disk
2. ADD the backend block pointing at the bucket just created
3. terraform init -migrate-state   -> the local state is copied INTO the bucket
4. The local .tfstate is now STALE and gitignored. Never run this layer again.
```

🟢 **The result: the bucket now stores the state that describes the bucket.** Self-hosting.

> ⛔ **Run once. Never again.** After step 3 this layer is inert — it exists so the bucket is
> *described in code* rather than clicked into being, which is what makes it reproducible.

---

## ✅ What was created — 2026-10-21

`tko-tfstate-<account-id>` in `ap-south-1`. **Four resources, not one.**

| Resource | Setting | Why |
|---|---|---|
| `aws_s3_bucket` | `force_destroy = false` | AWS refuses to delete a bucket that still holds objects |
| | `prevent_destroy = true` | 🔴 `destroy` **fails with an error**, not a prompt |
| `aws_s3_bucket_versioning` | `Enabled` | 🔴 the **only** recovery path for a corrupted state push |
| `aws_s3_bucket_server_side_encryption_configuration` | `AES256` (SSE-S3) | state is plaintext JSON |
| `aws_s3_bucket_public_access_block` | all four `true` | a public state bucket exposes the whole estate |

🔴 **Why four and not one:** in the console, versioning and encryption look like *checkboxes on a
bucket*. In the AWS **API** they are separate sub-resources with their own endpoints. **Terraform
mirrors the API, not the console.**

⚠️ Any guide showing `versioning { }` *inside* `aws_s3_bucket` predates provider v4 (2022) and will
not apply.

**Console-verified:** region · versioning Enabled · SSE-S3 · all four public-access blocks · the
four `default_tags`. State object present at `bootstrap/terraform.tfstate`. `plan` reads from S3
and reports **No changes**.

---

## 🔴 Initialising this layer — the flag is NOT optional

```bash
terraform init -backend-config=backend.hcl
```

**`backend.tf` deliberately omits the `bucket` argument.** A backend block cannot interpolate, so a
literal bucket name would publish the AWS account id in a **public** repository. Terraform's answer
is **partial configuration**: omit the argument, supply it at init.

| File | |
|---|---|
| `backend.hcl` | 🔒 **gitignored** — holds the real bucket name |
| `backend.hcl.example` | ✅ committed template; explains the trade-off in full |

⚠️ **An account id is not a secret** — it appears in every ARN, and AWS does not treat it as
sensitive. This is defence in depth, not a vulnerability being closed. The cost is one CLI flag.

⚠️ **Forgetting the flag** makes Terraform prompt for the bucket interactively. Annoying, not
dangerous.

⚠️ **A fresh clone has no `backend.hcl`.** Copy the `.example` and fill it in before the first init.

---

## Files

| File | Holds |
|---|---|
| `versions.tf` | `required_version` + the AWS provider constraint |
| `providers.tf` | region, `default_tags`. ⚠️ **No credentials** — the SDK resolves them |
| `variables.tf` | `aws_region`, `project_name` (+ an S3-naming validation rule) |
| `main.tf` | the bucket and its four security settings |
| `outputs.tf` | bucket name · ARN · region · a ready-to-paste backend snippet |
| `backend.tf` | the backend block, **minus** `bucket` |
| `backend.hcl` | 🔒 gitignored — the bucket name |
| `backend.hcl.example` | ✅ committed template |
| `.terraform.lock.hcl` | ✅ **committed** — provider `6.69.1` pinned by checksum across **five platforms** |

🟢 **Five platforms** (`windows_amd64`, `linux_amd64`, `linux_arm64`, `darwin_amd64`,
`darwin_arm64`) so Linux CI verifies against a recorded hash instead of rewriting a tracked file
mid-build — or failing under `init -lockfile=readonly`.

---

## ⛔ Deliberately absent

| | Why |
|---|---|
| **DynamoDB lock table** | S3 native locking (`use_lockfile = true`) replaced it in Terraform 1.11. Tutorials still showing a table predate 2025 |
| **Lifecycle rule on old versions** | state objects are kilobytes, and old versions **are** the recovery path |
| **Bucket policy** | access is granted IAM-side; a resource policy is a second place to look when something is denied |
| **`aws_s3_bucket_ownership_controls`** | since April 2023 every new bucket defaults to `BucketOwnerEnforced` — declaring it restates the default |
| **A `us-east-1` provider alias** | that is CloudFront's problem at step 4, not bootstrap's |
