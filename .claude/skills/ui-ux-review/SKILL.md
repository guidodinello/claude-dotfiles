---
name: ui-ux-review
allowed-tools: Bash Read Grep Glob Agent
description: >
  Evaluate UI/UX quality across the frontend — flow, visual consistency, layout,
  copy, and interaction design — from a screenshot, screen recording, or component
  path. Produces a structured report with severity ratings and code-level
  remediation suggestions. Use during feature implementation, before PR review,
  or as a periodic design audit. Does NOT modify code — findings only.
---

## Goal

Catch UX defects that linters and typecheckers can't: dead-end flows, missing
loading/empty/error states, inconsistent design tokens, unreadable copy, and
interaction patterns that violate established human-factors heuristics (Appendix
A). A well-calibrated run on a healthy screen produces few or no blocker/high
findings — don't manufacture severity to fill out a report.

This skill is frontend-agnostic. Most heuristics apply to any UI (web or mobile);
a few (thumb zones, bottom sheets, safe-area insets, gesture conventions) are
mobile-specific and should be skipped when reviewing `frontend/web/`.

## Invocation

Accepts one of:
- **A screenshot or screen recording path** — read it directly (Read supports
  images; for a recording, ask the user for representative frame(s) or extract
  them with `ffmpeg -i <recording> -vf fps=1 frame_%03d.png` into the scratchpad
  directory).
- **A component/screen file path or directory** — read the source directly. If
  the `run` skill is available and the app is easy to launch, prefer driving the
  real screen and screenshotting it over reading JSX alone — static analysis
  misses runtime-only defects (missing loading state on a real fetch, layout
  overflow with real data).
- **Nothing specific** — ask the user which screen(s) or flow to review.

---

## Step 1 — Scope the review

Identify:
- Which screen(s)/component(s) are in scope, and whether this is web or mobile
  (skip mobile-only heuristics for web).
- Whether this is a **quick check** (single component, e.g. during feature
  review) or a **full audit** (periodic sweep across a flow or the whole app).

For a full audit across many screens, spawn parallel Explore or general-purpose
agents — one per screen/flow — each given the relevant heuristics from Appendix A
and asked to return findings in the Report Format below. For a quick check on one
component, review it directly without spawning agents.

## Step 2 — Apply heuristics in priority order

Work through Appendix A using the **Quick audit ordering checklist** (end of
appendix) rather than UH1→UH35 in sequence — it front-loads the highest-signal,
cheapest-to-verify checks first (state coverage, tap targets, safe areas,
keyboard handling, button/error copy) so a time-boxed review still catches the
defects that matter most.

For each heuristic, only flag what you can point to concretely — a specific
file:line, screenshot region, or missing state branch. Skip heuristics whose
"signal strength" is Weak/Medium unless you have the context (domain knowledge,
full flow visibility) that heuristic's "what to look for" section calls for.

## Step 3 — Rate severity

Map findings to severity, not just heuristic priority — a UH1 (state visibility)
violation on a rarely-used settings row is a `low`, while the same violation on
the primary checkout button is a `blocker`:

- **blocker** — breaks the task (dead end, crash-equivalent, data loss risk,
  inaccessible primary action)
- **high** — works but actively misleads or frustrates users on a common path
- **medium** — noticeable friction or inconsistency, not on the critical path
- **low** — polish issue, minor inconsistency
- **nit** — cosmetic, purely stylistic

## Step 4 — Report

Do not silently drop low-signal items — list them under `nit`/`low` rather than
omitting them, but keep the top of the report focused on `blocker`/`high` so it's
actionable at a glance.

### Report format

```
## UI/UX Review — <screen/flow name>

### Blocker
- [UH#] <file:line or screenshot region> — <what's wrong> → <fix>

### High
- ...

### Medium
- ...

### Low / Nit
- ...

<N> findings across <M> heuristics checked. Skipped: <heuristics not applicable
and why, e.g. "mobile-only, this is a web screen">.
```

If no findings survive Step 3, report `No UX issues found` plus a one-line note
on what was checked (don't leave the reviewer guessing what was covered).

---

## Appendix A: Design Heuristics

Each heuristic maps a cognitive/HCI principle to concrete code-level signals,
grouped by what to look for, why it matters, and what to replace it with.
Priority reflects how often a violation meaningfully hurts users; signal
strength reflects how reliably it can be spotted from code/screenshots alone
(Strong = safe to flag confidently; Weak = requires domain context, be
conservative).

### UH1 — Visibility of system status

Keep users informed about what is going on through appropriate feedback within reasonable time.

**What to look for:** Actions with no visual response within 100ms (no press state, no skeleton, no spinner). Screens that appear to freeze during data fetches. Async operations that don't show progress. Pull-to-refresh that doesn't show a loading indicator.

**Why it matters:** Without feedback, users perceive the app as broken or unresponsive. The 100ms threshold is the limit for perceived instantaneous response — beyond that, users enter a wait state. Unacknowledged waits increase perceived effort and abandonment.

**What to replace with:**
```tsx
// Before: button goes dead, user taps repeatedly
<Pressable onPress={handleSubmit}>
  <Text>Save</Text>
</Pressable>

// After: loading state disables and shows spinner
<Pressable onPress={handleSubmit} disabled={isLoading}>
  {isLoading ? <ActivityIndicator color="#fff" /> : <Text>Save</Text>}
</Pressable>
```

- List screens: use skeleton placeholders (not spinners) — they set expectation of content shape
- Mutations: show inline loading state on the triggered button, not a full-screen overlay
- Pull-to-refresh: must show RefreshControl indicator; never swallow the gesture

**Signal strength:** Strong — absence of loading feedback is one of the most reliably detectable UX defects.
**Priority:** High

### UH2 — Match between system and real world

Speak the user's language, not system-oriented terms. Follow real-world conventions and mental models.

**What to look for:** Technical jargon in UI labels ("POST failed", "500 Internal Server", "401 Unauthorized"). Icons that conflict with real-world meaning. Date/time formats that don't match locale. Filters or categories that use internal taxonomy instead of user vocabulary.

**Why it matters:** Users build mental models from prior experience. Every mismatch forces conscious decoding, which increases cognitive load and slows task completion. System-oriented language makes errors inscrutable — "Error 403" means nothing to an end user.

**What to replace with:**
```tsx
// Before
<Text>Error 403: Forbidden</Text>

// After
<Text>You don't have permission to view this page.</Text>
<Button title="Contact your admin" onPress={handleContact} />

// Before: internal category name
<CategoryChip label="T-SHIRT_CATEGORY_03" />

// After: user-facing label
<CategoryChip label="Casual Tees" />
```

- Audit every visible string against an end-user readability check
- Use the design system's category/tag vocabulary, not the DB enum names
- Platform-native patterns (iOS bottom tab, Android nav drawer) should follow each platform's convention

**Signal strength:** Strong — jargon and error-code leaks are directly observable in source code.
**Priority:** High

### UH3 — User control and freedom

Users often perform actions by mistake. Provide a clearly marked "emergency exit" without extended dialogs.

**What to look for:** Destructive actions without undo or confirmation. No back button on modal screens. Swipe-to-delete without undo snackbar. No cancel on multi-step flows. Forms that discard input on navigation away.

**Why it matters:** Error recovery is a core usability need — mistakes are inevitable. When users can't undo, anxiety increases and exploration decreases.

**What to replace with:**
```tsx
// Before: swipe-to-delete, item disappears forever
<Swipeable onSwipeRight={() => deleteItem(item.id)}>
  <ListItem {...item} />
</Swipeable>

// After: swipe-to-delete with undo snackbar
<Swipeable onSwipeRight={() => confirmDelete(item)}>
  <ListItem {...item} />
</Swipeable>
```

- All destructive actions need either confirmation dialog or undo window (minimum 4s snackbar)
- Modal presentations must have a visible close/dismiss control (X, Cancel, or swipe-down grabber)
- Multi-step forms must preserve draft on navigate-away

**Signal strength:** Strong — missing undo/back on destructive actions is always a real usability defect.
**Priority:** High

### UH4 — Consistency and standards

Users should not have to wonder whether different words, situations, or actions mean the same thing. Follow platform conventions.

**What to look for:** Mismatched design tokens (two shades of primary blue, three border radii). Inconsistent button styles for the same action type. Different labels for the same action ("Save" vs "Update" vs "Submit"). Platform convention violations. Custom UI that reimplements native controls poorly.

**Why it matters:** Consistency reduces learning cost. Every inconsistency forces the user to re-evaluate what an element does. Jakob's Law: users spend most of their time on *other* apps, so deviation from platform norms costs trust.

**What to replace with:**
```tsx
// Before: three different patterns for the same action
<Button title="Save" />
<Pressable style={styles.customBtn}><Text>Update</Text></Pressable>
<TouchableOpacity><Text>Submit</Text></TouchableOpacity>

// After: one component, one label vocabulary
<Button variant="primary" label="Save changes" onPress={handleSave} />
```

- Flag any raw `<Text>` that should be a design system component
- Check that the same semantic action (save, delete, cancel, share) uses the same label everywhere
- Verify platform-specific patterns aren't swapped (Android back arrow vs iOS chevron)

**Signal strength:** Strong — token inconsistency is trivially detectable via regex on source.
**Priority:** High

### UH5 — Error prevention

Even better than good error messages is a careful design that prevents problems from occurring.

**What to look for:** Form inputs that accept invalid data then show an error (instead of constraining input). Submit buttons that remain active during processing (double-submit risk). Delete buttons placed next to edit buttons without spacing. No confirmation on irreversible actions. No input validation before network call.

**Why it matters:** Prevention is cheaper than recovery — both in engineering time and user frustration. Constraint-based design eliminates entire categories of errors before they happen.

**What to replace with:**
```tsx
// Before: free-text price field, validates on submit
<TextInput value={price} onChangeText={setPrice} />
<Button title="Submit" onPress={handleSubmit} />

// After: constrained input, disabled submit until valid
<TextInput value={price} onChangeText={setPrice} keyboardType="decimal-pad" placeholder="0.00" />
<Button title="Submit" onPress={handleSubmit} disabled={!isValidPrice(price) || isSubmitting} />
```

- Number-only fields should use `keyboardType="decimal-pad"` or `"number-pad"` — no free-text
- Submit buttons must disable on tap to prevent double-fire; consider debouncing
- Delete/edit adjacent buttons need visible separation (minimum 8px) or a divider
- Destructive actions (delete account, clear data) need two-step confirmation with explicit wording

**Signal strength:** Medium — some prevention patterns (double-submit) are code-detectable; constraint input quality requires human judgment.
**Priority:** High

### UH6 — Recognition rather than recall

Minimize memory load by making objects, actions, and options visible.

**What to look for:** Buried navigation (3+ taps to reach primary features). Settings-only features needed during normal flow. Information needed on the next screen that isn't carried forward. Long lists without section headers or search.

**Why it matters:** Short-term memory holds ~4 chunks. Every piece of information users must hold across screens consumes working memory that should be spent on their actual task.

**What to replace with:**
```tsx
// After: carry context forward
// Screen 2 shows: "Nike Air Max — Select size"
<View>
  <Text style={typography.title}>{selectedItem.name}</Text>
  <SizeSelector sizes={selectedItem.sizes} onSelect={handleSize} />
</View>
```

- Key navigation sections must be reachable within 2 taps from any screen
- Search should be available from the top level, not buried in a menu
- Multi-step flows should show a summary of user's choices before final confirmation

**Signal strength:** Medium — requires evaluating the flow across multiple screens.
**Priority:** High

### UH7 — Flexibility and efficiency of use

Provide accelerators — unseen by novice users — that speed up interaction for expert users.

**What to look for:** No shortcuts for repetitive actions. Power users forced through the same multi-step flow every time. No gestures (long-press, double-tap) that expose secondary actions. No search history or autocomplete. No batch operations.

**Why it matters:** Novices and experts have different needs. Accelerators substantially reduce interaction cost for frequent tasks.

- Primary actions on list items should be one tap; secondary actions via long-press or swipe
- Search should autocomplete from history and recent queries
- Favorite/recent items should appear as a shortcut section
- Batch operations for list management screens

**Signal strength:** Weak — hard to detect absence of accelerators without knowing domain frequency. Best assessed by asking "what does a power user do 10x/day?"
**Priority:** Medium

### UH8 — Aesthetic and minimalist design

Dialogues should not contain irrelevant or rarely needed information.

**What to look for:** Dense text walls. Cards showing more info than needed for the current context. Multiple competing visual hierarchies. Decorative elements with no function. Excessive modals or tooltips.

**Why it matters:** Visual clutter increases cognitive load linearly with element count. Every pixel should earn its place, especially on mobile.

- No two elements should compete for the same level of visual hierarchy
- Whitespace is not wasted space — insufficient padding is a defect
- Information density per screen should target ≤70% fill; >85% is a defect
- Primary action buttons should dominate visually; secondary actions clearly subordinate

**Signal strength:** Strong — density and hierarchy violations are visible from a screenshot.
**Priority:** Medium

### UH9 — Help users recognize, diagnose, and recover from errors

Error messages should be plain language, precise, and constructively suggest a solution.

**What to look for:** Error messages with codes only. Errors that blame the user. Errors without recovery path. Toast errors that auto-dismiss before reading. Generic catch-all errors ("Something went wrong").

**Why it matters:** Poor error communication doubles recovery time. Error messages are moments of peak frustration — every word must earn its place.

```tsx
// After: problem + solution
<ErrorState
  title="Can't load recommendations"
  message="Your internet connection seems offline. We'll retry automatically when you're back online."
>
  <Button title="Try again" onPress={retry} />
</ErrorState>
```

- Every error message must contain: what happened + why (if known) + what user can do
- Differentiate "no connection", "server down", "session expired" — each needs a different recovery path
- Retry must be offered for transient errors

**Signal strength:** Strong — error message quality is directly readable from source.
**Priority:** High

### UH10 — Help and documentation

Help must come to the user inline and contextually — they won't search for it.

**What to look for:** No onboarding flow. Blank empty states instead of guidance. No tooltips for non-obvious features. Help that links to external docs. No "what's new" after updates.

- Every empty state must answer: why is it empty + what can user do about it
- First-launch onboarding: max 3 screens, skip always visible
- Tooltips: one-time only
- After major update: one-screen "what's new"

**Signal strength:** Medium — missing empty states are code-detectable; help quality requires judgment.
**Priority:** Medium

### UH11 — Affordances

Visual properties of an element should suggest how to interact with it.

**What to look for:** Plain text acting as a button with no visual cue. Icons meant to be tappable with no interactivity cues. Cards that are tappable but look static. Flat design with no shadows/borders. Links identical to body text.

**Why it matters:** When an element doesn't look interactive, users don't attempt to interact — even if the action is critical (the Norman Door problem).

```tsx
// After: card with clear tappability cues
<Pressable
  style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
  onPress={handlePress}
>
  <Text>{item.name}</Text>
  <ChevronRightIcon />
</Pressable>
```

- All interactive elements need: min 44px, visual depth (shadow/border), active/pressed state
- Text buttons: underline or distinct color from body text
- Icon buttons: need a background circle/hover state or border
- List items that navigate: include a chevron/arrow as a signifier

**Signal strength:** Strong — affordance violations are visible in screenshots and code.
**Priority:** High

### UH12 — Signifiers

Perceptible cues that tell users *how* to perform an action.

**What to look for:** Swipeable items with no visual cue. Carousels with no pagination indicators. Scrollable content with no fade edge. Drag-to-reorder with no drag handle. Pull-to-refresh with no hint on first use.

**Why it matters:** Affordances reveal *that* you can act; signifiers reveal *how*. Users won't discover gesture-based interactions without signifiers.

- Carousels must show pagination dots AND arrow-button fallback
- Scrollable content: show partial overflow of next item as a peek
- Swipeable rows: show a 2-4px peek of the hidden action
- Drag-reorder lists need a visible drag handle

**Signal strength:** Medium — requires evaluating gesture discovery, harder from a static screenshot.
**Priority:** Medium

### UH13 — Mapping

The relationship between controls and their effects should be obvious from spatial layout.

**What to look for:** Controls that affect something off-screen with no visual connection. Direction mapping confusion. Tab bar actions that affect a distant part of the screen. Filters panel whose "Apply" button is disconnected from the filter controls.

**Why it matters:** Natural mapping reduces cognitive load to zero. Mismatched mapping forces the user to form and maintain an arbitrary connection between cause and effect.

- Filters panel: "Apply" must be visually grouped with the filter controls
- Sliders: up/down = increase, left/right = decrease is universal
- Tab bar items should affect the content immediately above the tab bar

**Signal strength:** Medium — requires understanding control-placement-to-effect relationships, which may span components.
**Priority:** Medium

### UH14 — Feedback

Every action should have an immediate, perceivable response.

**What to look for:** No visual feedback on button press. No haptic feedback on important actions. Form submissions that appear to do nothing for 500ms+. Toggle switches with no animation.

**Why it matters:** Feedback is the primary mechanism by which users learn the system is working. Delayed/absent feedback breaks the cause-effect loop, causing repeated taps and double-submissions.

```tsx
<Pressable
  onPress={handlePress}
  style={({ pressed }) => [styles.button, pressed && styles.buttonPressed]}
>
  <Text>Tap me</Text>
</Pressable>
```

- Every interactive element must change appearance on press
- Haptic feedback for: destructive actions, toggles, completed operations
- Form submission: button must show a loading spinner within 100ms of tap

**Signal strength:** Strong — missing press states and haptics are directly detectable in component code.
**Priority:** High

### UH15 — Constraints

Physical, logical, or cultural constraints that prevent invalid actions before they happen.

**What to look for:** Form fields accepting clearly invalid data, validated only on server round-trip. Date pickers allowing past dates when future is required. No character limits. Quantity selectors allowing 0/negative.

**Why it matters:** Constraints make it physically impossible to do the wrong thing — the strongest form of error prevention.

- Number inputs: use a Stepper (min/max) or validate on change, not on submit
- Date inputs: constrain via `minimumDate`/`maximumDate`
- Text inputs: `maxLength` for all database-backed fields
- Button disabled state is a constraint — use it proactively

**Signal strength:** Medium — violations are code-detectable but the right boundary requires domain knowledge.
**Priority:** Medium

### UH16 — Gulfs of execution and evaluation

The gap between a user's goal and the means to achieve it, and between system state and the user's understanding of it.

**What to look for:** Multiple steps where one would do. No confirmation/status change after completing a task. Actions available only via deep navigation. No visible state indicator after an action (favorited item doesn't show filled heart). Forms with no success state.

```tsx
// After: favorite with immediate visual state change
<Pressable onPress={toggleFavorite}>
  <HeartIcon filled={isFavorited} />
</Pressable>
```

- After every user action, the UI must change state to reflect it (optimistically if async)
- Count taps to primary features — >3 is a gulf-of-execution defect
- Form submission: transition to an explicit success state, not just "back to list"

**Signal strength:** Strong — missing optimistic updates and post-action state changes are directly code-detectable.
**Priority:** High

### UH17 — Fitts's Law (target size × distance)

Larger targets closer to the user's current position are faster to tap.

**What to look for:** Tap targets smaller than 44×44pt. Targets with less than 8pt gap. Primary actions in hard-to-reach zones. Icon-only buttons at 24×24pt with no padding.

**Why it matters:** Missing a tap target is frustrating. The 44pt minimum is an Apple HIG / Material Design requirement; violating it is a proven usability failure.

```tsx
<Pressable onPress={handleClose} style={styles.closeButton} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
  <XIcon size={24} />
</Pressable>
// closeButton: { width: 44, height: 44, justifyContent: 'center', alignItems: 'center' }
```

- Every interactive element: verify `minHeight >= 44` and `minWidth >= 44` (or `hitSlop` achieves it)
- Adjacent targets: minimum 8pt gap
- FABs: minimum 56×56pt

**Signal strength:** Strong — 44pt violations are trivially detectable by scanning style definitions.
**Priority:** High

### UH18 — Hick's Law (decision time vs. number of choices)

Decision time increases logarithmically with the number and complexity of choices.

**What to look for:** Long menus (7+ items). Tab bars with 5+ tabs. Category screens with 15+ items and no search/filter. Overloaded bottom sheets. Settings screens with endless ungrouped rows.

- Tab bars: maximum 5 tabs; 5th is often "More"
- Action sheets: maximum 4-5 options
- Settings screens: group into sections (max 7 items/section); provide search
- Category browsing: progressive disclosure — 4-6 top level → drill in

**Signal strength:** Medium — assessing choice overload requires understanding the decision context.
**Priority:** Medium

### UH19 — Thumb zone mapping *(mobile-only)*

The screen divides into reachability zones based on thumb position.

**What to look for:** Primary actions in the hard-to-reach top zone. Navigation controls at the top instead of bottom. Confirm/submit buttons at top far-right. Dismiss controls in the top-left corner.

- Primary actions → bottom zone; navigation → bottom tab; secondary → middle
- Confirm/Submit/Save/Continue — thumb-friendly zone (bottom half)
- Settings/toggles: frequently-changed near bottom, rarely-changed deeper in list

**Signal strength:** Medium — requires understanding which actions are primary for the screen's goal.
**Priority:** Medium

### UH20 — Bottom sheet and modal overlay behavior *(mobile-only)*

Modal overlays should signal their relationship to content below and avoid trapping users.

**What to look for:** Modals with no clear dismiss path. Bottom sheets covering the full screen. Sheets that can't be dismissed by swipe/backdrop tap. Multiple stacked modals with no hierarchy.

- Bottom sheets: max 50-70% of screen height; full-screen content should push-navigate instead
- Always include a grabber handle
- Swipe-down to dismiss must work
- Avoid stacked modals — use push navigation instead

**Signal strength:** Strong — full-screen misuse and missing dismiss paths are directly code-detectable.
**Priority:** Medium

### UH21 — Keyboard avoidance and scroll behavior

The interface must not obscure active inputs when the keyboard appears.

**What to look for:** No `KeyboardAvoidingView` wrapping forms. Keyboards covering the active field. Submit button hidden behind keyboard. Scroll not enabled when keyboard is open.

```tsx
<KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.container}>
  <ScrollView keyboardShouldPersistTaps="handled">
    <TextInput placeholder="Email" />
    <Button title="Log in" />
  </ScrollView>
</KeyboardAvoidingView>
```

- Every screen with text inputs must use `KeyboardAvoidingView`
- `keyboardShouldPersistTaps="handled"` so users can tap buttons while keyboard is open
- Test at the smallest supported screen size

**Signal strength:** Strong — missing `KeyboardAvoidingView` is trivially code-detectable (mobile).
**Priority:** High

### UH22 — Pull-to-refresh, swipe, and gesture conventions *(mobile-only)*

Standard platform gestures must work as expected; custom gestures must not conflict with system gestures.

**What to look for:** Missing pull-to-refresh on remote-loaded content. Custom swipes overlapping OS-level edge swipes. Gesture-only actions with no button fallback.

- Pull-to-refresh only on refreshable content
- Swipe-to-delete must have undo snackbar
- Reserve left-edge for iOS back gesture
- Gesture-only interactions are a WCAG violation — every gesture needs a tap alternative

**Signal strength:** Medium — gesture conflicts require runtime testing; missing fallbacks are code-detectable.
**Priority:** Medium

### UH23 — Safe area insets and notches *(mobile-only)*

Content must respect safe area insets.

**What to look for:** Hardcoded status-bar padding instead of `SafeAreaView`/`useSafeAreaInsets`. Content extending behind the notch. Bottom navigation overlapping the home indicator.

- Root screen containers: wrap in `SafeAreaView` with appropriate edges
- Bottom navigation: include home indicator safe area
- Use `react-native-safe-area-context` — never hardcode status bar heights

**Signal strength:** Strong — hardcoded padding and missing SafeAreaView are trivially code-detectable.
**Priority:** High

### UH24 — Appropriate UI for each state (loading → empty → error → data)

Every data-driven component must handle four states.

**What to look for:** Components that crash or show nothing on empty data. Infinite spinners with no error boundary. Full-screen spinners instead of skeletons. Blank empty states. Generic error states with no recovery.

```tsx
function ItemList() {
  const { data, isLoading, isError, error, refetch, isRefetching } = useQuery(...);
  if (isLoading) return <ItemListSkeleton />;
  if (isError) return <ErrorState title="Couldn't load items" message={error?.message} action={{ label: 'Try again', onPress: () => refetch() }} />;
  if (!data || data.length === 0) return <EmptyState title="No items yet" action={{ label: 'Browse catalog', onPress: goToBrowse }} />;
  return <FlatList data={data} renderItem={renderItem} refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} />} />;
}
```

- Skeleton placeholders for content-heavy lists, matching the content's shape
- Never a full-screen spinner for initial list load
- Empty state must include: icon + what happened + what to do next + CTA
- Error state must include: what went wrong + retry action

**Signal strength:** Strong — missing state handlers are directly code-detectable via component structure.
**Priority:** High

### UH25 — Empty states that guide users (not dead ends)

Empty states should explain why content is absent and provide a next action.

**What to look for:** Blank white screen on empty list. "No results" with no suggestion. Empty favorites with no explanation of how to favorite.

- Every empty state: illustration/icon + reason + action
- Search empty states: suggest broadening terms, show recent searches
- No generic empty-state component without props — each should be purpose-written

**Signal strength:** Strong — missing EmptyState or empty `<View />` is directly code-detectable.
**Priority:** High

### UH26 — Error recovery vs. error wall

Errors should provide a recovery path, not a full-screen dead end when only one section failed.

**What to look for:** Full-screen error overlays when a single widget fails. Errors covering the entire content with no dismiss. No retry on network errors.

```tsx
// After: inline error, doesn't break surrounding content
if (isError) return <InlineError title="Couldn't load recommendations" message="Tap to retry" onPress={() => refetch()} />;
```

- Component-level errors render inline, not full-screen
- Full-screen error walls acceptable only when the whole screen is unusable without the data (e.g. auth)
- Retry available without page navigation

**Signal strength:** Strong — error walls are directly code-detectable (component vs. page-level error rendering).
**Priority:** High

### UH27 — Optimistic UI with rollback vs. pessimistic

Choose optimistic updates for low-risk actions; pessimistic for high-risk.

**What to look for:** Spinner on every mutation, even simple toggles. Favorite toggle with 300ms+ delay before visual change. No rollback on failed optimistic update. Silent failure with no error notification.

```tsx
onPress={async () => {
  setOptimisticFavorited(!optimisticFavorited);
  try { await toggleFavorite(item.id); }
  catch { setOptimisticFavorited(optimisticFavorited); showToast('Failed to update favorite'); }
}}
```

- Optimistic UI for: favorites, likes, follows, dismiss/hide, toggles
- Always pair with rollback + error notification
- Pessimistic only for: purchases, account deletion, irreversible changes

**Signal strength:** Strong — optimistic vs. pessimistic choice is code-detectable (state change before vs. after await).
**Priority:** High

### UH28 — Gestalt principles (proximity, similarity, closure, figure-ground)

Visual perception follows predictable grouping rules.

**What to look for:** Related actions separated by large gaps; unrelated elements placed close together. Primary buttons with inconsistent styles. Missing visual completion cues. Content blending into the background.

- Proximity: label-value pairs ≤8px gap; section-to-section ≥16px gap
- Similarity: all primary buttons share exact same tokens; same-level headings share size/weight/color
- Figure-ground: content area must differ in background color from the page

**Signal strength:** Medium — proximity/similarity require layout evaluation; token violations are code-detectable.
**Priority:** Medium

### UH29 — Progressive disclosure

Reveal complexity gradually; show the minimum needed for the current context.

**What to look for:** Settings screens showing all options at once. Detail pages showing rarely-used info as prominently as essential info. Forms with 8+ fields visible at once.

- Pages with >7 interactive items need grouping
- Forms: wizard pattern for >4 fields, with a progress indicator
- Settings: group into sections with descriptive headers; drill-down for >4 items/section

**Signal strength:** Weak — requires understanding what's "primary" vs "secondary," which is domain-dependent.
**Priority:** Low

### UH30 — Information scent

Visual and textual cues that signal users they're on the right path.

**What to look for:** Generic link labels ("Click here", "Read more"). Category names that could mean anything. Search results with no context (no price/image/rating). CTAs that don't describe what happens next.

- Navigation labels must match the destination page title
- Search results: show enough context to evaluate without tapping in
- CTAs describe the outcome, not the action ("Get recommendations" not "Submit")

**Signal strength:** Medium — weak scent is detectable from copy review but requires understanding the user's goal.
**Priority:** Medium

### UH31 — Scanning patterns (F-pattern, Z-pattern)

Users scan mobile/web screens in predictable patterns; layout should place key content where users look first.

**What to look for:** Critical content in the bottom-right of long content screens. Key actions not at natural scan endpoints. Most-important info buried mid-screen.

- Primary CTA: bottom fixed bar (scan endpoint)
- Titles/prices: top of screen, first ~200px
- Action sheets: most-used action first, destructive at bottom

**Signal strength:** Medium — requires understanding what constitutes "key content" for the screen's context.
**Priority:** Medium

### UH32 — Button labels = action verbs

Every button label should start with a verb describing what happens on tap.

**What to look for:** "Submit", "OK", "Yes/No", "Click here", "Confirm", "Cancel" with no context. Labels that differ from the action they trigger.

- Every button label = verb + noun (minimum)
- "Submit" → "Save changes" / "Place order"; "OK" → "Got it" / "Continue"
- Confirmation: repeat the risky action in the button ("Delete item"), not just in the question

**Signal strength:** Strong — generic button labels are trivially detectable via grep on source.
**Priority:** High

### UH33 — Error messages = problem + solution

Every error message must state what went wrong and what the user can do.

**What to look for:** Error codes as the only message. Technical jargon. Blaming the user. No solution path. Passive voice.

- Template: "Can't [action]. [reason]. [solution]."
- Never show raw error codes to end users (log to observability instead)
- Differentiate no-connection vs. server-error vs. permission-denied, each with different copy/recovery

**Signal strength:** Strong — error message quality is directly readable from source.
**Priority:** High

### UH34 — Confirmation dialogs = what will happen + undo mechanism

Confirmation dialogs must state the consequence and how to undo it.

**What to look for:** "Are you sure?" with no stated consequence. Yes/No buttons forcing re-read of the question. No mention of undo. Dialogs for non-destructive actions (unnecessary friction).

- Template: "Do you want to [action] [item]?" + consequence + undo info
- Yes/No → outcome-describing labels instead ("Delete" / "Keep")
- Always state honestly whether the action can be undone
- Every dialog needs a clear dismiss path

**Signal strength:** Strong — vague confirmation dialogs are directly code-detectable.
**Priority:** High

### UH35 — Empty states = why it's empty + what to do next

Empty states must answer "why is this empty?" and "what should I do?"

**What to look for:** Blank screen on empty data. "No items" without explanation or CTA. Illustration with no text at all.

- Template: illustration + reason ("Your X is empty") + solution + CTA button
- Search empty: "No results for [query]" + broaden-search suggestion
- Favorites empty: explain how to favorite + browse CTA

**Signal strength:** Strong — missing empty state or empty View is directly code-detectable.
**Priority:** High

---

### Priority summary table

| Priority | Heuristics |
|----------|-----------|
| **High** | UH1, UH2, UH3, UH4, UH5, UH6, UH9, UH11, UH14, UH16, UH17, UH21, UH23*, UH24, UH25, UH26, UH27, UH32, UH33, UH34, UH35 |
| **Medium** | UH7, UH8, UH10, UH12, UH13, UH15, UH18, UH19*, UH20*, UH22*, UH28, UH30, UH31 |
| **Low** | UH29 |

`*` = mobile-only heuristic.

### Quick audit ordering checklist

Process components/screens in this order for efficient, high-signal coverage:

1. **State coverage** (UH24–UH27): loading, empty, error, data all handled? Fastest, highest-impact check.
2. **Tap targets** (UH17): scan all interactive elements for 44pt minimum. Blocks basic usability.
3. **Safe areas** (UH23, mobile): check root containers and modals.
4. **Keyboard handling** (UH21): check forms.
5. **Button labels** (UH32) and **error messages** (UH33): scan visible strings — quick source grep.
6. **Affordances** (UH11) and **feedback** (UH14): verify press states on all interactives.
7. **Gulfs** (UH16): check optimistic updates and post-action state changes.
8. **User control** (UH3): check undo/back on destructive actions.
9. **Confirmation dialogs** (UH34) and **empty states** (UH25/UH35): verify copy pattern.
10. **Consistency** (UH4): verify design tokens are used consistently.
11. **Error walls** (UH26): component-level vs. full-screen error rendering.
12. **Bottom sheets, gestures, thumb zones** (UH20, UH22, UH19, mobile): interaction-level review.
13. **Gestalt, scanning, information scent** (UH28, UH31, UH30): layout-level review.
14. **Progressive disclosure** (UH29): information architecture review.
15. **Flexibility, constraints** (UH7, UH15): power-user and edge-case review.
