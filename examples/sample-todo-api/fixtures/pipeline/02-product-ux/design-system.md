# Design System — Todo API Developer Portal

> Applies to any reference UI, developer portal, or documentation site built on top of the
> Todo API. The API itself is headless; these tokens standardise any accompanying UI.

---

## Design Tokens

```css
:root {
  /* Color palette */
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  --color-success: #16a34a;
  --color-warning: #d97706;
  --color-error: #dc2626;
  --color-surface: #ffffff;
  --color-surface-alt: #f8fafc;
  --color-border: #e2e8f0;
  --color-text: #0f172a;
  --color-text-muted: #64748b;

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-bold: 700;

  /* Spacing */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --space-12: 3rem;

  /* Radius */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px rgb(0 0 0 / 0.07);
}
```

---

## Component Specs

### Component: Button

Variants: `primary`, `secondary`, `danger`, `ghost`  
Sizes: `sm` (32px), `md` (40px), `lg` (48px)  
States: default, hover (brightness 90%), focus (2px ring in `--color-primary`),
disabled (opacity 0.5, cursor not-allowed)

### Component: Input

Single-line text input with optional prefix/suffix slot.  
Border: 1px solid `--color-border`; focus: 2px solid `--color-primary`  
Error state: border `--color-error` + error message below in `--font-size-sm`

### Component: Badge

Inline status indicator.  
Colors mapped: open → `--color-primary`; done → `--color-success`; overdue → `--color-error`

### Component: CodeBlock

Syntax-highlighted code snippet with copy button.  
Font: `--font-mono`; background: `--color-surface-alt`; padding: `--space-4`

---

## Accessibility (WCAG 2.1 AA)

- All interactive elements meet 4.5:1 color contrast ratio against backgrounds
- Focus indicators visible at all zoom levels (no `outline: none` without replacement)
- Error messages associated with inputs via `aria-describedby`
- Loading states announced via `aria-live="polite"`
- Keyboard navigation: Tab order follows visual reading order

Accessibility review is required before any documentation site ships.
