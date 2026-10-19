# `bootstrap/` — the one-time chicken-and-egg layer

**Creates:** the single S3 bucket that holds the Terraform state for every *other* layer.
**Step:** §11 step 2 · **Cost:** ~$0 · **Status:** ☐ not yet applied

---

## Why this layer is different from every other one

Every other layer stores its state in an S3 bucket. **That bucket has to be created by something,
and it cannot store its own state in itself before it exists.**

So `bootstrap/` is the only directory in this repository that runs with **local state**, once, by
hand — and then migrates its state into the bucket it just made.

```
1. No `backend` block here  ->  terraform apply  ->  LOCAL terraform.tfstate on disk
2. ADD the backend block pointing at the bucket just created
3. terraform init -migrate-state   ->  the local state is copied INTO the bucket
4. The local .tfstate is now stale and gitignored. Never run this layer again.
```

> ⛔ **Run once. Never again.** After step 3 this layer is inert — it exists so the bucket is
> *described in code* rather than clicked into being, which is what makes it reproducible.

---

## What it creates

A single S3 bucket, `tko-tfstate-<account-id>`, with:

| Setting | Why |
|---|---|
| **Versioning ON** | 🔴 the only way to recover from a corrupted state push |
| **Default encryption ON** | state is plaintext JSON; encrypt it at rest |
| **Public access blocked** (all four settings) | it contains every value Terraform has ever read |
| **`prevent_destroy` lifecycle** | a guard against your own `terraform destroy` |

⚠️ **No DynamoDB lock table.** S3 native locking (`use_lockfile = true`) replaced it as of
Terraform 1.11. Most tutorials still show the DynamoDB table — that is a dating signal for
out-of-date material.

---

## Files

| File | Holds |
|---|---|
| `versions.tf` | `required_version` + the AWS provider constraint |
| `main.tf` | the bucket and its four security settings |
| `backend.tf` | ⚠️ **added at step 3 of the dance above, not before** |
