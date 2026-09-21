import unittest

from checker import check_entries, parse_entries, present_fields


class JournalCheckerTests(unittest.TestCase):
    def test_normal_complete_entry(self):
        text = """## 1. Example
**Symptom.** Something broke.

**Root cause.** `a.py:1` had the bug.

**What misled us.** The log looked fine.

**The rule.** Verify the state you care about.

**Detect it again.** Run `grep thing`.
"""
        [(entry, missing)] = check_entries(parse_entries(text))
        self.assertEqual([], missing)

    def test_plural_rules_is_accepted(self):
        text = """## 1. Example
**Symptom.** Something broke.
**Root cause.** A cause.
**What misled us.** A misleading clue.
**The rules.**
- Rule one.
**Detect it again.** Ask a question.
"""
        [(entry, missing)] = check_entries(parse_entries(text))
        self.assertNotIn("The rule", missing)

    def test_why_it_was_hard_to_see_alias(self):
        text = """## 1. Example
**Symptom.** Something broke.
**Root cause.** A cause.
**Why it was hard to see.** A misleading clue.
**The rule.** A rule.
**Detect it again.** Ask a question.
"""
        [(entry, missing)] = check_entries(parse_entries(text))
        self.assertNotIn("What misled us", missing)

    def test_narrative_style_can_supply_symptom_and_root_cause(self):
        text = """## 25. Narrative example
*2026-08-11 · frontend*

The user saw the old account's information after signing into a different account, and the problem only appeared after a delayed response completed during a session change.

The service lived longer than the session, so an awaited response issued for one account could land after another account had signed in and overwrite shared state.

**Why it was hard to see.** It needed a sign-out and sign-in while the request was in flight.

**The rules.**
- Re-check the account after every await.
"""
        [(entry, missing)] = check_entries(parse_entries(text))
        self.assertNotIn("Symptom", missing)
        self.assertNotIn("Root cause", missing)
        self.assertIn("Detect it again", missing)

    def test_missing_detector_is_flagged(self):
        text = """## 1. Example
**Symptom.** Something broke.
**Root cause.** A cause.
**What misled us.** A misleading clue.
**The rule.** A rule.
"""
        [(entry, missing)] = check_entries(parse_entries(text))
        self.assertEqual(["Detect it again"], missing)


if __name__ == "__main__":
    unittest.main()
