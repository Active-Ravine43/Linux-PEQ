# Product

## Register

brand

## Users

Linux audio power users — musicians, producers, streamers, and tinkerers who want per-application EQ control on PipeWire. They're at their desk, often in a dim room, focused on sound. They know what a parametric EQ is and expect precision. They live in the terminal and value keyboard-first workflows that don't waste keystrokes.

## Product Purpose

PEQ gives Linux users per-application 10-band parametric equalization with independent volume control, exposed through a Textual TUI. It exists because Linux audio routing is powerful but opaque — pw-cli and wpctl are not user interfaces. PEQ makes PipeWire filter chains discoverable and tweakable without leaving the terminal.

## Brand Personality

**Restrained, precise, editorial.** The TUI is the product, and the product is the brand. Not a tool wearing a theme — a designed object in its own right. Typographic hierarchy, deliberate restraint, and a single muted accent per theme variant. No ornament. Every pixel on the terminal grid earns its place.

The physical object: a precision audio console in a darkened control room. Not a guitar pedal, not a spaceship dashboard, not a spreadsheet.

## Anti-references

- **alsamixer / retro TUIs**: blocky ASCII, cyan-on-black defaults, arcane keybindings, 1990s terminal aesthetics
- **Overdesigned TUIs**: excessive color, gradients, decorative borders, "modern" terminal apps that fight the medium
- **Audio production clutter**: every control visible at once, labeled with 8-point text and cryptic abbreviations
- **SaaS dashboard transplants**: card grids, hero metrics, badge counts — web patterns that don't belong in a terminal

## Design Principles

1. **The terminal is the medium.** Work with the grid, not against it. 1px borders, block-element visualizers, terminal-native affordances.
2. **Show state, not decoration.** Mute visualizer animates because it conveys signal. Theme accent marks active selection because it orients the user. Nothing moves that doesn't mean something.
3. **Keyboard-first, mouse-optional.** Every action has a keybinding. Mouse is additive convenience, never the only path.
4. **Restraint reads as confidence.** Three theme variants, one accent each. Off-black canvas. No color that doesn't earn its role.

## Accessibility & Inclusion

- Keyboard navigation is primary — all functions reachable without a mouse
- High contrast between text (#d4d4d8) and canvas (#0d0d0f) for readability in dim environments
- Theme variants let users choose warm (amber), cool (slate), or neutral (mono) — accommodates preference and mild color vision differences
- Mute state uses both symbol (🔇) and color (#b84a4a red) — not color alone
- Respects terminal font size preferences — layout uses fr units, not fixed pixel widths
