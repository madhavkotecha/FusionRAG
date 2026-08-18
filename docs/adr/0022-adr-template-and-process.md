# ADR-0022: ADR Template and Process

- **Status:** Accepted
- **Date:** 2026-03-02
- **Deciders:** Architecture Team

## Context

The project has 21 ADRs spanning foundation decisions (accepted) and research-driven proposals (proposed). As the team grows, we need a standardized template, review process, and maintenance procedures to keep ADRs consistent, discoverable, and actionable.

## Decision

Adopt the following ADR template and governance process for all future architectural decisions.

---

## ADR Template

```markdown
# ADR-NNNN: [Short Decision Title]

- **Status:** Proposed | Accepted | Rejected | Deprecated | Superseded by [ADR-NNNN]
- **Date:** YYYY-MM-DD
- **Deciders:** [names or roles]
- **Supersedes:** [ADR-NNNN] (if applicable)

## Context

[What is the issue that is motivating this decision? What forces are at play?
Include links to related ADRs, issues, or research papers.]

## Decision

[What is the change that we are proposing or have agreed to implement?
Be specific about what will change in the codebase.]

## Consequences

### Positive
- [Benefit 1]
- [Benefit 2]

### Negative
- [Trade-off 1]
- [Trade-off 2]

### Neutral
- [Side effect that is neither positive nor negative]

## Alternatives Considered

### Alternative 1: [Name]
- Description: [Brief description]
- Rejected because: [Reason]

### Alternative 2: [Name]
- Description: [Brief description]
- Rejected because: [Reason]

## Implementation Notes

[Optional: High-level implementation plan, affected services, migration strategy.]

## References

- [Link to research paper, RFC, or external documentation]
- [Link to related issue or PR]
```

---

## ADR Numbering

- Sequential four-digit numbers: `0001`, `0002`, ..., `0022`, ...
- File naming: `docs/adr/NNNN-kebab-case-title.md`
- Never reuse numbers, even for rejected/deprecated ADRs

## Status Lifecycle

```
Proposed → Accepted → Implemented → Deprecated
    ↓                                    ↓
 Rejected                         Superseded by NNNN
```

| Status | Meaning |
|--------|---------|
| **Proposed** | Under discussion, not yet approved |
| **Accepted** | Approved by deciders, ready for implementation |
| **Rejected** | Considered and explicitly not adopted |
| **Deprecated** | Was accepted but is no longer relevant |
| **Superseded** | Replaced by a newer ADR (link to successor) |

## Review Process

### Creating an ADR

1. Author creates a new ADR file using the template above
2. Set status to **Proposed**
3. Open a pull request with the ADR
4. Tag relevant reviewers (minimum 1 architect + 1 implementer)

### Reviewing an ADR

1. Reviewers comment on the PR within **5 business days**
2. Key review criteria:
   - Is the context complete and accurate?
   - Are alternatives genuinely considered (not strawmen)?
   - Are consequences realistic?
   - Is the decision specific enough to implement?
3. After approval, merge the PR and update status to **Accepted**

### Implementing an ADR

1. When implementation begins, no status change needed (remain Accepted)
2. Link implementation PRs to the ADR in commit messages or PR descriptions
3. When implementation is complete, the ADR serves as historical record

### Deprecating an ADR

1. Create a new ADR that supersedes the old one
2. Update the old ADR's status to `Superseded by ADR-NNNN`
3. Update the index in `docs/adr/README.md`

## Maintenance

### Quarterly Review

Every quarter, review the ADR index for:
- **Stale Proposed ADRs** — Accept, reject, or update with new context
- **Implemented ADRs** — Verify implementation matches the decision
- **Accuracy** — Ensure consequences match reality

### Index Management

The `docs/adr/README.md` index must be updated whenever an ADR is added or its status changes. The index groups ADRs by status (Accepted, Proposed, Rejected, Deprecated).

## Consequences

### Positive
- Consistent format makes ADRs easier to read and compare
- Clear review process prevents unilateral architectural decisions
- Status tracking provides visibility into decision pipeline
- Quarterly reviews prevent ADR rot

### Negative
- Process overhead for small decisions (mitigated: only use ADRs for significant architectural choices)
- Review latency may slow urgent decisions (mitigated: 5-day SLA, emergency bypass with post-hoc ADR)

## When to Write an ADR

Write an ADR when the decision:
- Affects multiple services or teams
- Is difficult to reverse once implemented
- Involves significant trade-offs
- Introduces a new technology or pattern
- Changes a previously accepted architectural decision

**Do NOT write an ADR for:**
- Bug fixes
- Library version upgrades (unless major breaking changes)
- Code style or formatting choices
- Single-service internal refactors

## References

- [Michael Nygard's original ADR article](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR GitHub organization](https://adr.github.io/)
