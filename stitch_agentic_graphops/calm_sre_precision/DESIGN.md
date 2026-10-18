---
name: Calm SRE Precision
colors:
  surface: '#101419'
  surface-dim: '#101419'
  surface-bright: '#36393f'
  surface-container-lowest: '#0a0e13'
  surface-container-low: '#181c21'
  surface-container: '#1c2025'
  surface-container-high: '#262a30'
  surface-container-highest: '#31353b'
  on-surface: '#e0e2ea'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#e0e2ea'
  inverse-on-surface: '#2d3136'
  outline: '#8c909f'
  outline-variant: '#424753'
  surface-tint: '#aec6ff'
  primary: '#aec6ff'
  on-primary: '#002e6a'
  primary-container: '#4e8eff'
  on-primary-container: '#00275d'
  inverse-primary: '#005ac3'
  secondary: '#4ae176'
  on-secondary: '#003915'
  secondary-container: '#00b954'
  on-secondary-container: '#004119'
  tertiary: '#f7be1d'
  on-tertiary: '#3f2e00'
  tertiary-container: '#b68a00'
  on-tertiary-container: '#372700'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#aec6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#6bff8f'
  secondary-fixed-dim: '#4ae176'
  on-secondary-fixed: '#002109'
  on-secondary-fixed-variant: '#005321'
  tertiary-fixed: '#ffdf9a'
  tertiary-fixed-dim: '#f7be1d'
  on-tertiary-fixed: '#251a00'
  on-tertiary-fixed-variant: '#5a4300'
  background: '#101419'
  on-background: '#e0e2ea'
  surface-variant: '#31353b'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: -0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  code-xs:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-lg: 1rem
  margin: 1rem
  margin-lg: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system targets Site Reliability Engineers, Platform Architects, and Incident Responders running critical mission-grade infrastructure under pressure. The emotional target is deep focus, calculated certainty, and low cognitive fatigue during high-stress operational workflows.

The visual style is rooted in dark, industrial minimalism fused with Swiss utility—prioritizing data density, razor-sharp alignment, and zero superfluous decoration. Layouts rely on flat planes, hairline dividers, and deliberate information zoning inspired by high-end engineering platforms. Visual hierarchy is achieved through precise typographic weight shifts, calibrated contrast steps, and purposeful status accents rather than heavy decorative treatments.

## Colors

The palette is engineered for prolonged operational monitoring in low-light environments, maximizing scannability while eliminating optical vibration:

- **Canvas Base (`#0E1217`):** The foundational viewport canvas providing deep, neutral immersion.
- **Surface Layer 1 (`#161C24`):** Primary panel, drawer, and card background.
- **Surface Layer 2 (`#1D2430`):** Interactive resting states, nested containers, and table headers.
- **Surface Layer 3 (`#252E3D`):** Active hovers, selected rows, and flyout menus.
- **Borders & Dividers (`#2A3340`):** Single-pixel perimeter framing that structures dense grid nodes.
- **Primary Text (`#E8EEF5`):** High-readability cool white for titles, values, and telemetry metrics.
- **Secondary Text (`#8E9AAB`):** Muted slate for metadata, labels, and timestamps.
- **Muted Text (`#5A6678`):** Low-priority descriptors, placeholders, and inactive states.
- **Electric Accent (`#4C8DFF`):** Focus triggers, active tabs, primary CTAs, and selected network nodes.
- **Operational Status Palette:**
  - **Healthy (`#22C55E`):** Stable services, passing SLOs, clean deploys.
  - **Degraded / Warning (`#EAB308`):** Elevated latency, non-paging anomalies, rate-limit warnings.
  - **Critical (`#EF4444`):** Node failure, breached error budgets, active P1/P0 incidents.

## Typography

Typographic scale is compressed to ensure dense technical efficiency across data-heavy operational dashboards. 

- **Primary UI (Inter):** Applied across all structural navigation, panel titles, modals, and narrative descriptions. Letter spacing is subtly tightened across larger sizes to maintain tension and precision.
- **Telemetry & Identity (JetBrains Mono):** Mandated for UUIDs, commit SHAs, latency metrics, IP addresses, trace IDs, and raw log rows. The strict tabular alignment ensures rapid column scanning without lateral drift.
- **Header Casing:** All field labels and operational metric titles use uppercase tracking (`label-sm`) with a 0.04em letter-spacing expansion for rapid peripheral recognition.

## Layout & Spacing

Layouts follow a desktop-first, highly condensed operational grid designed to maximize viewport utilization without clutter:

- **Grid Framework:** A 12-column variable fluid grid with a fixed 240px collapsable navigation rail and an optional 380px contextual inspector drawer on the right.
- **Rhythm & Increments:** Base scale adheres to strict 4px increments. Metric cards and data tables leverage condensed paddings (`space-sm` to `space-md`) to ensure high vertical density.
- **Responsiveness & Adaptability:** 
  - **Desktop Large (1440px+):** Full 3-column view: topology graph/metric cluster, incident feed, and real-time inspector pane.
  - **Desktop Compact (1024px–1439px):** Inspector drawer docks to an overlay sheet; graph canvases auto-reflow into prioritized vertical splits.
  - **Sub-1024px (Emergency Triage):** Rails collapse into a persistent quick-access drawer; operational lists switch to full-width stacked telemetry cards.

## Elevation & Depth

This system intentionally rejects diffused shadows and soft skeuomorphic blurs in favor of architectural surface layering:

- **Surface Tiers:** Depth is established by color-stepping. Canvas background sits at `#0E1217`, resting structural panels sit at `#161C24`, and floating menus or elevated modals sit at `#1D2430`.
- **Crisp Structural Strokes:** Every card, cell block, and panel is framed with an unyielding `1px solid #2A3340` boundary. Layering is conveyed through border overlap and tonal shift rather than optical elevation.
- **Floating Modals & Flyouts:** Command palettes (Cmd+K) and context menus utilize a strict directional drop: `0px 8px 24px rgba(0, 0, 0, 0.45)`, reinforced by the mandatory `1px solid #2A3340` perimeter border to separate them cleanly from the underlying operational canvas.
- **Interactive Focus States:** Active or focused panels swap their perimeter border from `#2A3340` directly to `#4C8DFF` with no blur halo.

## Shapes

The design system standardizes on a structural 12px outer radius for macro-level containers, balancing modern software refinement with technical austerity:

- **Primary Panels & Cards:** Fixed `12px` (`rounded-lg` level) border radius.
- **Interactive Controls (Buttons, Inputs, Selects):** Standardized at `6px` radius to maintain a crisp, clickable feel within dense panels.
- **Telemetry Chips, Badges, and Tags:** Styled with `4px` subtle radius for micro-elements, or fully circular pills (`9999px`) exclusively for live pulse dots and count indicators.
- **Dividers & Connectors:** Flat, unrounded 1px borders aligned strictly to pixel bounds.

## Components

### Buttons
- **Primary:** Background `#4C8DFF`, text `#FFFFFF`, font Inter 13px weight 500, height 32px, padding 0 12px, radius 6px. Hover: `#3A7AE8`. Active: `#2B68D1`.
- **Secondary:** Background `#1D2430`, border `1px solid #2A3340`, text `#E8EEF5`. Hover: background `#252E3D`, border color `#3B4758`.
- **Danger:** Background `rgba(239, 68, 68, 0.1)`, border `1px solid rgba(239, 68, 68, 0.3)`, text `#EF4444`. Hover: background `rgba(239, 68, 68, 0.2)`.

### Operational Status Badges & Chips
- Compact height (20px), radius 4px, font JetBrains Mono 11px uppercase.
- **Success:** Background `rgba(34, 197, 94, 0.1)`, border `1px solid rgba(34, 197, 94, 0.25)`, text `#22C55E`. Includes a 6px solid green indicator dot.
- **Warning:** Background `rgba(234, 179, 8, 0.1)`, border `1px solid rgba(234, 179, 8, 0.25)`, text `#EAB308`.
- **Critical:** Background `rgba(239, 68, 68, 0.12)`, border `1px solid rgba(239, 68, 68, 0.35)`, text `#EF4444`. Accompanied by a pulsing indicator dot.

### Inputs & Filters
- Background `#0E1217`, border `1px solid #2A3340`, radius 6px, height 32px, font Inter 13px, text `#E8EEF5`. Placeholder text `#5A6678`.
- Focus: Border `1px solid #4C8DFF`, outline none.
- Integrated keyboard shortcut hint displayed on the right: JetBrains Mono 10px `#8E9AAB` in a `#161C24` framed micro-capsule.

### Metric Cards & Data Tables
- **Cards:** Background `#161C24`, border `1px solid #2A3340`, radius 12px, padding 16px. Top micro-label in `label-sm` muted text; value rendered in 24px Inter semi-bold with monospace unit labels.
- **Data Tables:** Outer border `1px solid #2A3340`, header row background `#161C24`, height 32px, header text JetBrains Mono 11px uppercase `#8E9AAB`. Rows: height 36px, background `#0E1217`, alternating hover state `#161C24`, border-bottom `1px solid #1D2430`.

### Node Graph & Topology Elements
- Graph canvas rendered against background `#0E1217` with subtle `#1D2430` dot-matrix grid at 16px intervals.
- Service Nodes: Container radius 8px, background `#161C24`, border `1px solid #2A3340`. Status color stripe (3px) placed along the left vertical edge.
- Connectors: 1.5px stroke with `#2A3340` for idle links, dynamic animated dash-flow in `#4C8DFF` for active RPC traffic, and `#EF4444` for degraded links.