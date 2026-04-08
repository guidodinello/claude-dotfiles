---
name: conventional-commits
description: Generate granular conventional commits from staged changes
disable-model-invocation: false
---

# Conventional Commits Generator

Generate granular, well-structured conventional commits from `git diff --staged` output.

## Usage

Run this skill with the output of `git diff --staged`:

```bash
git diff --staged | claude /conventional-commits
```

Or paste the diff output directly when invoking the skill.

## Important Context

After providing commit commands, you should:

1. Run `git reset` to unstage everything
2. Execute the provided commands in sequence
3. All files will be unstaged in the working directory when commands run

## Analysis Approach

### 1. Determine File States from Diff

- `rename from/to` → File already physically renamed, needs BOTH `git add <new-path>` (new location) AND `git add <old-path>` or `git rm <old-path>` (old location). Missing either half will leave the old file untracked or the deletion unstaged.
- `deleted file` → File already physically deleted, needs `git add <old-path>` or `git rm <old-path>`
- `new file` → File exists, needs `git add <path>`
- `modified` → File exists with changes, needs `git add <path>`

### 2. Command Requirements

**Always include:**

- Staging commands (`git add`, `git rm`) for every commit
- Never use `git mv` - files are already renamed, just stage with `git add`
- Always single-quote paths containing `$` (e.g. TanStack Router dynamic segments like `$labId`) — unquoted `$` gets shell-expanded to empty string, silently breaking the staging command
- Single-line commit messages (no description)
- Chain commands with `&&` so execution stops on failure
- Multiple granular commits (one per logical change)
- Group related files into single commits when they represent one logical change

### 3. Commit Granularity Guidelines

**Group by type:**

- All renames together
- All new features together
- All refactors together
- All bug fixes together

**Keep related changes together:**

- File moves + import updates = single commit
- Component + its tests = single commit
- Feature implementation across related files = single commit

**Separate unrelated changes:**

- Features vs refactors = separate commits
- Backend vs frontend changes = separate commits (unless they're part of same feature)
- Chores vs features = separate commits

### 4. Large-Scale Cross-Cutting Changes

When a single change cascades across many layers (e.g. removing a DB column that touches a migration, model, resource, form request, actions, frontend schemas, API contracts, etc.), **prefer more granular commits even if intermediate states don't compile or pass tests.**

This is intentional — it makes the change easier to review, bisect, and revert layer by layer.

**Order commits from the inside out:**

1. Database (migration)
2. Backend model / schema
3. Backend business logic (actions, services)
4. Backend API surface (form requests, resources, controllers)
5. Frontend contracts (Zod schemas, types, API clients)
6. Frontend UI (components, forms)
7. Tests

**Example — removing a `middle_name` column:**

```bash
# 1. Database
git add database/migrations/xxxx_drop_middle_name.php && git commit -m "feat(database): drop middle_name column from users"

# 2. Model
git add app/Models/User.php && git commit -m "refactor(users): remove middle_name from model"

# 3. Business logic
git add app/Actions/Users/UpdateUserAction.php && git commit -m "refactor(users): remove middle_name from update action"

# 4. API surface
git add app/Http/Resources/UserResource.php app/Http/Requests/UpdateUserRequest.php && git commit -m "refactor(users): remove middle_name from resource and request"

# 5. Frontend contracts
git add resources/js/schemas/user.ts && git commit -m "refactor(users): remove middle_name from Zod schema"

# 6. Frontend UI
git add resources/js/components/UserForm.tsx && git commit -m "refactor(users): remove middle_name from user form"
```

> **Note:** The repo may be in a broken state between these commits. That's acceptable and expected — the goal is clarity of intent per layer, not a green CI at every step.

## Commit Message Format

Use conventional commit format:

```
<type>(<scope>): <description>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `style`: Code style changes (formatting, missing semicolons, etc.)
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build config, etc.)
- `perf`: Performance improvements
- `ci`: CI/CD changes
- `build`: Build system or external dependencies

### Scope

Use the module, component, or area affected:

- `(auth)`: Authentication module
- `(products)`: Products feature
- `(ui)`: UI components
- `(api)`: API layer
- `(database)`: Database changes
- `(config)`: Configuration files

## Examples

### Renamed Files

```bash
# File already physically renamed — stage BOTH the new path and the old deletion
git add src/new/path/File.php && git rm src/old/path/File.php && git commit -m "refactor(module): rename File to new location"
```

### Deleted Files

```bash
# File already physically deleted
git rm src/old/File.php && git commit -m "refactor(module): remove deprecated File"
```

### New Feature

```bash
git add path/to/file.ts && git commit -m "feat(products): add search functionality"
```

### Related Files

```bash
git add path/to/file1.ts path/to/file2.ts && git commit -m "refactor(components): extract shared utility functions"
```

### Multiple Commits for Different Changes

```bash
# Commit 1: Renames
git add src/new/path/*.ts && git commit -m "refactor(structure): reorganize component files"

# Commit 2: New feature
git add src/features/search/*.ts && git commit -m "feat(search): implement advanced search filters"

# Commit 3: Test updates
git add tests/features/search/*.test.ts && git commit -m "test(search): add tests for advanced filters"

# Commit 4: Documentation
git add README.md docs/search.md && git commit -m "docs(search): document new search features"
```

## Output Format

Provide commands as a bash script that can be copied and executed. **Always use single-line commands** — never use `\` line continuations, as they break when pasted into a terminal. Each commit is one line with `&&` chaining:

```bash
# Reset staged changes (run this first)
git reset

# Commit 1: [Description of logical group]
git add <file1> <file2> && git commit -m "type(scope): description"

# Commit 2: [Description of logical group]
git add <file1> <file2> && git commit -m "type(scope): description"

# ... etc
```

## Instructions for Claude

When this skill is invoked:

1. **Analyze the diff** to identify all file changes and their types
2. **Group changes logically** based on the guidelines above
3. **Generate appropriate commit commands** with proper staging
4. **Ensure proper chaining** with `&&` between commands
5. **Use clear, descriptive commit messages** following conventional commit format
6. **Provide context comments** explaining each commit group
7. **Start with `git reset`** instruction to unstage everything
8. **Order commits logically** (refactors before features that depend on them)

Remember:

- Files are already physically moved/deleted — for renames, always stage BOTH sides: the new path (`git add`) and the old path (`git add` or `git rm`). Forgetting the old path leaves a ghost deletion outside the commit.
- All commands assume unstaged working directory
- Group related changes, separate unrelated ones
- Keep commit messages concise and descriptive
