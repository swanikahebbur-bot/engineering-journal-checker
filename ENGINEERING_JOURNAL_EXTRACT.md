# Engineering journal

Bugs that were expensive to find, and the rule each one taught. **Written for whoever debugs next
— human or agent.**

This is not a changelog and not a list of what was fixed. Git already has both. What git does not
have is *why the bug was hard to see*, which is the only part that transfers to the next bug.

**Add an entry when a bug cost more than an hour, misled someone, or survived a previous fix.**
Not for ordinary work. A journal nobody trusts is one that logged everything.

**Format.** Keep all five fields — the last one is what makes an entry usable rather than
decorative, because a future session can *run* it instead of reading prose.

> **Symptom** — what is observed, in the words someone would report it in
> **Root cause** — with `file:line` as of the date, and the actual code
> **What misled us** — the wrong turn, the comment that lied, the check that couldn't fail
> **The rule** — the generalizable version, stated so it applies beyond this bug
> **Detect it again** — a command, a grep, a question to ask

---

*This is an extract of our engineering journal, not the whole file. Entry numbers are the
real ones, so they have gaps where an entry was left out. A few entries refer to entries that
are not in here; that is expected.*

## Index

**How to use this file.** Scan the rules below, not the entries. Each one is the generalizable
form — if it does not sound like your problem, the entry will not help. When one does, jump to it
and read *Detect it again* first: it is a command or a question you can run now, and it will tell
you in seconds whether you are looking at the same bug.

| # | The rule it taught | Area | Detector |
|---|---|---|---|
| 1 | A watchdog must not read the state it is guarding against | iOS, world transition | yes |
| 2 | Idempotence makes a retry safe and useless at the same time | iOS, SwiftUI presentation | yes |
| 3 | `BUILD SUCCEEDED` does not prove your change was applied | process | yes |
| 5 | Flip the orientation mask *before* the cover dismisses; request the geometry after | iOS, orientation | yes |
| 10 | An interface rotation is three separate hazards, and you will meet them one at a time | iOS, world transition | yes |
| 20 | Swift's synthesized `Decodable` is strict, and `try?` turns strict into silent | frontend / persistence, API decoding | yes |
| 22 | `==` against a framework enum is a bet that Apple stopped adding cases | iOS, feature-gating | **none** |
| 23 | Environment values freeze at the paging TabView's hosting boundary — and reasoning is not running | iOS, SwiftUI, shell chrome / layout | **none** |
| 24 | The fix removed the thing we *believed* was the trigger — the duplicate came back because the trigger was the configuration, not the presentation | iOS, AlarmKit / ActivityKit, focus sessions | **none** |
| 25 | Every `await` in a session-scoped service is an account boundary — and a guard that exists as a pattern is not a guard | — | **none** |

**Entries 22, 23, 24 and 25 carry no *Detect it again*.** Every entry states its rule;
these four state it without giving anyone a way to catch the bug recurring, which is the field that
turns a lesson into a check. `TASKS.md` T-38.

---
## 2. Idempotence makes a retry safe and useless at the same time

**Date:** 2026-07-30 · **Area:** iOS, SwiftUI presentation

**Symptom.** A 2.5-second retry in `WorldView.exitWorld` never once rescued a dropped dismissal.

**Root cause.** The retry called `leaveWorld()` again. That writes `showWorld = false` over a
`showWorld` that is *already* `false`. SwiftUI sees no change, schedules no view update, and the
cover is never dismissed. A retry that re-writes an unchanged `Bool` cannot dismiss anything.

**What misled us.** The comment cited idempotence as the reason the retry was **safe**. It is the
same reason the retry was **useless**, and nobody read the second implication.

**The rule.** In a declarative framework, "no-op" means "schedules no update." Retrying an
idempotent write is *guaranteed* to change nothing — which is precisely wrong when what you are
retrying is a side effect that got dropped. Retry the effect, then do not trust it: put the user
back in a state they can act from.

**Detect it again.** When you write a retry, ask what observable changes on the second attempt. If
the answer is "nothing, it's idempotent," it is not a retry.

---

## 3. `BUILD SUCCEEDED` does not prove your change was applied

**Date:** 2026-07-30 · **Area:** process

**Symptom.** Three consecutive green builds were reported as three landed stages. **Zero of the
changes were in the repo** — the files had never been written. The builds were compiling unchanged
code and passing, exactly as they would have before.

**What misled us.** A landing check that cannot fail is worse than no check, because it
manufactures confidence. `git status` caught it only when commit commands were being prepared.

**The rule.** A verification step must be capable of failing for the reason you care about. "It
compiles" answers a different question from "it is there."

**Detect it again.** Grep for a symbol that exists only in the new code:

```bash
cd "<repo>" && for m in "path/A.swift:newSymbolA" "path/B.swift:newSymbolB"; do f="${m%%:*}"; s="${m##*:}"; n=$(grep -cF "$s" "$f" 2>/dev/null || echo 0); [ "$n" -gt 0 ] && echo "OK   $s" || echo "MISS $s"; done
```

Pair it with the inverse — confirm the *old* code is gone — or a partially-applied edit reads as a
complete one.

---

## 5. Flip the orientation mask *before* the cover dismisses; request the geometry after

**Date:** 2026-07-30 · **Area:** iOS, orientation

**Symptom.** After leaving the landscape world, the portrait shell rendered rotated 90° inside a
landscape frame. Usable, but visibly broken.

**Root cause.** `AppDelegate.orientationMask` is what
`application(_:supportedInterfaceOrientationsFor:)` answers with. While it still said `.landscape`,
the portrait shell was measured into a landscape frame the instant the cover went away. The design
had moved *both* the mask flip and the `requestGeometryUpdate` call into `.onDisappear`.

**What misled us.** The design's reasoning for the move was correct and important — requesting a
geometry update on a scene whose top view controller is the cover you are about to dismiss
*does* silently drop the dismissal, and that was half the original bug. The error was treating the
mask and the geometry request as one thing.

**The rule.** They have different hazards and belong in different places. The **mask** is a plain
variable read from a delegate callback — it races nothing and must be correct *before* the
transition. The **geometry request** is the call that collides with an in-flight dismissal and must
come *after* it.

**Detect it again.** After any change to world entry/exit, exit once and confirm the shell is
upright. If content is right but rotated, suspect the mask, not the request.

**⚠ HALF-STALE 2026-08-05.** The mask half of this rule is still exactly right and still in force.
The geometry half no longer describes the code: the crossing does not call `requestGeometryUpdate`
at all any more — `setOrientationMask` sets the mask and lets the present/dismiss carry the
rotation, and the only surviving caller is `forceOrientation`, a repair path guarded against
running when the interface already agrees. Read the title as **"flip the mask before the
transition"** and ignore the second clause.

---

## 10. An interface rotation is three separate hazards, and you will meet them one at a time

**Date:** 2026-07-31 · **Area:** iOS, world transition

**Symptom.** Six rounds of "the world crossing is still glitching", each with a different-looking
defect, each fixed, each revealing the next one underneath.

**Root cause — all three are the same event, and none of them is obvious from the source.**

1. **It re-lays-out the view, resetting `@State` and cancelling `.task`.** This ate the aperture
   (the entry zoom never played), the ring's animation, and a watchdog. Anything that must survive
   a rotation belongs to a **parent** or to the **clock** (`TimelineView(.animation)`), never to
   the view being rotated.
2. **It is a UIKit transition, and a second one running at the same time collides.** A modal
   presentation overlapping a geometry request is what produced "one screen sliding off to reveal
   another" — a `Transaction(animation: nil)` does not suppress it.
   **⚠ CORRECTED 2026-08-01 — the remedy first written here was wrong.** This entry originally
   prescribed "present, *wait*, then rotate", i.e. sequencing the two transitions. That cannot
   work, and six measurement passes were spent tuning the wait before anyone noticed: the sleep was
   trimmed to 100ms against a `coverVertical` that runs 350–500ms. **The fix is suppression, not
   separation** — see entry 12. Sequencing remains useful for the geometry request itself, but the
   modal transition must be switched off outright.
3. **Anything orientation-dependent on screen during it will be seen.** Not just rectangles - a
   centred circle is invariant in *appearance* but its *position* is resolved against a frame that
   is changing size, so it was thrown up to 344px on the single frame the screen turned.

**What misled us.** Each fix genuinely worked and exposed the next layer, so every round felt like
a regression. And the shape of the bug — intermittent, ~1-in-3 — was an illusion: measurement
showed **4 of 4 entries failing every time**, with only the severity alternating.

**The rule.** Nothing orientation-dependent may be on screen while the interface rotates; anything
that must outlive the rotation belongs to a parent or the clock; and two UIKit transitions must
never overlap. Every fix that held was one of those three. Every fix that ignored them failed.

**Detect it again.** When two halves of a symmetric flow behave differently, **the difference is
the diagnosis**. Entries leaked and exits did not; the only structural difference was that exits
kept their cover raised across the rotation. That one comparison was worth more than three rounds
of reading the code. Later, the same trick again: the mask circle never moved while a sibling ring
moved 344px — same centring, same container, different compositing.

---

## 20. Swift's synthesized `Decodable` is strict, and `try?` turns strict into silent

**Date:** 2026-08-06 · **Area:** frontend / persistence, API decoding

**Symptom.** Three near-misses in one day, in three unrelated files, all of which would have
shipped as *silent data loss* rather than as an error:

1. Adding one field to a stored struct would have **wiped every existing user's saved calendar
   visibility** on first launch after the update.
2. Adding one field to another stored struct would have **wiped every existing user's chosen
   calendars** the same way.
3. Adding one value to a server-side vocabulary (`"focus"` in `VERIFICATION_METHODS`) would have
   made **every already-installed client render an empty goals list** — not the new goal missing,
   the *entire list* gone — the moment one such goal existed anywhere.

None of the three throws anything a user or a log would see. All three read as "the feature works,
and your data is gone."

**Root cause.** Two facts that are individually reasonable and lethal together.

*Fact one: the synthesized decoder is stricter than the type is.* Swift generates
`init(from:)` using `decodeIfPresent` **only for optional properties**. A non-optional property
*with a default value* still gets a plain `decode`, which throws `keyNotFound` when the key is
absent. So adding `var hasDeclinedSync = false` to a `Codable` struct does not mean "old blobs read
as false" — it means **old blobs stop decoding entirely**. The default is applied by `init()`, and
`init(from:)` never runs it.

The same strictness applies to enums: `RawRepresentable` decoding throws
`dataCorrupted` on a raw value it does not know. In a `[Goal]` that is not a partial failure —
`Array`'s decoder gives up on the first bad element, so **one unknown enum value discards every
other element in the response**.

*Fact two: this codebase reads through `try?`.* Every store does some version of
`(try? JSONDecoder().decode(T.self, from: data)) ?? .empty`, which is correct-looking and normally
right: a corrupt blob should not crash the app. But it converts *every* decoding failure into a
default value. Strictness plus `try?` equals "your saved state was quietly replaced with nothing."

**What misled us.**
1. **The property has a default, so it looks safe.** `var hasDeclinedSync = false` reads as "absent
   means false" in every language most of us have used, and in Swift's own memberwise init. It is
   only untrue for the *decoder*, which is the one caller that matters here.
2. **It cannot be caught by testing the new build against a new install.** A fresh install has no
   stored blob, so there is nothing to fail to decode. The bug only exists for users who already
   have data — i.e. everyone except the person testing it.
3. **`try?` is defensible everywhere it appears.** No individual use of it is wrong. The hazard is
   the interaction, and interactions do not show up in a diff.
4. **The enum case is worse than it looks.** "An old client will not understand the new value" reads
   as "the new goal will be missing." It is not; it is the whole list.

**The rule.** **A `Codable` type that is PERSISTED is a schema, and every field added to it is a
migration.** Hand-write `init(from:)` with `decodeIfPresent` and an explicit default for every new
key, forever — the synthesized one is only safe for a type that has never been stored. For
server-side vocabularies, the client must decode unknown values into a known case (an `unknown`
case, or a custom `init(rawValue:)` that falls back) rather than throwing, and any addition ships
**client-first and dark**: the client learns the value, is released, and only then does the server
start emitting it.

Corollary about `try?`: it is right for *corrupt* data and wrong for *unfamiliar* data, and it
cannot tell the difference. Where the two must be distinguished, decode with `try` and handle the
error, or make the type incapable of the second failure.

**Detect it again.** For any struct that is written to `UserDefaults` or a file, adding a property
is the trigger — check it before you check anything else:

```bash
# Persisted Codables read through a swallowing try? - each one is a schema
grep -rn "try? JSONDecoder().decode" --include="*.swift" . | head -20
```

The direct test takes two minutes and is the only one that proves it: decode a **legacy blob**
(saved before the field existed) with the new type and assert every prior field survived. One agent
did exactly this with `swiftc -swift-version 6` against a hand-written old blob, and it is the only
reason we know the fix works rather than believing it does.

For enums crossing the wire:

```bash
grep -rn "String, Codable\|String, Decodable" --include="*.swift" . | grep -i "enum"
```

Ask of each: *if the server sent a value this build has never heard of, what does the user see?*
If the answer is "an empty list", fix it before the server can ever send one.

---

## 22. `==` against a framework enum is a bet that Apple stopped adding cases

**Date:** 2026-08-07 · **Area:** iOS, FamilyControls, feature-gating

**Symptom.** The founder ran a four-hour focus session on his own phone and was **never offered the
app picker** — no shield row on the commit card, no block, nothing. The feature had been built,
reviewed, shipped to TestFlight and documented. On the device it simply was not there, and it
failed *silently*: no error, no empty state, no log line. The screen rendered exactly as it does on
a Simulator, which is to say as though the device could not do Screen Time at all.

**Root cause.** One line:

```swift
var isSupported: Bool { authorization == .approved }
```

`FamilyControls.AuthorizationStatus` had three cases when that was written. **iOS 26.4 added a
fourth — `.approvedWithDataAccess`** — which is what the status becomes when the app holds
`com.apple.developer.family-controls.app-and-website-usage` and the user grants it.
It means *approved, and then some*. Against `== .approved` it reads as **not approved**, so
`isSupported` went false, and with it `isConfigured`, `canShield`, the picker row, and every raise
the app would ever attempt. **A user who granted everything they were asked for got no shield, and
the app told them nothing.**

**What misled us.** Three things, and the third is the durable one.

1. **The state is unreachable in the Simulator**, where Family Controls never authorizes at all.
   Every path that could have shown it needs hardware, which is where this whole tier lives.
2. **The symptom is indistinguishable from correct behaviour.** `isSupported == false` renders as
   "this device can't do this", which is *right* on a Simulator and *catastrophically wrong* here.
   A gate whose false branch is a legitimate state has no failure appearance.
3. **The comment on the line described the Simulator case at length and never mentioned the enum.**
   It had been reasoned about carefully — in one direction only. Confident prose about *why false
   is sometimes correct* is what kept anyone from asking *when false is wrong*.

**The rule. Never equality-test an enum you do not own.** A framework enum is an open set, and every
`==` against one is a wager that the vendor is finished. Ask the question you actually mean — here
"did they say yes", not "did they say yes in the exact words available in the SDK I compiled
against" — and write it as an exhaustive `switch` with `@unknown default`, so the compiler tells you
the day the set grows instead of the user discovering it.

**And pick the default by asymmetry, not by caution.** `@unknown default` here returns **true**:
treating a real approval as a refusal silently disables an entire feature, while treating a refusal
as an approval costs one failed raise that the applier already handles. When the two mistakes cost
different amounts, "be conservative" is not a decision — it is a way of avoiding one.

**Same family as entry 20** (`Decodable` strictness plus `try?`): both are the app being *strict
about a value it should have been generous with*, and both failed silently in a way that looked
like an empty state. When a gate can be wrong in only one direction, make that the loud direction.

---

## 23. Environment values freeze at the paging TabView's hosting boundary — and reasoning is not running

**Date:** 2026-08-11 · **Area:** iOS, SwiftUI, shell chrome / layout

**Symptom.** The founder reported the same bug three times: with a live focus-session pill on the
shell's bottom chrome, the goal list's wallet chips ("0 Tempo", "From 10 per check-in") sat
*behind* the pill, and being pinned `.safeAreaInset` chrome, could never be scrolled clear. Two
fixes shipped in between, each reviewed and each reasoned correct. Both failed on device.

**Root cause — two, stacked, which is why it survived two fixes.**

1. **`onGeometryChange` on the shell's bottom overlay fired exactly once, at first layout, and
   never again.** The measured reserve froze at whatever the launch state was: launch with a pill
   and every screen stayed padded high forever; launch without one and nothing ever rose. Swapped
   for a `GeometryReader` writing a `PreferenceKey`, which re-collects on every layout pass.
2. **The environment write never re-propagated into pages already pushed inside the paging
   `TabView`.** The reserve travelled as an `EnvironmentValues` key set on the shell's chain. Each
   `.page`-style tab lives in its own hosting controller, and an environment change on the shell
   did not re-render pushed destinations inside them — on-screen probes read **shell 60 / pushed
   page 104, simultaneously, indefinitely**. Tree-scoped propagation stops where the tree does.
   The fix is the pattern this codebase already documents for the session clock: a shared
   `@Observable` (`BottomChrome.shared.height`) read directly in `body`. Observation tracking is
   *data*-driven, not *tree*-driven, so it crosses hosting-controller boundaries that environment
   plumbing does not.

**What misled us.** Each half was individually plausible and the two failures were
indistinguishable from each other on screen. A frozen measurement and a frozen environment both
render as "the chips didn't move" — so fixing either one, alone, changed nothing visible, and each
"failed fix" was read as the *same* bug rather than as one of two. Only putting the publisher's
value and the consumer's value **on the screen at the same time** (`PUB:60 / ENV:104` in red debug
labels, in the Simulator) split them apart. Twenty minutes of running beat three rounds of review.

**The rules.**

- **A cross-cutting UI fact (chrome height, live-session presence) is a property of the shell,
  not of a view — publish it through a shared `@Observable`, never through the environment, if
  any consumer lives inside a `TabView`'s hosting boundary.** Environment is for tree-scoped
  configuration; it silently stops being reactive exactly where UIKit containers begin.
- **A layout fix is unverified until it has been watched moving in both directions.** Appear AND
  disappear, on the live screen, not on a fresh launch — fresh launches lay out from current
  state and hide every staleness bug. The Simulator runs the whole non-shield app; there was
  never a reason this needed three reports from a physical phone.
- When a fix "didn't take", suspect **two stacked defects with one symptom** before suspecting
  the fix. Instrument the seam between them — one probe per layer, visible simultaneously — and
  the layers name themselves.

## 24. The fix removed the thing we *believed* was the trigger — the duplicate came back because the trigger was the configuration, not the presentation

**Date:** 2026-08-11 · **Area:** iOS, AlarmKit / ActivityKit, focus sessions

**Symptom.** The founder's Lock Screen showed the same focus session twice — identical copy, one
card with a progress bar (ours) and one without — for the *second* time. The first occurrence
(2026-08-08) was diagnosed as AlarmKit vending its own `AlarmAttributes` Live Activity because we
supplied an `AlarmPresentation.Countdown`, and the fix was to stop supplying one. That fix was
reviewed, reasoned, shipped — and the duplicate returned on device with the countdown presentation
already gone.

**Root cause.** The trigger was never the presentation. Scheduling any
`AlarmConfiguration.timer(duration:)` makes the alarm a live countdown to the *system*
(`Alarm.State` has a `.countdown` case for it), and the system surfaces its own Live Activity for
one at schedule time however the presentation is dressed. Omitting the countdown presentation only
changed what the unwanted card *looked like*. The real lever is the configuration:
`.alarm(schedule: .fixed(fireDate))` names the closing instant instead, sits in `.scheduled` with
no countdown mode and no activity until the moment it alerts, and the alert still breaks through
Focus and silent mode — which is the entire reason AlarmKit is used.

**Why it was hard to see.** The first diagnosis *worked in the room*: it explained both cards,
the fix visibly changed behaviour in testing windows where the schedule call happened to throw
(the retry path takes our card down, so one card showed either way), and the theory — "describing
a countdown card is what asks for one" — reads like documentation even though no documentation
says it. Nothing in the API surface distinguishes "this parameter decorates the system's card"
from "this parameter causes it". Only the plain card's *copy* proved the truth later: it matched
exactly one view in the codebase, the one that renders nothing but `AlarmAttributes` activities,
so an AlarmKit activity provably existed with no countdown presentation supplied.

**The rules.**

- **A fix whose mechanism you inferred (rather than read or measured) is a hypothesis that
  shipped.** Record it as one. The 2026-08-08 comment asserted the countdown presentation "is
  what makes AlarmKit vend its OWN activity" as fact; stating the confidence level would have
  made the second report a confirmation instead of a mystery.
- **When a duplicate UI element reappears, fingerprint it by its copy.** Every string on the
  plain card resolved to one renderer, which named the owning framework and closed the diagnosis
  in minutes. Copy enums shared across processes (FocusSessionCopy) make this fingerprinting
  possible — one more reason strings live in one place.
- **Prefer changing what the system is *told the thing is* over changing how it is dressed.** A
  timer is a countdown, and the OS treats it as one everywhere; no presentation flag negotiates
  that away. If the surface is unwanted, the object must stop being the kind of object that gets
  the surface.

## 25. Every `await` in a session-scoped service is an account boundary — and a guard that exists as a pattern is not a guard

*2026-08-11 · frontend · found by adversarial review of the widget bridge, before any user hit it*

`GoalService` outlives the session: built once at launch, handed to every screen, serving
whichever account is signed in. Its goals fetch learned this the hard way long ago — a stalled
GET's continuation once pruned a goal created after the request was issued, and `fetchGoals` grew
a generation counter and an issued-for-scope check, re-verified after every `await`. The lesson
was written down, in a long comment, in that function.

Then two more fetches were written — the wallet, and (2026-08-11) the keeps aggregates — and
neither carried the guard, because nothing made them carry it. Each looks innocent alone: a few
lines, one `await`, an assignment after. The race they share needs an account to sign out while
its response is in flight and a second account to sign in before it lands — which no one
reproduces at a desk, ever. Account A's keeps landing under account B would have poisoned B's
`keptToday` reads; A's wallet landing under B would have put A's coin balances on B's screens and
set `walletHasLoaded` as though B's wallet had been measured.

What escalated it from latent to urgent was a change that never touched the continuation at all:
the widget bridge. The day `loadKeeps`'s continuation began publishing to the App Group, its
landing zone stopped being the app's own screens and became the Lock Screen — readable without an
unlock. A's history on B's Lock Screen is not a stale-cache bug; it is cross-account data
exposure, produced by code that had been "working" unchanged the whole time.

**Why it was hard to see.** The guard existed — as prose, in a sibling function, explained
beautifully. A pattern that lives in a comment is enforced by nothing: the next fetch method is
written by reading the API client's signature, not by reading the neighbour's war story. And the
severity was set by the *reader* of the state, not the writer: auditing the new widget code alone
showed nothing wrong, because the defect sat in an old writer whose blast radius the new reader
had silently widened.

**The rules.**

- **Every `await` in a session-scoped service is an account boundary until proven otherwise.**
  The question for a continuation is never just "is this data fresh" — it is "is this data for
  the account that is signed in *now*". Both facts (a fetch generation and the scope it was
  issued for) are captured at issue and re-checked after the await, on the failure branch too: a
  superseded failure must not re-mark the current account's fresh cache stale.
- **The third copy of a guard is the signal that the pattern failed.** One guarded fetch is a
  fix; a second unguarded one is an accident; a third is proof the protection lives in the wrong
  place. Until a paved path exists (one guarded fetch helper), the counters' declarations must
  name every sibling, so the list itself confronts whoever writes the fourth.
- **When a new surface starts reading old state, re-audit the writers at the new blast radius.**
  The continuation did not change the day the widget shipped — its consequences did. A bridge
  that carries data past a trust boundary (here: the phone's unlock) upgrades every latent race
  behind it, and the audit belongs to the bridge's pull request, not to luck.
