# `infra/` — Terraform for TheKnowledgeOrbits on AWS

Infrastructure as Code for the **AWS half** of this system.
**Region:** `ap-south-1` (Mumbai) · **Environment:** `prod` only · **Terraform:** 1.16.6

> 🔴 **Read `FEATURES/AWS/FEATURES_AWS_Deployment.md` before changing anything here.** That file
> owns scope, phase order, cost ceilings and the list of permanently rejected services. This README
> owns only *how to operate what is in this directory*.

---

## 1. 🔴 WHAT TERRAFORM DOES **NOT** MANAGE — read this first

| Not managed here | Where it lives |
|---|---|
| **PostgreSQL + pgvector** | Supabase — external, unchanged, **touched by zero Terraform** |
| **Redis** | Upstash — external, unchanged |
| **Media / images** | Cloudinary |
| **Transactional email** | Brevo |
| **Error tracking / LLM traces** | Sentry · Langfuse |
| **Domain registration + nameservers** | the registrar (DNS *records* are managed here once delegated) |
| **LLM providers** | Groq · Mistral · OpenRouter — plain HTTPS from inside a container |

> 🔴 **This is a feature, not an omission.** Terraform's blast radius is **only the AWS half**, so a
> botched `apply` — or a `destroy` on a bad day — **cannot touch the database.**
>
> ⛔ **Do not add providers for any of the above.** The isolation is the point. If something external
> needs to change, it changes in that vendor's console, and the change is recorded in
> `FEATURES/AWS/FEATURES_AWS_Deployment.md` §16.1 (the platform register).

**Also not managed here:** the application itself. Terraform builds the *place* code runs; CI puts
code *into* it. The only connection is four well-defined seams — see §9 of the plan.

---

## 2. Layout

```
infra/
├── .terraform-version        pinned CLI version
├── bootstrap/                run ONCE, by hand, with LOCAL state
│                             creates the S3 bucket that holds all other state
├── modules/                  reusable, environment-agnostic building blocks
│   ├── networking/           VPC · subnets · route tables
│   ├── storage/              S3 buckets
│   └── cdn/                  CloudFront + ACM + Route 53 records
└── live/
    └── prod/                 the only environment (see "Why no dev" below)
        ├── 10-foundation/    VPC · subnets · DNS zone       (changes yearly)
        └── 30-web/           CloudFront · DNS · EC2         (changes per deploy)
```

⚠️ **Directories appear only when a step needs them.** `20-platform/`, `modules/iam/`,
`modules/web-server/`, `modules/observability/` and `live/prod/40-data-factory/` are **not created
yet** — they arrive at their step. An empty directory is an invitation to fill it with something
nobody asked for.

### Why no `dev` environment

There is **one** database. An AWS "dev" would point at the *production* Supabase project — which is
worse than having no dev environment, because experiments would *feel* safe while writing real
data. The layout allows `live/dev/` later without moving a file.

---

## 3. 🔴 LAYERED STATE — the decision that matters most

**Every `live/prod/NN-*/` directory has its own state file.** That is the entire point of the
numbering.

| | Effect |
|---|---|
| **Blast radius** | a broken `apply` in `30-web` **cannot** delete the VPC — it is not in that state file |
| **Speed** | `plan` refreshes one layer, not every resource in the account |
| **Order** | the numbers encode dependency direction: foundation → platform → app |
| **Safe teardown** | `destroy` on `30-web` to save money is routine, not a gamble |

Layers read each other through `terraform_remote_state` or SSM parameters — **never by sharing one
state file.**

> ⚠️ **One state file for everything is the most common beginner mistake, and it is what makes
> `terraform destroy` genuinely dangerous.** It is also what most tutorials show.

---

## 4. Running it

All commands run **from inside a layer directory**, never from `infra/`.

```bash
cd infra/live/prod/10-foundation
terraform init        # download providers, configure the S3 backend
terraform validate    # syntax + types, offline
terraform fmt         # canonical formatting
terraform plan        # THE DIFF. Changes nothing. Costs nothing.
terraform apply       # execute it
```

> 🔴 **`plan` is free and changes nothing. Run it fifty times for every five applies.**
> **Read every `destroy` line and every `-/+ forces replacement` line before typing yes.**

```
  + create                           safe
  ~ update in-place                  usually safe
-/+ destroy and then create          ← DANGEROUS: new IP, lost disk, lost data
  - destroy                          ← read every single one
```

### Windows note

PowerShell 5.1: **`&&` is a parse error.** Chain with `;` or use
`if ($LASTEXITCODE -eq 0) { ... }`. Use **absolute paths** when changing directory.

---

## 5. 🔴 SAFETY RULES — non-negotiable

| # | Rule |
|---|---|
| 1 | 🔴 **Terraform state is PLAINTEXT.** Anything placed in a `.tf` or `.tfvars` is readable in the state file **forever**, including in every historical version in the bucket |
| 2 | 🔴 **Therefore: Terraform creates the secret CONTAINER; the VALUE is set once out-of-band** (AWS CLI or console). The application reads it at runtime through its IAM role. **No credential, API key or database password ever appears in `infra/`** |
| 3 | ⛔ **Never commit state.** `.gitignore` covers `*.tfstate`, `tfplan`, `.terraform/` and `*.tfvars` — **unscoped, because the repo is public** |
| 4 | ✅ **DO commit `.terraform.lock.hcl`.** It pins provider versions *and checksums* — the Terraform equivalent of `package-lock.json`. Ignoring it lets two machines resolve different provider versions |
| 5 | 🔴 **No long-lived AWS access keys in CI.** GitHub Actions assumes a role via **OIDC** |
| 6 | **Modules contain no `provider` and no `backend` block.** That single rule is what makes a module reusable — breaking it is why people's modules "work in dev but not prod" |
| 7 | **A root module's `main.tf` calls modules and nothing else.** A bare `resource` there is how layers start leaking into each other |
| 8 | 🔴 **Infrastructure never auto-deploys.** `plan` is posted on a PR; `apply` is `workflow_dispatch` only, after a human reads the plan |

---

## 6. Conventions

| Thing | Convention |
|---|---|
| Resource names | `tko-prod-<component>` |
| S3 buckets *(globally unique across all of AWS)* | append the account id — e.g. `tko-tfstate-<account-id>` |
| State keys | `prod/<layer>/terraform.tfstate` |
| Terraform labels | snake_case; `this` for a singleton resource |
| Module directories | lowercase, hyphenated |

Every resource carries four `default_tags` set on the provider — `Project`, `Environment`,
`ManagedBy`, `Layer`. **That is how "what is costing me money?" gets answered in Cost Explorer
later.** Retrofitting tags across live resources is tedious; setting them costs nothing now.

---

## 7. Status

| Layer | State |
|---|---|
| `bootstrap/` | ☐ not yet applied |
| `10-foundation/` | ☐ not yet written |
| `30-web/` | ☐ not yet written |

**Progress, decisions and the per-step cost ledger:** `FEATURES/AWS/` *(gitignored — private)*.

---

## 8. Where the real documentation lives

⚠️ `FEATURES/` is **gitignored**, so the four files below are local-only and are **not** on GitHub.

| File | Owns |
|---|---|
| `FEATURES/AWS/FEATURES_AWS_Deployment.md` | 🔴 **decisions · scope · phase order · exit criteria.** Wins on any decision |
| `FEATURES/AWS/Steps for AWS.md` | the numbered build checklist |
| `FEATURES/AWS/G1_ENV_INVENTORY.md` | every environment variable, its wave, and where it lives on AWS |
| `FEATURES/AWS/AWS_BIBLE.md` | concepts and reference — *why*, not *what* |
