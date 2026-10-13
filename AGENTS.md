# Human review for SIHSALUS Terminology

Read [README.md](README.md), the affected operational guide, and the nested
instructions in `apps/api` or `apps/web` before changing those applications.
Preserve upstream attribution, local work, credentials, and recovery artifacts.

Agents may investigate, prepare isolated changes, and run appropriate checks.
Keep diffs reviewable and explain the problem, choice, alternatives, failure
modes, and executed/pending verification. Leave the human decision in the
[PR template](.github/PULL_REQUEST_TEMPLATE.md) pending.

Merges, release publication, configuration application, deployments, permission
grants, credential resets, and destructive operations require human approval of
the concrete result. Name the PR/head SHA, manifest/digest and target, or account
and exact roles. A plan approval, “yolo”, green CI, or an earlier operation does
not substitute for review. Material changes require renewed review. Merge and
deployment decisions are separate.

For account administration, first report whether the requested account already
exists, its current and proposed privileges, and whether credentials would change.
Use native OCL mechanisms after approval. Do not reset credentials or create a
duplicate identity as a side effect. For terminology changes, identify the domain
reviewer and preserve unresolved clinical decisions for their review.

Do not approve reviews or deployment jobs through a maintainer's credentials,
enable auto-merge, bypass protections, or present automated review as human
acceptance. Publishing the runtime artifact does not authorize its application.
