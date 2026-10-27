# OMOP Mapping Review — Access, in Plain Terms

A short answer to three questions: do we need new user groups, how do people get
access, and what can each group do.

---

## 1. Should we create and manage new user groups?

**Yes — a small set (four), managed where you already manage company access
(your identity provider, e.g. Entra/Okta), not by hand in Databricks.**

Why groups instead of naming individuals:
- **Onboarding/offboarding is automatic** — add or remove a person from a group
  and their access follows. Nothing to clean up in the tool.
- **Least privilege & audit** — each group gets exactly the access its job needs,
  and access is easy to review.
- **Low overhead** — four groups, set up once.

| Group | Who's in it | In one sentence |
|---|---|---|
| **Reviewers** | Researchers / clinical SMEs | Look at codes that need attention and propose the right meaning |
| **Approvers** | Data governance / stewards | Sign off on what reviewers propose |
| **Curators** | Data engineering team | Maintain the data and publish approved decisions |
| **Admins** | Platform owners | Manage the application and who can use it |

*(Reviewers can optionally be split by clinical area — e.g. conditions, drugs,
procedures — so each person only sees their own area. Worth doing later if the
reviewer pool is large; not required to start.)*

---

## 2. How do people get access?

Two simple steps, both one-time per group:

1. **Identity team adds the person to a group** (Reviewers or Approvers) in the
   identity provider — the same process used for any other system.
2. **The group is allowed to open the app**, once.

That's it for the vast majority of users. They don't get individual database
logins or any manual setup — **the application does the data work on everyone's
behalf**, securely, under a single managed service account.

The Curators and Admins teams get a bit more (to maintain the data and the app),
which is a separate, one-time setup.

---

## 3. What access does each group actually get?

| Group | Can do | Can see | Cannot do |
|---|---|---|---|
| **Reviewers** | Open the app; propose a mapping for each code | The list of codes needing attention (summarized counts only) and the approved-term picker | See patient-identifiable data; approve anything |
| **Approvers** | Open the app; approve, reject, or return proposals | The same lists, plus the proposals submitted | Approve a code they reviewed themselves (enforced) |
| **Curators** | Maintain the data; publish approved mappings back to the data | Full data set (their job) | Manage who has access |
| **Admins** | Manage the app and group access | Configuration | — |

**Privacy, stated plainly:** no one in the Reviewer or Approver groups ever sees
patient-level records. They work from **summarized lists of codes** (small groups
are hidden), never individual patient data. The clinical detail stays restricted
to the data-engineering team that needs it.

**Accountability:** every proposal and approval is recorded with the person's
name and time, and the system **prevents anyone from approving their own work** —
so there's always a second set of eyes.

---

### Bottom line
Create **four role-based groups**, managed in your identity provider. Most people
simply get added to *Reviewers* or *Approvers* and are allowed to open the app —
no individual data access to provision. Each group is limited to what its role
needs, no one in the review process sees patient data, and every decision is
attributed and independently approved.
