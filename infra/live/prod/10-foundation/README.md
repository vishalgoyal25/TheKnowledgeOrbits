# `live/prod/10-foundation/` — the layer nothing else can exist without

**State key:** `prod/10-foundation/terraform.tfstate`
**Step:** §11 step 3 · **Cost:** ~$0.50/month (the Route 53 zone) · **Changes:** yearly
**Status:** ☐ not yet implemented

---

## What this layer owns

| Resource | Module | Note |
|---|---|---|
| VPC, subnets, IGW, route tables | `modules/networking/` | public subnets, no NAT |
| S3 Gateway VPC Endpoint | `modules/networking/` | free |
| **Route 53 hosted zone** | *(bare resource — see below)* | **$0.50/month, the only recurring cost in this layer** |

## 🔴 Why `10-` — the number is the dependency order

```
10-foundation   changes yearly    <- the VPC and the DNS zone
20-platform     changes monthly      (ECR, IAM/OIDC, parameters)
30-web          changes per deploy   (EC2, CloudFront, DNS records)
40-data-factory later
```

**Each layer has its own state file.** A broken `apply` in `30-web` **cannot** delete this VPC,
because the VPC is not in that state file. That is the entire point of the numbering, and it is
what makes `terraform destroy` on `30-web` a routine cost-saving act rather than a gamble.

## ⚠️ This layer is the one you are most careful with

Everything above depends on it. A `-/+ forces replacement` on the VPC would cascade into every
resource in every higher layer. 🔴 **Read the plan output line by line here especially.**

## Outputs other layers consume

| Output | Read by |
|---|---|
| `vpc_id` | `30-web` — security groups (step 6) |
| `public_subnet_ids` | `30-web` — the EC2 instance (step 6) |
| `hosted_zone_id` | `30-web` — ALIAS records + ACM DNS validation (step 4) |
| `name_servers` | 🔴 **you, by hand** — these four values go into the registrar |

## 🔴 The nameserver handover, and its ordering trap

Creating the hosted zone does **not** change DNS. It produces four nameserver values that must be
set at the registrar. ⚠️ **And the order within step 3b is load-bearing:**

```
[a] COPY the two surviving TXT records into Route 53   <- FIRST
      google-site-verification  (Search Console ownership)
      _dmarc                    (email authentication policy)
[b] THEN change the nameservers at the registrar
[c] Wait for propagation (<1h typical, up to 48h)
```

**Reverse [a] and [b] and there is a window where Search Console ownership and the DMARC policy
resolve to nothing.** Full record inventory: plan §13.0.
