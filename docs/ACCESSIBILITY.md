# EventGenie Accessibility & WCAG 2.1 Compliance

EventGenie is designed to be accessible to all users, adhering to **WCAG 2.1 Level AA** standards. All color palettes, interactive widgets, focus states, and typography are engineered and verified through automated regression tests.

---

## 1. Color Contrast Ratios (WCAG 2.1 AA & AAA)

Every foreground/background color pair in the design system is mathematically validated using the standard W3C relative luminance formula:

$$\text{Contrast Ratio} = \frac{L_1 + 0.05}{L_2 + 0.05}$$

| UI Element | Foreground | Background | Measured Ratio | WCAG Requirement | Status |
|---|---|---|---|---|---|
| **Headings & Brand Title** | `#2D1B4E` (Plum) | `#FBF7F0` (Ivory) | **14.13:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Body Text** | `#3D2E5C` (Muted Plum) | `#FBF7F0` (Ivory) | **11.31:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Secondary Labels** | `#6B5B8A` (Light Plum) | `#FBF7F0` (Ivory) | **5.65:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AA) |
| **Card / Input Content** | `#2D1B4E` (Plum) | `#FFFFFF` (White) | **15.11:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Primary Buttons (Saffron)** | `#1C1235` (Ink) | `#F5A623` (Saffron) | **8.50:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Primary Button Text (Plum)** | `#2D1B4E` (Plum) | `#F5A623` (Saffron) | **7.44:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Secondary Buttons (White)** | `#2D1B4E` (Plum) | `#FFFFFF` (White) | **15.11:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Footer Headings** | `#F5F0EB` (Ivory) | `#1C1235` (Deep Ink) | **15.12:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Footer Links** | `#B8A9D4` (Lavender) | `#1C1235` (Deep Ink) | **7.86:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Info Alert Text** | `#1E40AF` (Deep Navy) | `#EFF6FF` (Ice Blue) | **8.56:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Warning Alert Text** | `#92400E` (Deep Amber) | `#FEF3C7` (Warm Amber) | **6.85:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AA) |
| **Success Alert Text** | `#065F46` (Deep Emerald)| `#ECFDF5` (Mint) | **7.43:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **Error Alert Text** | `#991B1B` (Deep Crimson)| `#FEF2F2` (Soft Rose) | **9.43:1** | $\ge 4.5:1$ (AA) | ✅ PASS (AAA) |
| **UI Form Borders** | `#8C7B65` (Warm Border) | `#FBF7F0` (Ivory) | **3.81:1** | $\ge 3.0:1$ (UI) | ✅ PASS (AA) |
| **White on Gold (Prohibited)** | `#FFFFFF` | `#F5A623` | **2.03:1** | $\ge 4.5:1$ (FAIL) | ❌ Disallowed |

---

## 2. Accessibility Engineering Features

### 1. Forced Light Theme (`.streamlit/config.toml`)
- Prevents operating systems in Dark Mode from inverting or darkening form controls against the light ivory landing page.
- Ensures all inputs remain dark plum text on white backgrounds across all operating systems.

### 2. Keyboard Navigation & Focus Visibility
- **Skip-to-Content Link:** Positioned off-screen (`left: -9999px`) until focused via keyboard (`Tab`), immediately snapping to the top left with a high-contrast outline (`3px solid var(--text-heading)`).
- **Sticky Nav Offset (`scroll-margin-top: 80px`):** Guarantees anchor navigation targets (`#home`, `#how-it-works`, `#sample-preview`, `#planner-section`, `#about`) are never obscured beneath the 60px fixed navigation bar.
- **Focus Rings:** All buttons, form fields, and interactive links have visible focus indicators (`outline: 2px solid var(--accent-gold-bg)` with `outline-offset: 2px`).

### 3. Touch Targets (WCAG 2.5.5)
- All buttons, including Quick Demo cards, primary actions, and submit buttons, enforce a minimum height of **44px** (`min-height: 44px !important`).

### 4. Non-Color-Only Indicators (WCAG 1.4.1)
- Form statuses, budget checks, and warning notices use dual representations: an explicit icon (e.g. ⚠️, ⚡, 🤖, 📋) combined with clear text labels (e.g., `Warning: Caution`, `Verified: Math Checks Out`, `Benchmark Fallback`). Color is never the sole information carrier.

### 5. Multilingual Indic Font Stacks
- Font stacks include native glyph fallbacks for Indic scripts:
  `'Playfair Display', 'Noto Sans Devanagari', 'Noto Sans Kannada', 'Noto Sans Telugu', 'Noto Sans Tamil', Georgia, serif`
- Eliminates missing-glyph replacement characters ("tofu" boxes) across all 6 supported languages (English, Hindi, Kannada, Telugu, Tamil, Marathi).
