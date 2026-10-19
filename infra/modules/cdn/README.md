# `modules/cdn/` — CloudFront + ACM + Route 53 records

**Used by:** `live/prod/30-web/` · **Step:** §11 step 4 · **Cost:** ~$1/month
**Status:** ☐ not yet implemented

> ⚠️ Renamed from `static-site/`. **The frontend is NOT a static site** — it mixes SSR, ISR and CSR,
> so CloudFront fronts a **Node runtime**, not a bucket of HTML. The old name encoded a wrong
> assumption.

---

## 🔴 The two-region rule — the classic first-attempt failure

```
ap-south-1 (Mumbai)              us-east-1 (N. Virginia)
+---------------------+          +-----------------------+
| VPC / EC2 / S3      |          |  ACM CERTIFICATE      |
+---------------------+          +-----------+-----------+
                                             |
                       CloudFront accepts a certificate
                       ONLY if issued in us-east-1.
```

**CloudFront's control plane lives in N. Virginia and will not see a certificate issued anywhere
else** — including the region everything else is in. This module therefore needs a **second
provider alias**:

```hcl
provider "aws" { alias = "us_east_1"  region = "us-east-1" }
```

…and the `aws_acm_certificate` resource must carry `provider = aws.us_east_1`. **That one line is
what people forget**, and the resulting error ("certificate not found") names neither the region
nor the cause.

## 🔴 A12 — both domains serve, no redirect

| | Consequence |
|---|---|
| **Certificate** | apex as `domain_name`, `www` in `subject_alternative_names` |
| **CloudFront** | **both** names in `aliases` |
| **Route 53** | 🔴 **two ALIAS records**, apex and `www`, to the same distribution |

**ALIAS, not CNAME.** DNS forbids a `CNAME` at a zone apex, and CloudFront has no fixed IP — ALIAS
is Route 53's answer and it is the whole reason DNS moves here from the registrar.

## 🔴 Behaviours — one domain, two backends

| Path pattern | Cache | Why |
|---|---|---|
| `/_next/static/*` | **hard** | content-hashed filenames, immutable |
| `/static/*` | **hard** | Django admin CSS etc. |
| `/api/*` | 🔴 **none** — forward all headers + cookies | dynamic, authenticated |
| `/*` (default) | short / origin-controlled | SSR + ISR pages |

> 🔴 **One path must be verified, not assumed: the SSE stream.** The Research Agent streams
> `text/event-stream` with a 15-second heartbeat. **CloudFront may buffer it**, turning a live
> stream into one clump at the end — a failure that looks like "slow", not like an error.
> **Either exclude that path from CloudFront, or prove streaming works end to end.**

## Contract

| Inputs | `domain_name` · `subject_alternative_names` · `hosted_zone_id` · `origin_domain_name` · `origin_type` (`s3` \| `custom`) |
|---|---|
| **Outputs** | `distribution_id` (CI needs it for invalidations) · `distribution_domain_name` · `certificate_arn` |

⚠️ **`origin_type` exists because step 4 points at an S3 placeholder and step 6 switches the same
distribution to the EC2 instance.** Designing for that switch now avoids rewriting the module later.
