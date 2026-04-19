# Python Project — Agent Code Guidelines

General-purpose guidelines for Python projects where AI agents assist with development.
Copy this file as `CLAUDE.md` at the root of any new project and adapt the
project-specific sections at the bottom.

---

## Philosophy

Python has an explicit design philosophy. When in doubt, run `import this`. The most
load-bearing principles for daily work:

- **Explicit is better than implicit** — no magic, no hidden state, no surprising
  side-effects. If a function does something non-obvious, a name or comment should say so.
- **Simple is better than complex** — the right solution is usually the least code that
  correctly solves the problem, not the most flexible abstraction.
- **Readability counts** — code is read far more often than it is written. Optimise for
  the reader.
- **Errors should never pass silently** — fail loudly and early. Don't swallow exceptions
  or return `None` where an error is the right answer.
- **If the implementation is hard to explain, it's a bad idea** — complexity is a warning
  sign, not a badge of honour.

---

## Software engineering principles

### YAGNI — You Aren't Gonna Need It

Don't add features, abstractions, or configurability for hypothetical future requirements.
Build what the task actually needs. If the requirement arrives later, add it then.

```python
# Bad — parameterised "for future flexibility"
def train(optimizer="adam", scheduler=None, warmup_steps=0, grad_clip=None, ...):
    ...

# Good — add parameters when there's an actual reason to vary them
def train(lr: float = 3e-4) -> None:
    ...
```

### DRY — Don't Repeat Yourself (but don't over-apply it)

Duplicate code is a maintenance hazard. Extract shared logic — but only once you see the
same thing repeated at least three times and are confident the repetition isn't
coincidental. Premature abstraction is worse than duplication.

### KISS — Keep It Simple

Prefer a flat structure over a deep hierarchy. Prefer a function over a class. Prefer a
class over a framework. Each layer of indirection has a cost; make sure it earns it.

Jack Diederich's rule: *if you can't explain what the class does without using the word
"manager", "handler", or "helper" — it probably shouldn't be a class.*

### Single responsibility

Functions and classes should do one thing. If a function's docstring needs the word "and",
consider splitting it. If a class has methods that don't share any state, consider
splitting it into free functions.

### Fail fast

Validate inputs at the boundary (user input, external APIs, file I/O). Inside the system,
trust your own invariants and let unexpected states raise immediately rather than
propagating silently.

```python
# Bad — silently returns wrong results
def divide(a, b):
    if b == 0:
        return 0

# Good — caller learns about the problem immediately
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError(f"divide: b must be non-zero, got {b}")
    return a / b
```

---

## Running the project

```bash
uv pip install -e .          # editable install — do this once on a fresh clone
uv run ruff check .          # lint (must be clean before committing)
uv run ruff check --fix .    # auto-fix what ruff can
uv run pytest tests/ -v      # run test suite (must be green before committing)
pre-commit install           # install git hooks (once per clone)
```

**Never invoke `python3` directly.** Always use `uv run python` (or `uv run <script>`) so
the uv-managed virtual environment and pinned dependencies are used.

```bash
# Good
uv run python scripts/train.py
uv run python -c "import mypackage; print(mypackage.__file__)"

# Bad — bypasses the venv
python3 scripts/train.py
```

---

## Imports

**Never use `sys.path.insert` or `sys.path.append`.**
Install the project as an editable package (`uv pip install -e .`) and use a proper build
backend (`hatchling`, `setuptools`, etc.) so all packages are importable without path
manipulation.

```python
# Good
from mypackage.core import MyClass

# Bad
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import MyClass
```

Import order (enforced by ruff/isort): stdlib → third-party → first-party. Use
**relative imports** inside a package, **absolute imports** across packages.

Don't use `from module import *`. It pollutes the namespace and makes it impossible to
tell where a name came from without reading the source.

---

## Logging

**Never use `print()` for status, progress, or diagnostic output.**
Use the stdlib `logging` module with a two-handler setup (stdout + rotating file).

```python
import logging
import sys
from pathlib import Path

def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    logger.setLevel(logging.INFO)
    return logger
```

Use `%`-style formatting in logger calls — it defers string construction until the
message is actually emitted:

```python
logger.info("processed %d items in %.2fs", count, elapsed)  # good
logger.info(f"processed {count} items in {elapsed:.2f}s")   # bad — always evaluated
```

`print()` is acceptable only for structured output that is the *primary product* of a
script (e.g. a formatted report or table).

---

## Type annotations

Annotate all public functions with parameter types and return types.

```python
# Good
def card_strength(palo: int, numero: int, muestra_palo: int) -> int: ...
def load_checkpoint(path: Path, device: str = "cpu") -> nn.Module: ...

# Bad
def card_strength(palo, numero, muestra_palo): ...
```

Use modern Python 3.10+ syntax — never `Optional`, `List`, `Dict`, `Union`, or `Tuple`
from `typing`:

```python
# Good
def process(items: list[int], mapping: dict[str, int]) -> tuple[int, ...]: ...
def find(value: int | None = None) -> str | None: ...

# Bad
from typing import Optional, List, Dict
def process(items: List[int], mapping: Dict[str, int]) -> Optional[str]: ...
```

---

## Dataclasses and immutability

Use `@dataclass(slots=True)` for all new dataclasses — it catches attribute typos at
class definition time and reduces memory footprint.

Use `@dataclass(frozen=True, slots=True)` for data that is set once and never mutated.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Config:           # immutable — set once and passed around
    lr: float
    seed: int

@dataclass(slots=True)
class TrainingState:    # mutable — updated every step
    step: int
    loss: float
```

Prefer `tuple` over `list` for fields that are never mutated after construction.
Always write full container type hints — never bare `list` or `dict`:

```python
# Good
checkpoints: list[Path]
rewards: dict[str, float]

# Bad
checkpoints: list
rewards: dict
```

---

## Protocols instead of ABCs

Use `typing.Protocol` with `@runtime_checkable` to define structural interfaces.
Concrete classes satisfy the protocol structurally — they do **not** inherit from it.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Agent(Protocol):
    def act(self, obs: np.ndarray) -> int: ...
    def reset(self) -> None: ...
```

```python
class RandomAgent:          # no inheritance — satisfies Agent structurally
    def act(self, obs):
        return random.randint(0, N_ACTIONS - 1)
    def reset(self) -> None:
        pass

assert isinstance(RandomAgent(), Agent)  # True at runtime
```

Use ABCs only when concrete classes genuinely share implementation, not just an interface.

---

## Named constants

Never embed raw magic numbers or strings in logic. Define named constants at module
level, near the code that uses them.

```python
# Good
MAX_RETRIES = 3
LEARNING_RATE = 3e-4
HIDDEN_DIM = 256

model = MLP(hidden_dim=HIDDEN_DIM)

# Bad
model = MLP(hidden_dim=256)
```

Use `Enum` for values that belong to a fixed, named set:

```python
from enum import IntEnum, auto

class Phase(IntEnum):
    BIDDING = auto()
    PLAY = auto()
    DONE = auto()
```

---

## Path handling

**Always use `pathlib.Path` — never bare strings for file paths.**

```python
from pathlib import Path

# Good
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "outputs"
model.save(str(OUTPUT_DIR / f"checkpoint_{step}.pt"))  # str() only at the API boundary

# Bad
output_dir = "/home/user/project/outputs"
path = output_dir + "/" + f"checkpoint_{step}.pt"
```

Use `/` for joining, `.parent` for navigation, `.stem`/`.suffix`/`.name` for
introspection. Convert to `str` only when a third-party API requires it.

---

## Prefer the standard library

**Before writing a utility, check if the stdlib already has it.** Custom implementations
are harder to read, harder to test, and don't benefit from CPython optimisation.
The rule: **stdlib first, third-party second, in-house last.**

### functools — caching and higher-order functions

Never write a manual cache dict when `@cache` works:

```python
# Bad
_cache: dict = {}
def expensive(x: int) -> int:
    if x not in _cache:
        _cache[x] = _compute(x)
    return _cache[x]

# Good
from functools import cache

@cache
def expensive(x: int) -> int:
    return _compute(x)
```

Other tools worth knowing: `partial` (fix some arguments of a function),
`wraps` (preserve metadata in decorators), `reduce` (fold a sequence).

### itertools — iteration without manual loops

```python
from itertools import chain, combinations, takewhile, groupby

# Flatten a list of lists
all_items = list(chain.from_iterable(nested))

# All pairs from a collection
pairs = list(combinations(items, 2))

# Take while condition holds
prefix = list(takewhile(lambda x: x > 0, values))
```

### contextlib — context managers without boilerplate

Use `@contextmanager` instead of a class with `__enter__`/`__exit__` for simple cases:

```python
from contextlib import contextmanager, suppress
import time

@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    yield
    logger.info("%s: %.3fs", label, time.perf_counter() - t0)

with timed("data loading"):
    data = load(path)

# Suppress a specific exception cleanly
with suppress(FileNotFoundError):
    cache_path.unlink()
```

### timeit — micro-benchmarks

Use `timeit` for measuring small snippets rather than wrapping them in manual
`perf_counter` loops:

```python
import timeit

t = timeit.timeit("my_function(x)", setup="from mymodule import my_function; x = 42", number=10_000)
print(f"{t / 10_000 * 1e6:.2f} µs per call")
```

For whole-script profiling: `uv run python -m cProfile -s cumtime script.py`.

---

## Configuration

When a function takes more than ~4 settings parameters, bundle them into a typed
dataclass config object:

```python
@dataclass(slots=True)
class TrainConfig:
    lr: float = 3e-4
    batch_size: int = 256
    total_steps: int = 1_000_000
    seed: int = 42
    checkpoint_dir: Path = Path("checkpoints")

def train(cfg: TrainConfig) -> None:
    logger.info("lr=%s steps=%d seed=%d", cfg.lr, cfg.total_steps, cfg.seed)
    ...
```

Argparse stays at the CLI boundary and populates the config:

```python
def main() -> None:
    args = parser.parse_args()
    cfg = TrainConfig(lr=args.lr, total_steps=args.steps)
    train(cfg)
```

Reach for `pydantic-settings` only when you need config from multiple sources (env vars +
YAML + CLI) with merge priority and validation error messages. For research scripts, a
plain dataclass is simpler and sufficient.

---

## Python idioms

### Underscore conventions

Python uses underscores as a communication tool — use them consistently:

```python
# Throwaway variable — signals "I don't care about this value"
_, important = some_tuple()
for _ in range(3):
    retry()

# Star-unpacking with throwaway — grab first and last, ignore middle
first, *_, last = my_long_tuple

# Numeric literals — use underscores for readability in large numbers
MAX_STEPS = 5_000_000
LEARNING_RATE = 3e-4
BUFFER_SIZE = 1_000_000

# _single_leading: protected by convention (not enforced), signals "internal use"
self._model = None

# __double_leading: triggers name mangling — use only when you explicitly need
# to prevent subclass accidental override. Not a general privacy mechanism.
```

### @property, @staticmethod, @classmethod

Use each for the right reason:

```python
class Agent:
    # @property — attribute-style access for cheap, derived values
    # Never do heavy computation or I/O inside a property
    @property
    def is_trained(self) -> bool:
        return self._model is not None      # fast, pure

    # @staticmethod — logically belongs to the class but needs no instance or class state
    @staticmethod
    def action_space_size() -> int:
        return N_ACTIONS

    # @classmethod — alternative constructors or factory methods that need the class itself
    @classmethod
    def from_checkpoint(cls, path: Path) -> "Agent":
        agent = cls()
        agent._model = load(path)
        return agent

    # Plain method — needs instance state (self)
    def choose_action(self, obs: np.ndarray) -> int:
        return self._model.predict(obs)
```

If a method doesn't use `self` or `cls`, it should be `@staticmethod` (or a free
function if it doesn't conceptually belong to the class).

### Custom decorators

When writing a decorator, always use `functools.wraps` to preserve the wrapped
function's name and docstring:

```python
from functools import wraps
import time

def timed(fn):
    @wraps(fn)          # without this, fn.__name__ becomes "wrapper"
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        logger.info("%s took %.3fs", fn.__name__, time.perf_counter() - t0)
        return result
    return wrapper

@timed
def simulate(n: int) -> dict: ...
```

---

## Code smells to avoid

These patterns are warning signs that the design needs rethinking:

- **Mutable default arguments** — Python evaluates defaults once at import time:
  ```python
  def append(item, lst=[]):  # Bad — lst is shared across all calls
      lst.append(item)
      return lst

  def append(item, lst=None):  # Good
      if lst is None:
          lst = []
      lst.append(item)
      return lst
  ```

- **Boolean flags that select behaviour** — split into two functions instead:
  ```python
  def process(data, verbose=True):  # Bad — two functions in a trenchcoat
      ...

  def process(data): ...        # Good
  def process_verbose(data): ... # Good
  ```

- **Catching generic exceptions** — always catch the specific exception you expect:
  ```python
  try:                          # Bad
      result = load(path)
  except Exception:
      result = None

  try:                          # Good
      result = load(path)
  except FileNotFoundError:
      result = None
  ```

- **Heavy logic in properties** — properties should feel like attribute access; if
  computation is expensive, use an explicit method instead.

- **Deeply nested comprehensions** — if a list comprehension needs more than one `for`
  clause or a non-trivial condition, a regular loop is clearer.

- **Classes with no shared state** — if every method could be a free function, it
  probably should be. (See: Jack Diederich, *Stop Writing Classes*.)

- **Mutable module-level state** — module globals that get mutated are hidden shared
  state. They break encapsulation, make testing hard, and cause subtle bugs across imports.
  Constants (`ALL_CAPS`) are fine; mutable dicts and lists at module scope are not.

- **`assert` for input validation** — `assert` is disabled with `python -O` and must
  never be used for validation. Use `ValueError` or `TypeError` at boundaries:
  ```python
  # Bad — silently skipped in optimised builds
  assert user_id > 0, "user_id must be positive"

  # Good
  if user_id <= 0:
      raise ValueError(f"user_id must be positive, got {user_id}")
  ```

---

## Exception handling

### Raise low, catch high

Lower-level functions should raise specific, descriptive exceptions and let them
propagate. Only catch at system edges — CLI entry points, request handlers, event loop
callbacks — where you have enough context to decide what to do.

```python
# Bad — swallows the error mid-stack, caller can't recover
def load_user(user_id: int) -> User:
    try:
        return db.get(user_id)
    except Exception:
        return None  # caller has no idea what went wrong

# Good — raise specifically, catch at the handler boundary
def load_user(user_id: int) -> User:
    return db.get(user_id)  # let DBError propagate

async def handle_request(user_id: int) -> Response:
    try:
        user = load_user(user_id)
    except DBError as e:
        logger.exception("DB lookup failed for user %d", user_id)
        return Response(500)
```

### Custom domain exceptions

Define a base exception per package so callers can catch your errors specifically
without catching everything:

```python
class AppError(Exception):
    """Base for all application errors."""

class AuthError(AppError):
    """Session expired or token invalid."""

class NotFoundError(AppError):
    """Requested resource does not exist."""
```

Prefer built-in exceptions (`ValueError`, `TypeError`, `FileNotFoundError`) for
generic programming errors. Use custom exceptions for domain concepts.

---

## Async

### Never block the event loop

`time.sleep()`, synchronous HTTP calls, and CPU-bound work stall every other coroutine.
Use async-native alternatives or offload to a thread:

```python
# Bad — blocks the entire event loop
import time
async def wait():
    time.sleep(5)

# Good
import asyncio
async def wait():
    await asyncio.sleep(5)

# Good — offload blocking I/O to a thread pool
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_function, arg)
```

### Store `asyncio.create_task()` results

Tasks not referenced by a variable can be garbage-collected and silently canceled
before they finish. Always keep a reference:

```python
# Bad — task may be GC'd before completion
asyncio.create_task(background_job())

# Good
task = asyncio.create_task(background_job())
# keep `task` alive (store on self, in a set, etc.)
```

### Prefer `asyncio.Queue` for producer-consumer patterns

`asyncio.Queue` decouples producers from consumers cleanly and handles backpressure
without manual coordination:

```python
queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)

async def producer() -> None:
    async for item in source:
        await queue.put(item)

async def consumer() -> None:
    while True:
        item = await queue.get()
        await process(item)
        queue.task_done()
```

---

## Generators

### Generator expressions over list comprehensions

When the caller only iterates the result, pass a generator expression instead of
building a full list in memory:

```python
# Bad — materialises the whole list
total = sum([x * x for x in range(1_000_000)])

# Good — streams one element at a time
total = sum(x * x for x in range(1_000_000))
```

### `yield from` for delegation

Replace manual loops that re-yield from a sub-iterator with `yield from`:

```python
# Bad
def flatten(nested):
    for sublist in nested:
        for item in sublist:
            yield item

# Good
def flatten(nested):
    for sublist in nested:
        yield from sublist
```

---

## Tests

Every non-trivial module needs tests. Minimum coverage:

- **Happy path** — does the function return the right thing for normal input?
- **Edge cases** — empty collections, zero, `None`, boundary values.
- **Invariants** — properties that must always hold (e.g. output shape, value bounds).

```bash
uv run pytest tests/ -v
```

Structure:
```
tests/
  test_core.py       # unit tests for core logic
  test_integration.py  # end-to-end or multi-module tests
```

---

## Linting

ruff is the single linter and formatter. Suggested configuration for `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["SIM108"]  # ternary not always clearer

[tool.ruff.lint.isort]
known-first-party = ["mypackage"]
```

Pre-commit hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

Run `uv run ruff check --fix .` before every commit.
Inline `# noqa` is a last resort — prefer `per-file-ignores` in `pyproject.toml` with a
comment explaining why.

---

## Project-specific notes

*(Replace this section when adapting for a new project.)*

| Item | Value |
|------|-------|
| Python version | 3.13 |
| Package manager | uv |
| Build backend | hatchling |
| Test runner | pytest |
| Linter/formatter | ruff |
