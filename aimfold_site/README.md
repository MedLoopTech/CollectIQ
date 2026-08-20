# Aimfold brand site

The **Aimfold** brand identity — kept deliberately separate from
`01_landing_intake`/`04_reviewer_dashboard` (the CollectIQ pilot's own
branded site), per the same architectural principle the rest of this
repo follows: CollectIQ is one Aim running on the Aimfold engine, not
the platform itself, so its brand shouldn't be reused as the platform's
brand either.

## What's here

`index.html` — a single, self-contained brand/landing page (no build
step, no dependencies beyond Google Fonts for Inter), covering:

- The logo mark (converging-signal-lines SVG, built from the brand
  board — no exported asset files were provided, so this is a
  from-scratch recreation, not a pixel-exact reproduction)
- Color palette: `#0B0F19` (ink), `#4B5563` (slate), `#E5E7EB` (border),
  `#F7F8FA` (background), `#2563EB` (blue) — used as CSS custom
  properties in `:root`
- Typography: Inter (400/500/600/700/800)
- Full rewrite of the copy to the generic "Opportunity Intelligence"
  positioning (not the AR/collections-specific copy `01_landing_intake`
  uses) — tagline, story, the 7-step Aimfold Flow, and the 6 use cases,
  matching the brand board
- A static, illustrative product-preview card (not a live UI — the real
  functional equivalent is `aimfold_core/inbox/index.html`, a separate,
  unstyled-for-now surface not touched by this rebrand)

## What this isn't

- Not deployed anywhere yet — no Netlify site exists for this directory
  the way `01_landing_intake`/`04_reviewer_dashboard` have one.
- Not wired to any backend — the "Request early access" CTA is a
  `mailto:` link, not a form that writes anywhere; there's no signup
  flow or database behind this page.
- Not a reskin of `aimfold_core/inbox/`'s actual Opportunity Inbox UI —
  that's a working application surface with real Supabase queries; this
  is marketing/brand identity only. Restyling the Inbox UI to match this
  palette is a natural, separate follow-up, not done here.

## Verified how

Opened in the Browser tool (`get_page_text`, console-error check, and
`getComputedStyle()` assertions on font-family/colors/grid-template-columns)
at both desktop (1280px) and mobile (375px) widths — confirmed no
horizontal overflow, correct 7-column→2-column flow-step grid and
3-column→1-column use-case grid collapse, and the nav links correctly
hiding under the mobile breakpoint. Not just written and assumed to work.
