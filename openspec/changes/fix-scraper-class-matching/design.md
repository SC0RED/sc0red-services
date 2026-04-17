## Context

The scraper's clutter-removal step uses `re.compile(cls, re.IGNORECASE)` with BeautifulSoup's `class_` parameter. This does a substring search across the entire class attribute string. A class token `"no-sidebar"` contains the substring `"sidebar"` → match → element removed.

## Goals / Non-Goals

**Goals:**
- Fix the false-positive class matching that strips content from sites with compound class names
- Preserve the intended behavior: elements with classes like `"sidebar"`, `"footer"`, `"nav"` are still removed

**Non-Goals:**
- Changing the list of clutter classes — the set is correct, only the matching logic is wrong

## Decisions

### Decision 1: Token-level matching via set intersection

**Decision**: iterate over all elements with `class_=True`, split their class attribute into individual tokens, lowercase them, and check for exact match against the clutter set using set intersection.

```python
_CLUTTER_CLASSES = {"nav", "footer", "header", "sidebar", "cookie", "popup"}
for el in soup.find_all(class_=True):
    if el.name in ("html", "body"):
        continue
    class_tokens = {c.lower() for c in el.get("class", [])}
    if class_tokens & _CLUTTER_CLASSES:
        el.decompose()
```

**Why**: BeautifulSoup's `el.get("class")` already returns a list of individual class tokens — no string splitting needed. Set intersection is O(1) per token. The `html`/`body` guard is belt-and-suspenders safety.

**Alternatives considered**:
- Word-boundary regex `r'\bsidebar\b'`: still matches inside `no-sidebar` because CSS classes are individual tokens (not hyphen-separated words in regex terms). `\b` treats `-` as a word boundary, so `\bsidebar\b` matches the `sidebar` part of `no-sidebar`.
- Only guard `html`/`body` from removal: fixes the immediate symptom but leaves the substring matching bug for other elements (a `<div class="no-sidebar-content">` would still be stripped).
