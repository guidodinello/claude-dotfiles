---
name: permissions-audit
description: >
  Performs a comprehensive authorization audit of a project's codebase — analyzing roles, permissions,
  and authorization logic across backend and frontend. Generates three structured Markdown files
  (roles/permissions matrix, permissions usage map, and authorization issues) plus an interactive
  HTML dashboard for navigating findings. Use this skill whenever the user asks to audit permissions,
  analyze authorization, review roles and access control, check for permission gaps or inconsistencies,
  find unprotected endpoints, or any request related to security/authorization review of a codebase.
  Also trigger when the user mentions "permissions audit", "authorization audit", "roles matrix",
  "permission gaps", "unprotected endpoints", "access control review", or shares a project and asks
  about its security posture regarding permissions. This skill works with any backend/frontend stack
  (Laravel, Django, Express, Rails, React, Vue, Angular, etc.).
---

# Permissions Audit Skill

Performs a complete authorization audit of a project and produces both structured Markdown reports and an interactive HTML dashboard.

## Workflow

### Phase 1: Deep Codebase Analysis

Analyze the ENTIRE project (both backend and frontend) focusing on roles, permissions, and authorization logic. Be extremely thorough — do not only look for explicit permission checks. Also detect implicit checks, role conditionals, middleware protections, and missing protections.

#### 1.1 — Identify ALL roles
- Roles in enums, database seeders, config files, constants
- Role hierarchies or inheritance patterns
- Default roles assigned on user creation

#### 1.2 — Identify ALL permissions
- Permissions defined in enums, constants, configs, or databases
- Permissions referenced in authorization checks (guards, middlewares, policies, gates, decorators)
- Permissions implied by conditionals (`if (user.isAdmin)`, `role === 'admin'`, etc.)

#### 1.3 — Map permission usage across layers
For EACH permission found, document:
- **Backend**: endpoints, services, guards/middlewares, policies/gates that check it (with file paths)
- **Frontend**: pages, components, route guards, conditional rendering, hooks that reference it (with file paths)

#### 1.4 — Identify authorization issues
Look for ALL of these issue types:
- **A) Unprotected backend endpoints** — routes with no permission/role check
- **B) Frontend-only protection** — UI hides features but backend doesn't enforce
- **C) Backend ↔ Frontend mismatches** — different permissions checked for same action
- **D) Incorrect permission checks** — too permissive, too restrictive, or wrong role
- **E) Over-privileged access** — endpoints accessible by roles that shouldn't have access
- **F) Dead permissions** — defined but never used anywhere
- **G) Duplicated or inconsistent authorization logic**

For each issue, include: description, file references, why it's a problem, severity (high/medium/low), and suggested fix.

### Phase 2: Generate Markdown Reports

Create three Markdown files:

1. **`ROLES_PERMISSIONS_MATRIX.md`** — Table mapping all roles × all permissions with ✅/❌
2. **`PERMISSIONS_USAGE.md`** — Every permission with its backend + frontend usage (file paths, functions)
3. **`AUTHORIZATION_AUDIT_ISSUES.md`** — Structured list of all issues found, categorized by type and severity

Save these to `/mnt/user-data/outputs/`.

### Phase 3: Generate Interactive HTML Dashboard

Read the HTML template at `assets/permissions-dashboard-template.html` (relative to this skill's directory).

The template is a single-file HTML application with:
- A sidebar navigation with sections for Overview, Permissions (by category), Roles, and Analysis
- A dashboard overview with stats, role breakdowns, category counts, and issue summary
- Expandable permission cards showing backend/frontend usage and role assignments
- A role matrix comparison table
- Dedicated pages for backend gaps, frontend gaps, inconsistencies, and unused permissions
- Dark theme with responsive design

#### How to populate the template

The template contains a `PERMS` JavaScript array and static HTML content that you must replace with the actual audit findings. Specifically:

1. **`PERMS` array** — Replace with the actual permissions found. Each entry has this structure:
```javascript
{
  slug: 'permission.slug.name',        // The permission identifier
  name: 'Human Readable Name',          // Display name
  cat: 'category-key',                  // Category key (e.g., 'statements', 'users', 'billing')
  warn: true/false,                      // Whether this permission has issues
  roles: { role1: true, role2: false },  // Which roles have this permission
  backend: 'Description of backend usage or ⚠️ warning',
  frontend: 'Description of frontend usage or ⚠️ warning',
}
```

2. **Sidebar navigation** — Update nav items to match the actual categories and counts found
3. **Dashboard stats** — Update total permissions, roles count, backend gaps count, inconsistencies count
4. **Overview cards** — Update role bars (permission counts per role), category table, issues summary, key files
5. **Role detail pages** — Update the tables listing permissions per role and missing permissions
6. **Backend gaps section** — Replace with actual unprotected endpoints found (use `.gap-item.sev-high` and `.gap-item.sev-medium` classes)
7. **Frontend gaps section** — Replace with actual frontend issues
8. **Inconsistencies section** — Replace with actual backend ↔ frontend mismatches
9. **Unused permissions section** — Replace with dead permissions
10. **Category pages** — The template auto-generates these from the `PERMS` array via `renderPerms()`, but the sidebar category nav items and `catMap` in `navigate()` need to match actual categories
11. **Role matrix** — Auto-generated from `PERMS` array via `renderMatrix()`, but update `catLabels` to match actual categories

#### Adapting to different role sets

The template example uses 3 roles (Admin, Internal, External). Your project may have different roles. Adapt:
- The `roles` object in each PERMS entry to use actual role keys
- The matrix table headers
- The role detail cards
- The tag badges (A/I/E) in permission cards — use appropriate letters/colors per role
- The overview role bars

#### Category system

Categories are flexible — use whatever grouping makes sense for the project. Common examples:
- By domain: `users`, `billing`, `reports`, `settings`, `content`
- By CRUD: `create`, `read`, `update`, `delete`
- By module: module names from the project

Update the `catMap` in the `navigate()` function and `catLabels` in `renderMatrix()` to match.

### Phase 4: Output

Save the HTML dashboard to `/mnt/user-data/outputs/permissions-audit.html` and present it along with the three Markdown files.

## Notes

- The HTML is a **single self-contained file** — no external dependencies except system fonts
- Prioritize completeness over brevity in the analysis
- The goal is to detect authorization vulnerabilities and inconsistencies
- Works with any tech stack — adapt the analysis approach to the project's framework
- For very large projects, focus on the most critical/sensitive areas first, then expand
