# `modules/networking/` — VPC, subnets, routing

**Used by:** `live/prod/10-foundation/` · **Step:** §11 step 3 · **Cost:** ~$0
**Status:** ☐ not yet implemented

---

## What it owns

A VPC and the routing that makes a subnet reachable.

```
VPC  10.0.0.0/16
 |
 +-- public subnet  10.0.1.0/24   (AZ a)   route: 0.0.0.0/0 -> IGW
 +-- public subnet  10.0.2.0/24   (AZ b)   route: 0.0.0.0/0 -> IGW
 |
 +-- Internet Gateway
 +-- S3 Gateway VPC Endpoint      (free; keeps S3 traffic off the public path)
```

## 🔴 Two decisions baked in, both deliberate

**1. Public subnets, no NAT Gateway.** A NAT Gateway costs ~$33/month — **more than the server it
would protect**. The security it buys is replaceable: an instance in a public subnet whose security
group admits traffic *only from CloudFront's managed prefix list* has no meaningful attack surface.
⛔ **Permanently rejected** — do not re-propose.

**2. Two AZs, even though only one is used initially.** Subnets are free; retrofitting a second AZ
into a live VPC is not. Capacity for later, cost of nothing now.

> ⚠️ **"Public subnet" is a route-table entry, not a checkbox.** A subnet is public if and only if
> its route table has `0.0.0.0/0 -> igw-*`. There is no flag.

## Contract

| Inputs | |
|---|---|
| `name_prefix` | `tko-prod` |
| `vpc_cidr` | `10.0.0.0/16` |
| `azs` | two availability zones |

| Outputs | Consumed by |
|---|---|
| `vpc_id` | `30-web` (security groups, step 6) |
| `public_subnet_ids` | `30-web` (the EC2 instance, step 6) |

⏸ **Security groups are NOT here.** They land in `modules/security/` at step 6, when there is
something to protect. See §5 of the plan.
