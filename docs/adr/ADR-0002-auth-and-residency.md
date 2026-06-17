# ADR-0002: Auth provider and hosting residency

- **Story:** SS-1.8
- **Status:** Accepted (showcase). Gov / defence self-host is a named future swap.
- **Date:** 2026-06-17
- **Deciders:** David (owner)

## Context

Sprintsight introduces the Sprint Suite identity layer and is wired to it first. We need:

- an **auth provider** (do not roll our own), and
- a **datastore** that is Postgres + pgvector (per the SS-1.9 schema), and
- a **data residency** posture that supports the gov / defence angle.

Candidates considered for auth: Supabase Auth, Clerk, Auth0. The schema already assumes Postgres + pgvector. As a solo builder, fewer moving parts wins, provided the gov story is not foreclosed.

## Decision

**Managed Supabase, UK / EU region.**

- Bundles Postgres + pgvector + Auth + storage in one in-region managed service. This collapses several Stage-0 decisions (datastore, vector store, auth, encryption-at-rest) into a single dependency.
- Roles are handled at the application layer via the `app_user` enum (schema decision D4), not via provider-specific role features. This keeps identity portable.
- **Gov / defence path:** Supabase is open-source and self-hostable. A real gov engagement swaps managed Supabase for self-hosted Supabase, or self-managed Postgres plus a self-hostable auth provider. This is a deliberate later step, not now.

## Consequences

**Positive**
- One managed, in-region dependency. Strong solo accelerator.
- Encryption-at-rest is provided, which closes the residual security flag on the SS-1.9 schema.
- Satisfies the schema Group 1 (identity) and the schema security posture.

**Negative / risks**
- Managed SaaS versus self-host tension for a true gov / defence deployment. Accepted for the showcase on synthetic data.
- The Composio MCP (Jira board driver) is already flagged separately as a gov swap point. Residency for connectors is a distinct decision from residency for the datastore.
- Vendor coupling on auth. Mitigation: keep `app_user` decoupled from provider-specific fields so a provider swap touches the edge, not the domain.

## Revisit triggers

- A real gov / defence engagement.
- Moving from synthetic data to real client data.
- Going multi-tenant (which also turns on the `tenant_id` enforcement deferred in schema decision D2).

## Links

- Brain dump sections 6 (tech stack), 7 (account system), 8 (security and data model).
- SS-1.9 schema: Group 1 (identity / access) and the security posture section.
- HANDOVER open decision 2.
