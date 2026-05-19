# sc0red Services — design tokens (visual audit reference)

Extracted from `development.sc0red.com` on 2026-05-19. Per OQ §8 of the
[`rename-janus-to-sc0red-services`](../openspec/changes/rename-janus-to-sc0red-services/proposal.md)
change, this is a **visual audit**, not a Figma extraction — values are
inspected from the live site's compiled CSS and may differ slightly
from the original design source.

## Colour palette

| Token (on company site) | Value          | Use                                  |
|-------------------------|----------------|--------------------------------------|
| `sc0red-blue`           | `#3A77FF`      | Primary action button, accent text   |
| `vector-blue-deep`      | `#2563EB`      | Hover state for primary actions      |
| (mark fill — green)     | `#05BF7B`      | One stripe of the Advisory mark SVG  |
| (mark fill — blue)      | `#2475F5`      | One stripe of the Advisory mark SVG  |
| (mark fill — white)     | `#FFFFFF`      | One stripe of the Advisory mark SVG  |

> The `vector-blue-deep` class name is a legacy artifact in the company site's
> Tailwind config (left over from when the team explored "Vector" naming). The
> value `#2563EB` is canonical regardless of the class name.

## Typography

| Token  | Family                       | Source                                |
|--------|------------------------------|---------------------------------------|
| Display| `Inter Tight`                | Loaded via web font on the site       |
| Body   | `InterVariable`              | Self-hosted `/fonts/InterVariable.woff2` |
| Mono   | `ui-monospace, SFMono-Regular, Menlo, Monaco, ...` | System monospace stack |

## Logo asset

- File: `frontend/public/sc0red-services-logo.svg`
- Source: `https://development.sc0red.com/images/advisory/advisory-mark-on-ink.svg`
- Variant: "mark on ink" — designed to sit on dark backgrounds (Janus's default theme).
- Dimensions: 128×128 viewBox.
- Three coloured paths (green / blue / white triangles) forming the Advisory mark.

## Mapping to Janus's existing tokens

Janus's current accent in `globals.css`:
- `--accent-blue` ≈ `#3b82f6` (Tailwind blue-500 ish)
- `--accent-blue-glow` ≈ derived from accent-blue

After alignment:
- `--accent-blue` → `#3A77FF` (matches sc0red-blue)
- `--accent-blue-glow` → derived from new accent
- Hover/active states that previously used `#2563eb` (vector-blue-deep)
  are already aligned.

## What's out of scope for this visual audit

- Component-by-component restyle. Tokens move; components keep their layout.
- Custom font swap. Janus already uses Inter; the variants are compatible.
- Dark-vs-light theme rewrites. The Advisory mark is on-ink (dark-bg) — fine
  for Janus's default dark theme.
