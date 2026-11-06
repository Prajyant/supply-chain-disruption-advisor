---
inclusion: auto
name: design-taste-frontend
description: Apply professional frontend design taste to all UI work — components, pages, layouts, styling. Use whenever building, redesigning or polishing any frontend.
---

# tasteskill 2.5 — Design Taste for Frontend Work

> Source: https://github.com/Leonxlnx/taste-skill  
> Applied to: Supply Chain Disruption Advisor (React + TypeScript + TailwindCSS, software/tech page kind)

This project is classified as **software / tech** (a SaaS supply chain intelligence platform). Apply the rules below to every frontend task.

---

## House Rules (these override everything)

1. **No caption or description under any image or visual.** No label explaining what a chart shows inline — let the data speak.
2. **Every visual renders** — no empty containers, no skeleton placeholders left in production, no broken chart states without a fallback.
3. **One idea per section / card.** A risk card shows one risk. A stat tile shows one number. Never pack two unrelated ideas into one component.
4. **Equal left and right content edges.** Every panel, table, card grid and form aligns to the same content edge. No element bleeds to one side only.
5. **Hover micro-animations:** linked cards lift 2 px (`translateY(-2px)`), buttons step on hover and depress on click, icon buttons scale to 1.05. No tilt, no carousel auto-play, no timed tabs.
6. **Real data, real UI.** No placeholder text (`Lorem ipsum`, `Sample supplier`, `---`). Use the actual shipment IDs, supplier names, route strings from the API. Fall back to a named empty state, never invisible silence.
7. **Real icons in their own colours.** Use Lucide React icons as-is — never redraw or recolour brand icons. AWS, shipping line and country flags keep their real palette.
8. **Shader / animation effects only on tech sections.** Live route maps, AIS vessel trails, risk propagation graphs and the digital twin graph may use animation. Static summary cards, CFO tables and settings pages stay calm — flat colour, no animation beyond hover.
9. **No invented data.** Never hard-code fake shipment values, fake risk scores or fake supplier names to make a UI look populated. Show the empty state.

---

## Page Kind: Software / Tech

This is a **software** product (SaaS dashboard). Apply the tech rules:

- Dark background (`slate-950`) is correct. Keep it.
- Accent colour: `primary-600` (indigo). **Never violet or lavender as a new accent.**
- One button style per context: primary CTA = filled `primary-600`, secondary = `slate-800` outlined. Never mix more than two button shapes on one page.
- One card family: `bg-slate-900 border border-slate-800 rounded-xl`. Never introduce a second card style (e.g. white cards, gradient cards) without removing the old one.
- One radius scale: `rounded-lg` for inputs/badges, `rounded-xl` for cards, `rounded-full` for avatars/status dots. Never mix.
- One heading scale: the existing Tailwind type scale. Never add a second font family.

---

## Layout Rules

- **One section per screen on full-page views.** Dashboard, Digital Twin, Vessel Tracking — each major panel fills its visible area. No second panel heading peeking in above the fold.
- **Equal edges.** All page content sits inside a consistent horizontal padding (`px-6` or `px-8`). No component pokes out to one side.
- **Splits stack text first on mobile** — at `< 768 px` all two-column layouts go single column, text above visual.
- **Sidebar width is fixed.** Content area is `flex-1`. Never let the sidebar grow into the content.

---

## Component Rules

### Cards
- Use `bg-slate-900 border border-slate-800 rounded-xl p-6` — the project's existing `.card` class.
- Hover: `hover:-translate-y-0.5 hover:border-slate-700 transition-all duration-150`.
- Clickable cards get `cursor-pointer` and a visible focus ring.
- One card family. If a new variant is needed, extend via a modifier class, not a whole new design.

### Data Tables
- Header row: `bg-slate-800/50 text-slate-400 text-xs uppercase tracking-wide`.
- Rows: `border-b border-slate-800 hover:bg-slate-800/30`.
- Numeric columns right-aligned. Text columns left-aligned.
- Empty state: a centred message + icon, never an empty `<tbody>`.

### Status Badges
- Use the existing `.status-badge` class.
- Colour map: `critical/high` → red-500, `medium` → amber-500, `low` → emerald-500, `info` → blue-500, `unknown` → slate-500.
- Never invent new colours for statuses.

### Charts (Recharts)
- Background: transparent (inherits `slate-900`).
- Grid lines: `stroke="#1e293b"` (slate-800).
- Tooltip: `bg-slate-800 border-slate-700 text-slate-100`.
- Legend text: `text-slate-400 text-xs`.
- No chart renders with dummy data — always wire to real API state.

### Maps (Leaflet)
- Tile layer: OpenStreetMap with `.map-tiles-dark` CSS filter (already applied).
- Map background matches dark theme: `background: #0f172a`.
- Danger zones: semi-transparent red polygon, no fill label.
- Vessel markers: coloured circles matching the status palette above.

### Forms & Inputs
- Use the existing `.input` class: `bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-4 py-2`.
- Validation errors in `text-red-400 text-sm mt-1`.
- Labels: `text-slate-400 text-sm mb-1 block`.

### Empty States
- Every list, table and chart that can be empty needs an explicit empty state.
- Structure: centred icon (`text-slate-600 w-12 h-12`) + heading (`text-slate-400`) + optional action button.
- Never leave an empty container — it looks broken.

### Loading States
- Use the existing `animate-pulse` skeleton pattern (`bg-slate-800 rounded animate-pulse`).
- Skeletons match the shape of the real content (card skeleton = card-shaped block).
- Spinners only for action feedback (button submitting). Never a full-page spinner.

---

## Motion Rules

- **Hover only.** Cards lift 2 px, buttons depress, icon buttons scale. Nothing else moves on hover.
- **No scroll-triggered reveals, no fade-ins, no parallax.**
- **No auto-playing carousels.** Tabs are user-controlled only.
- **Transitions:** `duration-150` for hover state changes, `duration-300` for panel open/close. Never `duration-700+` on interactive elements.
- **Reduced motion:** wrap animation utilities in `motion-safe:` Tailwind prefix or check `prefers-reduced-motion` in JS.
- **The AIS vessel map and Digital Twin graph** may animate continuously — they are live data visuals (tech rule). All other pages stay still except hover.

---

## Copy Rules

- **Headings name things.** "Active Risks" not "Overview". "Shipments in Transit" not "Status".
- **Buttons are verb + object.** "View Details", "Export CSV", "Run Analysis" — never just "Click here" or "Submit".
- **Numbers are specific.** Show `12 shipments` not `several shipments`. Show `$2.4M` not `high value`.
- **No placeholder copy in production.** No "Coming soon", no "TODO", no "Sample data".
- **Stat tiles:** number large, label below in `text-slate-400 text-sm`, unit inline with the number (`$2.4M`, `94%`, `3 critical`).

---

## Colour Palette

| Token | Hex | Use |
|---|---|---|
| `slate-950` | `#020617` | Page background |
| `slate-900` | `#0f172a` | Card background |
| `slate-800` | `#1e293b` | Input, row hover, divider |
| `slate-700` | `#334155` | Border, subtle line |
| `slate-400` | `#94a3b8` | Secondary text, labels |
| `slate-100` | `#f1f5f9` | Primary text |
| `primary-600` | `#4f46e5` | Primary action, accent |
| `primary-500` | `#6366f1` | Hover state of primary |
| `red-500` | `#ef4444` | Critical risk, error |
| `amber-500` | `#f59e0b` | Medium risk, warning |
| `emerald-500` | `#10b981` | Low risk, success |
| `blue-500` | `#3b82f6` | Info, in-transit |

Never introduce new colours. Extend using opacity modifiers (`red-500/20` for a soft background).

---

## Never (hard stops)

- Violet or lavender as a design accent colour (real third-party logos keep their own colours).
- Stock photographs passed off as real supplier locations or facilities.
- Invented risk scores, shipment values or supplier names to make a UI look populated.
- Scroll-triggered animations, parallax, tilt effects.
- A second card style, a second button shape, a second font family introduced without replacing the first.
- Copying layout or visual style directly from another SaaS product.
- Empty containers with no fallback state.
