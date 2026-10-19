# `live/prod/30-web/` — the application layer

**State key:** `prod/30-web/terraform.tfstate`
**Steps:** §11 step **4** (CDN) then step **6** (compute) · **Changes:** per deploy
**Status:** ☐ not yet implemented

---

## 🔴 This layer is built in TWO passes, deliberately

| Pass | Step | Creates | Cost |
|---|---|---|---|
| **1 — CDN first** | **4** | ACM cert · CloudFront · Route 53 ALIAS records · an S3 **placeholder** page | ~$1 |
| **2 — compute** | **6** | EC2 · EBS · security groups · Caddy · **CloudFront origin switched from S3 to the instance** | ~$14 |

### Why the CDN comes before the compute

> 🟢 **A CDN in front of a bucket is the safest real thing you can build on AWS.** It holds no data,
> costs about a dollar, is fully reversible — and it produces a **working HTTPS URL on day one**.
>
> 🔴 **Learning the `plan -> apply -> destroy -> apply` loop there, rather than on something that
> can lose data, is the entire point.** Step 4 is deliberately out of numeric order for this reason.

## Reads from `10-foundation`

Via `terraform_remote_state` (or SSM parameters) — 🔴 **never by sharing a state file.**

| Needs | For |
|---|---|
| `hosted_zone_id` | ALIAS records + ACM DNS validation (step 4) |
| `vpc_id`, `public_subnet_ids` | the instance and its security group (step 6) |

## 🔴 The teardown rehearsal lives here

`terraform destroy` on **this layer only**, then `apply` again. It proves two claims at once:

- the cost-saving loop works — ⚠️ **until the site is public, stopping compute overnight is free money**
- the blast-radius guarantee is real — **the VPC and the DNS zone survive, because they are in a
  different state file**

**Nothing irreplaceable lives here:** the instance is stateless (its image comes from ECR), the
ISR cache regenerates, and DNS records are recreated with the distribution. 🔴 **Rehearse it once,
early** — an untested teardown is a hope, not a capability.

## ⚠️ Step-6 items already known, recorded so they are not rediscovered

| | |
|---|---|
| **D6** | 🔴 **mandatory now that Path A is locked** — Django and Next share one box, so both run under `systemd` with hard `MemoryMax=`. Without it a Next.js SSR leak can get **Django** OOM-killed, and the site returns 502 while the box looks healthy |
| **Q5a** | instance size still open. `t4g.small` is an **unverified inherited number** — size it against the real load shape (~167 writes/sec, not 16,666) |
| **G5** | Supabase via the **transaction pooler**, `CONN_MAX_AGE=0`, inside the web tier's connection budget |
| **G2** | static files: WhiteNoise on the instance, or `collectstatic` to S3 + OAC |
| **SSE** | 🔴 verify the stream survives CloudFront. It is the most likely thing to break behind a CDN |
