---
paths:
  - "**/*.php"
  - "**/composer.json"
---

<!-- Code examples and table rows can't be rewrapped without breaking them;
     prose is held to 80 columns. This directive travels with the file so it
     lints clean in any repo that vendors it. Claude Code strips block HTML
     comments before injection, so this costs no context. -->
<!-- markdownlint-configure-file {
  "MD013": { "code_blocks": false, "tables": false }
} -->

# PHP Project — Agent Code Guidelines

General-purpose guidelines for PHP projects (Laravel + Pest) where AI agents
assist with development. Import into a project's `CLAUDE.md` with
`@~/.claude/guidelines/php.md`, or copy it in and adapt the project-specific
section at the bottom.

---

## Philosophy

PHP is a strongly-typed language when you make it one. Modern PHP (8.2+) with
strict types, readonly, enums, and first-class callables is expressive and safe
— the runtime only stays honest if the codebase refuses to opt out. The
load-bearing principles:

- **Types are not optional** — every parameter, return, and property is typed.
  `mixed` and untyped code are the exception you justify, not the default you
  inherit.
- **Immutable by default** — a value that never changes after construction can't
  be corrupted from a distance. Reach for mutability only when the domain
  genuinely requires it.
- **Explicit over magic** — Laravel offers a lot of magic; prefer the explicit
  form when the magic hides where behavior comes from. A reader should not have
  to know framework internals to follow the flow.
- **Fail loud, fail early** — validate at the boundary, throw specific
  exceptions, never swallow. A silent wrong answer is worse than a crash.
- **Thin framework layer, rich domain** — controllers and requests translate
  HTTP to domain calls and back. Business rules live in the domain, where they
  can be tested without HTTP.
- **Readability counts** — code is read far more than written. Optimise for the
  next reader, who is usually you in three months.

---

## Software engineering principles

### YAGNI — You Aren't Gonna Need It

Don't add parameters, abstractions, or config for hypothetical future needs.
Build what the task requires; add the rest when a real requirement arrives.

```php
// Bad — parameterised "for future flexibility", every caller passes the defaults
public function send(string $to, ?string $cc = null, ?string $bcc = null, array $headers = [], bool $queue = false): void

// Good — add parameters when there's an actual reason to vary them
public function send(string $to): void
```

### DRY — Don't Repeat Yourself (but don't over-apply it)

Duplicated logic is a maintenance hazard — extract it once you've seen the same
thing three times and are confident the repetition isn't coincidental. Premature
abstraction (a base class two subclasses share, a trait used once) is worse than
a little duplication.

### SSOT — Single Source of Truth

Every constant, schema, or business rule has exactly one authoritative
definition; everything else derives from it. Violations show up as drift — two
places that should agree but don't.

```php
// Bad — the valid statuses are defined twice; the array and the enum can drift
const STATUSES = ['pending', 'confirmed', 'cancelled'];
enum Status: string { case Pending = 'pending'; case Confirmed = 'confirmed'; case Cancelled = 'cancelled'; }

// Good — one definition; derive the rest
enum Status: string
{
    case Pending = 'pending';
    case Confirmed = 'confirmed';
    case Cancelled = 'cancelled';

    /** @return list<string> */
    public static function values(): array
    {
        return array_column(self::cases(), 'value');
    }
}
```

### KISS — Keep It Simple

Prefer a function over a class, a class over a hierarchy, a hierarchy over a
framework abstraction. Each layer of indirection has a cost; make sure it earns
it. If you can't explain what a class does without the words "manager",
"handler", or "helper", it probably shouldn't be a class.

### Single responsibility

A class or method should do one thing. If a method name needs "and", split it.
If a class has methods that share no state, it's probably several things wearing
one name.

```php
// Bad — the name has to say "and", revealing two responsibilities
public function validateAndStoreUser(UserDto $dto): User

// Good — each method has one job and a name that fits it exactly
public function validate(UserDto $dto): void
public function store(UserDto $dto): User
```

### Locality of Behavior

Code that changes together lives together. A reader should understand a behavior
from one place, not by chasing references across the tree.

- Keep a request's validation rules and its `toDto()` in the same request class.
- Keep field-name constants on the request/model that owns them, not a global
  constants file.
- Keep a private rule-check method next to the `execute()` that calls it.

The test: if understanding one behavior needs more than two files open, it has
too much distance.

### Fail fast

Validate inputs at the boundary (form requests, external API responses, file
I/O). Inside the domain, trust your own invariants and let an unexpected state
throw immediately rather than propagate a wrong value.

```php
// Bad — silently coerces a missing relation into a wrong result
public function externalId(Lab $lab): string
{
    return $lab->external_id ?? '';
}

// Good — the caller learns about the problem immediately
public function externalId(Lab $lab): string
{
    return $lab->external_id
        ?? throw new UnprocessableEntityHttpException('Lab has no external id.');
}
```

---

## Language baseline

**Every PHP file starts with `declare(strict_types=1);`.** Without it, PHP
silently coerces `"3"` into `3` and `null` into `""`, defeating the type system
you rely on.

```php
<?php

declare(strict_types=1);

namespace App\Domain\Users;
```

**Prefer `final` classes by default.** Inheritance is the exception, not the
baseline — a `final` class documents "this is not an extension point" and lets
you change internals freely. The one caveat: classes that must be mocked in
tests (see *Service classes* below) cannot be `final`.

**Use constructor property promotion and `readonly`.**

```php
// Bad — verbose, and the properties are mutable
final class AppointmentDto
{
    public string $clinicId;
    public string $doctorId;

    public function __construct(string $clinicId, string $doctorId)
    {
        $this->clinicId = $clinicId;
        $this->doctorId = $doctorId;
    }
}

// Good — promoted, immutable, one line each
final readonly class AppointmentDto
{
    public function __construct(
        public string $clinicId,
        public string $doctorId,
    ) {}
}
```

Follow PSR-12 / the project's formatter (Pint or PHP-CS-Fixer). Don't
hand-format — let the tool own style so diffs stay about behavior.

---

## Type declarations

**Type every parameter, return, and property.** Untyped code is a defect, not a
shortcut.

```php
// Bad
public function total($items) { ... }

// Good
public function total(Collection $items): int { ... }
```

PHP's native types can't express element types, so **use docblock generics for
collections and arrays** — static analysers (PHPStan/Psalm) read them:

```php
/** @param list<AppointmentDto> $appointments */
public function summarize(array $appointments): Summary
/** @return Collection<int, User> */
public function activePatients(): Collection
```

Avoid `mixed`. If a value can be several shapes, model it (a union type, a DTO,
an enum), don't erase it. Make nullability explicit (`?string`, `Foo|null`)
rather than relying on a default of `null` on an untyped property.

---

## Immutability

**Prefer immutable types.** DTOs and value objects are `final readonly`. For
dates, use `CarbonImmutable` — a plain `Carbon` mutates in place, so
`$start->addHour()` silently changes every reference to `$start`.

```php
// Bad — mutates the shared instance; $start is now one hour later everywhere
$end = $start->addHour();

// Good — CarbonImmutable returns a new instance, $start is untouched
public CarbonImmutable $startsAt;
$end = $this->startsAt->addHour();
```

In Eloquent models, cast temporals to immutable variants:

```php
protected $casts = [
    'starts_at' => 'immutable_datetime',
    'date_of_birth' => 'immutable_date',
];
```

---

## Enums

**Use backed enums instead of class constants or magic strings** for a closed
set of values. They give you exhaustiveness, type safety, and a home for related
behavior.

```php
// Bad — stringly-typed, no safety, easy to misspell
if ($appointment->status === 'confirmed') { ... }

// Good
enum AppointmentStatus: string
{
    case Confirmed = 'confirmed';
    case Cancelled = 'cancelled';

    public function isActive(): bool
    {
        return $this === self::Confirmed;
    }
}

if ($appointment->status === AppointmentStatus::Confirmed) { ... }
```

Pass the **case** itself where an API accepts a `BackedEnum` — don't reach for
`->value` unless the signature demands a string. Many framework and package APIs
(route model binding, Spatie roles, validation `Rule::enum`) accept the enum
directly and normalize internally.

---

## Error handling

### Custom domain exceptions

Define exceptions for domain-specific rule violations, extending the framework's
HTTP exceptions (Symfony's `UnprocessableEntityHttpException`,
`NotFoundHttpException`, etc.) so the right status code falls out automatically.
Put them under the owning domain module.

```php
final class AppointmentTooSoonToRescheduleException extends UnprocessableEntityHttpException
{
    public function __construct()
    {
        parent::__construct('Cannot reschedule an appointment that starts within the next 24 hours.');
    }
}
```

### Raise low, catch high

Lower layers throw specific exceptions and let them propagate. Only catch at the
edge — a request handler, a queue worker, a console command — where you have the
context to decide what to do. Never swallow an exception into a `null` or a
default mid-stack.

```php
// Bad — swallows the error, the caller can't tell success from failure
public function find(int $id): ?Lab
{
    try {
        return Lab::findOrFail($id);
    } catch (\Throwable) {
        return null;
    }
}

// Good — let it propagate; the framework's handler renders the right response
public function find(int $id): Lab
{
    return Lab::findOrFail($id);
}
```

Hardcode user-facing messages at the throw site rather than hiding them behind a
constant — the message is part of the contract, and inlining it makes a wrong
message obvious in review.

---

## Named constants / magic values

**No magic strings or numbers.** Give them typed names. For request/response
field names, use typed class constants and reference them via `self::`.

```php
// Bad
if ($age >= 18 && $request->input('country') === 'US') { ... }

// Good
private const int ADULT_AGE = 18;
public const string COUNTRY = 'country';

if ($age >= self::ADULT_AGE && $request->string(self::COUNTRY)->toString() === 'US') { ... }
```

---

## Laravel (DDD)

Organize by domain, not by framework layer. Each domain module splits into a
framework layer (`App/` — Controllers, Requests, Resources, Notifications) and a
business layer (`Domain/` — Actions, DTOs, Models, Enums, Exceptions). The
domain layer never depends on the framework layer, so business rules stay
testable without HTTP.

### Single-action controllers

Controllers are invocable `final readonly` classes with one job: translate the
request to a domain call and the result to a response. They **delegate all logic
to an action** and **all field extraction to the request** via
`$request->toDto()`.

```php
// Bad — validation and business logic leak into the controller
public function store(Request $request): JsonResponse
{
    $data = $request->validate([...]);
    $appointment = Appointment::create([...]);       // logic in the controller
    return response()->json($appointment);
}

// Good — delegate to request (extraction) and action (logic)
final readonly class StoreAppointmentController
{
    public function __invoke(StoreAppointmentRequest $request, StoreAppointmentAction $action): JsonResponse
    {
        $appointment = $action->execute($request->toDto());

        return AppointmentResource::make($appointment)->response()->setStatusCode(201);
    }
}
```

Controllers **always return `JsonResponse`, never a `JsonResource` directly** —
call `->response()` on the resource to convert it. Never extract fields from the
request in the controller (`$request->string(...)`); that belongs in `toDto()`.

Inject everything — the request, the action, and route bindings — into
`__invoke`, not the constructor. Use the container attributes to pull the
authenticated user and named route params instead of reaching for
`$request->user()` or matching argument names:

```php
public function __invoke(
    #[CurrentUser] User $user,
    #[RouteParameter('lab')] Lab $lab,   // binds {lab} even though the var isn't named $lab implicitly
    UpdateLabAction $action,
): JsonResponse
```

Match the return shape to the result:

| Result | Return | Status |
| -------- | -------- | -------- |
| Single entity | `Resource::make($x)->response()` | 200 |
| Collection / paginated | `Resource::collection($x)->response()` | 200 |
| Mutation, no body | `response()->noContent()` | 204 |
| Created entity | `Resource::make($x)->response()->setStatusCode(201)` | 201 |
| File download | `response()->streamDownload(...)` | 200 |

### Domain actions

Business logic lives in actions, not controllers. An action accepts a DTO (or a
model) and returns a domain object. Keep `execute()` high-level and declarative
— extract each business rule check into a private method with a descriptive name
so the flow reads like prose.

```php
// Bad — the rule is inlined; the reader has to decode the condition
public function execute(Lab $lab, string $bookingKey): AppointmentDto
{
    $appointment = $this->scheduler->get($lab->external_id);
    if ($appointment->startAt !== null
        && $appointment->startAt->lessThanOrEqualTo(CarbonImmutable::now()->addHours(24))) {
        throw new UnprocessableEntityHttpException('Cannot reschedule...');
    }
    return $this->scheduler->reschedule($lab, $bookingKey);
}

// Good — execute() reads top-to-bottom; the rule has a name
public function execute(Lab $lab, string $bookingKey): AppointmentDto
{
    if (! $this->canReschedule($lab)) {
        throw new AppointmentTooSoonToRescheduleException();
    }

    return $this->scheduler->reschedule($lab, $bookingKey);
}

private function canReschedule(Lab $lab): bool
{
    $appointment = $this->scheduler->get($lab->external_id);

    return $appointment->startAt === null
        || $appointment->startAt->greaterThan(CarbonImmutable::now()->addHours(24));
}
```

Inject every collaborator through the constructor — **never service-locate**
with `app()` or `resolve()` inside an action. Actions compose: an orchestrating
action injects the smaller actions it needs and calls their `execute()`, rather
than duplicating their logic.

```php
final readonly class SignupAction
{
    public function __construct(
        private CreatePatientAction $createPatient,
        private ChargeAction $charge,
    ) {}

    public function execute(SignupDto $dto): Patient
    {
        $patient = $this->createPatient->execute($dto->patient);
        $this->charge->execute($patient, $dto->payment);

        return $patient;
    }
}
```

When an action performs several writes, wrap them in `DB::transaction(...)` so a
mid-sequence failure can't leave half-written state. Keep the boundary at the
orchestrating action (or the controller) and be consistent about where it lives.

### DTOs

DTOs are `final readonly`, built with named arguments — no named constructors
(`fromArray()`) needed. Put optional params last with a `null` default, type
collections via docblock generics rather than bare arrays, and mark secrets with
`#[SensitiveParameter]` so they're redacted from stack traces and logs.

```php
final readonly class SignupDto
{
    /** @param Collection<int, AddressDto> $addresses */
    public function __construct(
        public string $email,
        #[SensitiveParameter] public string $password,
        public Collection $addresses,
        public ?string $referralCode = null,
    ) {}
}
```

### Request classes & DTOs

Every form request declares a `toDto()` method; the controller only ever calls
that. Use typed constants for field names and reference them in both `rules()`
and `toDto()`.

```php
final class StoreAppointmentRequest extends FormRequest
{
    public const string CLINIC_ID = 'clinic_id';
    public const string DOCTOR_ID = 'doctor_id';

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            self::CLINIC_ID => ['required', 'integer', 'exists:clinics,id'],
            self::DOCTOR_ID => ['required', 'integer', 'exists:doctors,id'],
        ];
    }

    public function toDto(): AppointmentDto
    {
        return new AppointmentDto(
            clinicId: $this->integer(self::CLINIC_ID),
            doctorId: $this->integer(self::DOCTOR_ID),
        );
    }
}
```

For array and nested payloads, compose child keys from the parent constant so
each dotted path is defined exactly once:

```php
public const string ADDRESS = 'address';
public const string ADDRESS_STREET = self::ADDRESS . '.street';   // 'address.street'
public const string ANSWERS = 'answers';
public const string ANSWER_VALUES = self::ANSWERS . '.*.value';   // wildcard array depth
```

Validate enum fields with `Rule::enum(...)`, and override its message through
the rule's class-name key (concatenate the imported `Enum::class`):

```php
self::GENDER => ['required', Rule::enum(Gender::class)],
// in messages():
self::GENDER . '.' . Enum::class => 'Gender must be one of ' . implode(', ', Gender::values()) . '.',
```

**Don't add a base FormRequest class, and don't put `authorize()` in the
request** — authorization belongs at the route (see *Authorization*). Share
behavior by composing traits: expose each rule fragment as a `xxxRules()` method
and spread the fragments into `rules()`.

```php
trait HasPagination
{
    public const string PER_PAGE = 'per_page';

    /** @return array<string, mixed> */
    public function paginationRules(): array
    {
        return [self::PER_PAGE => ['integer', 'gte:1', 'lte:100']];
    }
}

// in a request — merge fragments with the spread operator
public function rules(): array
{
    return [...$this->paginationRules(), self::STATUS => ['required', Rule::enum(Status::class)]];
}
```

### Custom validation rules

Encapsulate non-trivial or DB-backed validation in a rule class implementing
`Illuminate\Contracts\Validation\ValidationRule` (the modern
`validate($attribute, $value, Closure $fail)` signature). Make it `final`,
`readonly` where it holds no state, and **return early after the first
`$fail()`** rather than accumulating errors.

```php
final readonly class ValidProducts implements ValidationRule
{
    public function validate(string $attribute, mixed $value, Closure $fail): void
    {
        if (! is_array($value)) {
            $fail('The :attribute must be a list of ids.');

            return;
        }

        $enabled = Product::query()->whereIn('id', $value)->enabled()->count();
        if ($enabled !== count($value)) {
            $fail('One or more products are unavailable.');
        }
    }
}
```

### Service classes

Service classes that wrap external systems (payment gateways, third-party APIs)
must **not** be `final` or class-level `readonly` — that prevents Mockery from
mocking them in tests. Put the immutability on the constructor params instead.

```php
// Bad — final readonly can't be mocked
final readonly class SchedulingService
{
    public function __construct(private SchedulingApiConnector $connector) {}
}

// Good — mockable, params still immutable
class SchedulingService
{
    public function __construct(
        private readonly SchedulingApiConnector $connector,
    ) {}
}
```

### API resources

Resources use `@mixin` to type the wrapped model/DTO, so properties are accessed
directly as `$this->prop`. Two rules keep them safe:

**Never emit a Carbon instance directly** — always serialize explicitly, with
`?->` for nullable fields:

```php
'starts_at' => $this->startsAt->toIso8601String(),   // datetime
'date_of_birth' => $this->dateOfBirth?->toDateString(), // nullable date
```

**Gate everything that isn't a direct table column**, or you invite
`MissingAttributeException` and N+1 queries:

```php
/** @mixin Product */
final class ProductResource extends JsonResource
{
    /** @return array<string, mixed> */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,                                                    // column — always safe
            'category' => CategoryResource::make($this->whenLoaded('category')),  // relation — gated
            'reviews_count' => $this->whenCounted('reviews'),                     // count — gated
            'reviews_avg' => $this->whenAggregated('reviews', 'rating', 'avg'),   // aggregate — gated
        ];
    }
}
```

### Routes

Define routes **without explicit `->name()`**. Group by prefix, and when several
routes share a policy, apply `->can()` at the group level instead of per-route.

```php
// Bad — per-route names and repeated authorization
Route::get('/{lab}', GetLabController::class)->name('labs.show')->can('view', 'lab');
Route::post('/{lab}/share', ShareLabController::class)->name('labs.share')->can('view', 'lab');

// Good
Route::prefix('/{lab}')
    ->whereNumber('lab')
    ->can(LabPolicy::VIEW, 'lab')
    ->group(static function (): void {
        Route::get('/', GetLabController::class);
        Route::post('/share', ShareLabController::class);
    });
```

### Authorization

Authorize at the route with `->can(Policy::CONST, 'param')` (see *Routes*),
never in the controller or the form request. Policies are `final readonly` and
expose action constants so the route and policy can't drift.

**Mask a failed authorization as 404, not 403.** A `403` confirms the resource
exists, leaking information across tenants. Have the policy throw
`ModelNotFoundException` instead of returning `false`:

```php
final readonly class LabPolicy
{
    public const string VIEW = 'view';

    public function view(User $user, Lab $lab): bool
    {
        return $this->throwUnlessOwned($lab->user_id === $user->id);
    }

    private function throwUnlessOwned(bool $owned): true
    {
        return $owned ?: throw new ModelNotFoundException();
    }
}
```

### Eloquent / models

Models are `final`, guard only the primary key (`$guarded = ['id']` — never
`$fillable`), and cast deliberately: `immutable_datetime`/`immutable_date` for
temporals (never plain `datetime`), enums cast directly (`'status' =>
Status::class`), and `'password' => 'hashed'`. Keep factories in
`database/factories/`, never a `newFactory()` on the model. In migrations, write
explicit `created_at`/`updated_at` timestamps rather than `$table->timestamps()`
(the shorthand makes them nullable).

Annotate every relationship with a generic return docblock, use the `#[Scope]`
attribute (not the legacy `scopeX` method name), and express derived attributes
with `Attribute::make()` (not `getXAttribute`):

```php
/** @return BelongsTo<Clinic, $this> */
public function clinic(): BelongsTo
{
    return $this->belongsTo(Clinic::class);
}

#[Scope]
protected function active(Builder $query): void
{
    $query->where('status', Status::Active);
}

/** @return Attribute<string, string> */
protected function email(): Attribute
{
    return Attribute::make(set: fn (string $value): string => strtolower($value));
}
```

### Framework hardening

Set global safety guarantees once in `AppServiceProvider::boot()` — each turns a
whole class of silent bug into a loud failure:

```php
Model::shouldBeStrict(! $this->app->isProduction());          // lazy-load / missing-attribute throws off-prod
DB::prohibitDestructiveCommands($this->app->isProduction());  // no accidental prod wipe
Password::defaults(fn () => Password::min(8)->mixedCase()->numbers()->symbols()->uncompromised());
Relation::enforceMorphMap(['lab' => Lab::class, 'user' => User::class]); // stable morph aliases, not FQCNs
```

Reference the shared password policy in requests as `Password::default()` so the
rule has a single definition.

---

## Testing (Pest)

### Structure

Group tests with `describe`/`it`, reference the controller under test in a
docblock, and lean on the base `TestCase` + `RefreshDatabase` wired in
`Pest.php`. Arrange, act, assert. Apply `RefreshDatabase` to both the Feature
and Unit suites — a class-focused "unit" test that builds its state through
factories still needs a database.

```php
<?php

declare(strict_types=1);

use App\Appointments\App\Controllers\StoreAppointmentController;

describe('store appointment', function (): void {
    /** @see StoreAppointmentController */
    it('creates an appointment', function (): void {
        $data = StoreAppointmentRequestFactory::new()->create();

        $response = actingAs(patient())->postJson(url('/api/appointments'), $data);

        $response->assertCreated();
        assertDatabaseHas('appointments', ['clinic_id' => $data['clinic_id']]);
    });
});
```

### Datasets

Extract shared fixtures into named datasets under `tests/Datasets/` and bind
them so every test gets a fresh instance. Use named-key datasets for validation
matrices so a failure names the case.

```php
// tests/Datasets/user.php
dataset('user', [fn () => UserFactory::new()->createOne()]);

// in a test file — every it() receives a fresh User
beforeEach()->with('user');
it('does something', function (User $user): void { /* ... */ });

// named-key matrix — the failing case is self-describing in the output
it('rejects weak passwords', function (string $password): void { /* ... */ })
    ->with(['too short' => ['short'], 'no numbers' => ['NoNumbers!']]);
```

### RequestFactories

Generate API payloads with a `RequestFactory` whose `definition()` returns a
**valid** default — create real related records rather than hardcoding foreign
keys to `1`, so any test that doesn't override them still passes.

### Model factories

**Prefer `createOne` / `createMany` over `create`.** `create()` returns
`Collection<TModel>|TModel` — a union the analyser can't narrow — while
`createOne(): TModel` and `createMany(): Collection<TModel>` are specific, so
you get real inference and type safety.

```php
// Bad — return type is a union; no inference on $user
$user = UserFactory::new()->create();

// Good — $user is definitely a User
$user = UserFactory::new()->createOne();
```

**`for{Relation}()` methods are free** — the base `Factory::__call` resolves
them via magic when the model defines the relation and the related model has a
factory. You do **not** define them.

```php
// Both work with no factory changes, because Appointment has user()/doctor()/clinic() relations
AppointmentFactory::new()->forUser($user)->forDoctor($doctor)->forClinic($clinic)->createOne();
```

**Add explicit state methods only for deviations** from `definition()`. Method
names that don't start with `for`/`has` are *not* magic — they must be defined
or they throw. For post-persist setup that isn't a column (assigning a role,
attaching pivots), use `afterCreating()`, not state:

```php
// A role is not a column — factory state can't set it; afterCreating can
public function patient(): static
{
    return $this->afterCreating(fn (User $user) => $user->assignRole(RoleEnum::Patient));
}
// then:
UserFactory::new()->patient()->createOne();
```

**Override precedence: pass per-call overrides to `createOne([...])`, not
`new([...])`.** State resolves in the order it was pushed, last writer wins —
`definition()` < `new()` < chained states < `createOne()`. Overrides in `new()`
can be clobbered by a later chained state; overrides in `createOne()` always
win.

```php
// Bad — a later ->confirmed() could overwrite a status you set here
AppointmentFactory::new(['status' => $status])->confirmed()->createOne();

// Good — the caller's overrides are the final word
AppointmentFactory::new()->confirmed()->createOne(['status' => $status]);
```

### Assertions

**Assert meaningful values, not trivially-true ones.** An assertion that passes
regardless of a bug is worse than none — it reads as coverage while verifying
nothing.

```php
// Bad — passes for literally any id; proves nothing about ownership
->assertJsonPath('data.0.id', fn (int $id): bool => $id > 0);

// Good — proves the returned record is the expected one
->assertJsonPath('data.0.id', $appointment->id);
```

**Hardcode expected error messages** in assertions — don't reference the
exception's constant. The test should break loudly if someone changes the
user-facing message.

**For pagination, assert the envelope schema, not a volume-dependent page
count.** Creating 20 rows just to force `last_page >= 2` silently couples the
test to the page size. Pagination is framework behavior — assert the *shape*;
one record is enough.

```php
// Bad — depends on the default page size being < 20
AppointmentFactory::new()->forUser($patient)->createMany(20);
$response->assertJsonPath('meta.last_page', fn (int $v): bool => $v >= 2);

// Good — asserts the response is shaped as a paginated payload
AppointmentFactory::new()->forUser($patient)->createOne();
$response->assertJsonStructure([
    'data',
    'links' => ['first', 'last', 'prev', 'next'],
    'meta' => ['current_page', 'from', 'last_page', 'path', 'per_page', 'to', 'total'],
]);
```

### Authorization & ownership

Cover every owned resource with three tests: unauthenticated (401),
authenticated-but-missing (404), and authenticated-but-owned-by-someone-else
(**404, not 403** — matching the policy's existence masking).

```php
it('is not found for another users resource', function (): void {
    $appointment = AppointmentFactory::new()->forUser(anotherUser())->createOne();

    actingAs(user())
        ->getJson(url("/api/appointments/{$appointment->id}"))
        ->assertNotFound();
});
```

### Global test functions

`postJson`, `getJson`, `actingAs`, `assertDatabaseHas`, and friends are Pest
globals — call them bare. Don't FQCN (`\Pest\Laravel\postJson(...)`) or add
per-file `use function` imports for them.

### Mocking services

Prefer a typed mock helper (a small function in `Pest.php` that returns the mock
through the container) over `$this->mock()` / `test()->mock()` inside a test
closure — static analysers at a high level can't resolve the latter through
Pest's closure binding.

For SDK-based integrations, use the SDK's own test double (e.g. Saloon's
`MockClient` / `MockResponse`) rather than `Http::fake()`, which only intercepts
calls made through the `Http` facade.

### Controlling time

Freeze time for anything date-dependent with `CarbonImmutable::setTestNow()` in
`beforeEach`, and clear it in `afterEach` so it can't leak into other tests:

```php
beforeEach(fn () => CarbonImmutable::setTestNow('2025-01-01 12:00:00'));
afterEach(fn () => CarbonImmutable::setTestNow());
```

### Notifications

Fake in `beforeEach`, assert on the recipient:

```php
beforeEach(fn () => Notification::fake());

it('notifies the patient on creation', function (): void {
    // ... create appointment ...
    Notification::assertSentTo($patient, AppointmentCreatedNotification::class);
});
```

---

## Code smells to avoid

These are warning signs that the design needs rethinking:

- **Logic in controllers** — a controller doing more than "call action, return
  response" is hiding a missing action.
- **Fields extracted in the controller** — `$request->string('x')` outside
  `toDto()`. The DTO is the boundary; keep extraction there.
- **Carbon in resources** — returning a `Carbon`/`CarbonImmutable` straight from
  `toArray()` ships a non-deterministic format. Always `->toIso8601String()` /
  `->toDateString()`.
- **`create()` for a single model** — use `createOne()` for the narrower return
  type.
- **Trivially-true assertions** — `fn ($id) => $id > 0`, `assertStatus(200)`
  with no body check.
- **Magic strings / numbers** — un-named literals in conditions and array keys.
- **`mixed` and untyped signatures** — erasing a type instead of modelling it.
- **Swallowed exceptions** — `catch (\Throwable) { return null; }` mid-stack.
- **`final readonly` on a service that gets mocked** — breaks Mockery; move
  immutability to constructor params.
- **Ungated relations in resources** — accessing `$this->relation` instead of
  `$this->whenLoaded('relation')` invites N+1s and `MissingAttributeException`.
- **`$table->timestamps()` in migrations** — creates nullable timestamp columns;
  declare them explicitly.
- **Service location inside an action** — `app(Foo::class)` / `resolve(...)`.
  Inject through the constructor so the dependency is visible and mockable.
- **`authorize()` in a form request, or an ownership check in the controller** —
  authorize at the route with a policy instead.
- **A policy that returns `false`** for an ownership failure — returns 403 and
  leaks that the resource exists; throw `ModelNotFoundException` to mask as 404.
- **Multiple writes with no transaction** — an action that does several writes
  without `DB::transaction(...)` can leave half-written state on failure.

---

## Static analysis & style

- **PHPStan or Psalm at a high level** (PHPStan level 9–10) — this is what makes
  the docblock generics and typed signatures pay off. Run it in CI; a red
  analyser blocks merge.
- **Pint or PHP-CS-Fixer** owns formatting — never hand-format.
- **Rector** for automated upgrades and modernization, run deliberately (not on
  every save).
- Run the project's aggregate quality command (often `composer fixer` /
  `composer test`) before every commit; the suite must be green.

---

## Project-specific notes

Replace this section when adapting these guidelines for a new project.

| Item | Value |
| ------ | ------- |
| PHP version | 8.4 |
| Package manager | Composer |
| Framework | Laravel 12 |
| Test runner | Pest |
| Style | Pint |
| Static analysis | PHPStan (level 10) |
