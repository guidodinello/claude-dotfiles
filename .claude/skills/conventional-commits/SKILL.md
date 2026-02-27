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

- `rename from/to` → File already physically renamed, needs `git add <new-path>`
- `deleted file` → File already physically deleted, needs `git add <old-path>` or `git rm <old-path>`
- `new file` → File exists, needs `git add <path>`
- `modified` → File exists with changes, needs `git add <path>`

### 2. Command Requirements

**Always include:**
- Staging commands (`git add`, `git rm`) for every commit
- Never use `git mv` - files are already renamed, just stage with `git add`
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
# File already physically renamed in working directory
git add src/new/path/File.php && \
git commit -m "refactor(module): rename File to new location"
```

### Deleted Files

```bash
# File already physically deleted
git rm src/old/File.php && \
git commit -m "refactor(module): remove deprecated File"
```

### New Feature

```bash
# Stage and commit new functionality
git add path/to/file.ts && \
git commit -m "feat(products): add search functionality"
```

### Related Files

```bash
# Stage multiple related files and commit together
git add path/to/file1.ts path/to/file2.ts && \
git commit -m "refactor(components): extract shared utility functions"
```

### Multiple Commits for Different Changes

```bash
# Commit 1: Renames
git add src/new/path/*.ts && \
git commit -m "refactor(structure): reorganize component files"

# Commit 2: New feature
git add src/features/search/*.ts && \
git commit -m "feat(search): implement advanced search filters"

# Commit 3: Test updates
git add tests/features/search/*.test.ts && \
git commit -m "test(search): add tests for advanced filters"

# Commit 4: Documentation
git add README.md docs/search.md && \
git commit -m "docs(search): document new search features"
```

## Output Format

Provide commands as a bash script that can be copied and executed:

```bash
# Reset staged changes (run this first)
git reset

# Commit 1: [Description of logical group]
git add <files> && \
git commit -m "type(scope): description"

# Commit 2: [Description of logical group]
git add <files> && \
git commit -m "type(scope): description"

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
- Files are already physically moved/deleted - just stage them
- All commands assume unstaged working directory
- Group related changes, separate unrelated ones
- Keep commit messages concise and descriptive