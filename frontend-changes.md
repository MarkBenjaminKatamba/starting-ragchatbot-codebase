# Frontend Changes: Light/Dark Theme Toggle

## Summary
Added an icon-based theme toggle button fixed in the top-right corner. It switches between the existing dark theme and a new light theme, with a smooth animation, and is fully keyboard accessible.

## Files changed

### `frontend/index.html`
- Added `<button id="themeToggle" class="theme-toggle">` at the top of `<body>` containing sun and moon inline SVG icons (`aria-hidden`). The button carries a dynamic `aria-label` ("Switch to light theme" / "Switch to dark theme") and a `title`.
- Added a small inline script in `<head>` that sets `data-theme` on `<html>` before first paint (saved choice from `localStorage`, otherwise the OS `prefers-color-scheme`, otherwise dark). This prevents a flash of the wrong theme.
- Bumped asset cache-busting versions to `?v=10`.

### `frontend/style.css`
- Added `:root[data-theme="light"]` overrides for the existing CSS variables (background, surface, text, border, assistant message, welcome box, links, shadow, focus ring). Dark remains the default `:root`.
- Introduced new variables (`--code-bg`, `--error-*`, `--success-*`) and replaced hard-coded colours (code blocks, error/success messages) so they adapt to both themes. Added `color-scheme` so native controls/scrollbars match.
- Added `.theme-toggle` styles: 44px circular button, `position: fixed; top: 1rem; right: 1rem`, using the same surface/border/shadow variables as the rest of the UI, with hover, active and `:focus-visible` (focus ring) states.
- Icon animation: the sun and moon are stacked and cross-fade with a rotate/scale transition (0.5s).
- Smooth theme transition: a temporary `html.theme-transition` class applies 0.35s transitions to background, text, border and shadow colours across the page. It is only active during a toggle, so normal hover/focus behaviour is unaffected.
- `prefers-reduced-motion` disables the animations.

### `frontend/script.js`
- Added `setupThemeToggle()` (called on `DOMContentLoaded`): toggles `data-theme` on `<html>`, persists the choice to `localStorage` (wrapped in try/catch), updates the button's `aria-label`, and adds/removes `theme-transition` around the switch.

## Accessibility / keyboard
- Native `<button type="button">`, so it is focusable via Tab and activates with Enter/Space.
- Visible focus ring via `:focus-visible`; the label reflects the action the button will perform.

## Verification
Checked in a browser: Tab focuses the button, Enter toggles the theme, the icon swaps, the `aria-label` updates, and the choice persists in `localStorage`. Both themes render correctly. Screenshots confirmed layout and contrast.

---

# Frontend Changes: Light Theme Refinement (accessibility pass)

Builds on the toggle above: the light theme is now a tuned, WCAG-checked palette rather than a simple inversion. Only `frontend/style.css` changed.

## Light palette (`:root[data-theme="light"]`)
| Token | Value | Notes |
|---|---|---|
| `--background` | `#f8fafc` | Light page background |
| `--surface` | `#ffffff` | Sidebar, inputs, cards |
| `--surface-hover` | `#e2e8f0` | Hover state |
| `--text-primary` | `#0f172a` | 17.1:1 on background, 17.9:1 on surface |
| `--text-secondary` | `#475569` | 7.2-7.6:1 on background/surface, 6.5:1 on assistant bubble |
| `--primary-color` / `--user-message` | `#1d4ed8` | Darkened from `#2563eb`; 6.7:1 white-on-primary and primary-on-white |
| `--primary-hover` / `--link-hover` | `#1e40af` | 8.7:1 on white |
| `--link-color` | `#1d4ed8` | 5.5-6.4:1 on all light backgrounds |
| `--assistant-message` | `#e8eef6` | 15.3:1 with primary text |
| `--welcome-bg` | `#dbeafe` | 14.6:1 with primary text |
| `--border-color` | `#cbd5e1` | Decorative dividers/cards |
| `--border-strong` | `#7a8ba3` | New; about 3:1 for interactive control outlines (WCAG 1.4.11) |
| `--error-text` / `--success-text` | `#b91c1c` / `#166534` | 5.8:1 / 6.7:1 on their tinted backgrounds |
| `--focus-ring` | `rgba(29,78,216,.3)` | Visible keyboard focus |

## Supporting changes
- New `--border-strong` token (equal to `--border-color` in dark, so dark is visually unchanged), used on the chat input, suggested-question buttons and the theme toggle so their outlines meet 3:1 in light mode.
- New `--welcome-shadow` token so the welcome card shadow is softer in light mode.
- Fixed `.message-content blockquote`, which referenced an undefined `--primary` variable; it now uses `--primary-color`. As a side effect the blockquote accent bar is now also visible in the dark theme.

## Verification
Contrast ratios were computed from the palette and re-measured from computed styles in the browser (user bubble 6.7:1, assistant 17.9:1, suggested buttons 16.3:1, sidebar headers 8.2:1). Visually checked with sample user/assistant messages, links, code, blockquote, error and success states in light mode.

---

# Frontend Changes: Theme Implementation Requirements Audit

Request (from screenshot): JavaScript functionality (toggle on click, smooth transitions) and implementation details (CSS custom properties, `data-theme` attribute on `<html>`/`<body>`, all existing elements work in both themes, keep visual hierarchy and design language). No code changes were needed; the earlier work already covers each point:

| Requirement | Where it is met |
|---|---|
| Toggle themes on button click | `setupThemeToggle()` in `frontend/script.js` |
| Smooth transitions between themes | `html.theme-transition` rule plus icon rotate/fade in `frontend/style.css` (disabled for `prefers-reduced-motion`) |
| CSS custom properties for theme switching | `:root` (dark) and `:root[data-theme="light"]` variable sets in `frontend/style.css` |
| `data-theme` attribute on html element | Set pre-paint by the inline script in `frontend/index.html`, then by the toggle |
| All existing elements work in both themes | Audited every colour literal in `style.css`. Remaining literals are intentional: `color: white` on primary-blue buttons/bubbles (6.7:1 in light, 5.2:1 in dark), the send-button hover glow, and a gradient on the header title, which is `display: none`. Everything else uses variables |
| Maintain visual hierarchy and design language | Same layout, spacing, radii and component styles; only colour tokens differ |
