# AMR Operator Mission Control — Design QA

## Comparison target

- Source visual truth: `/home/shanto/Downloads/AMR_UI_Concepts/3_Mission_Control.png`
- Rendered implementation: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_final_dashboard.png`
- Parameter focus state: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_parameter_focused.png`
- Light-theme verification: `/home/shanto/Downloads/AMR_UI_Concepts/amr_operator_light_offscreen.png`
- Full-view comparison: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_side_by_side.png`
- Focused robot-stack comparison: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_stack_side_by_side.png`
- Compact-workspace implementation: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_compact_workspace.png`
- Spacing before/after comparison: `/home/shanto/Downloads/AMR_UI_Concepts/mission_control_spacing_before_after.png`

## Capture normalization

- Source pixels: 1487 × 1058 at device density 1.
- Implementation pixels and Qt viewport: 1440 × 900 at device density 1.
- Full-view normalization: the source was scaled proportionally to 1440 × 1025 and top-cropped to 1440 × 900. The implementation was not scaled.
- State: dark theme, connection ribbon visible, settings collapsed, robot stack stopped. The source shows a running Bringup process while the implementation reflects the real stopped state; this is an intentional live-data difference.
- Focused comparison: the Robot Stack panels were cropped independently and placed together at equal visual height so typography, columns, controls, and row rhythm could be inspected.

## Primary interactions checked

- Wi-Fi SSH status updates from the live development-machine keyring.
- Settings expansion and dashboard collapse behavior.
- Parameter Tuning tab selection and full-workspace **Focus tuning** mode.
- Returning from Parameter Tuning restores the operations dashboard.
- Dark and light theme rendering.
- Enabled, disabled, start, stop, and action button states.
- Parameter YAML loading, section grouping, comments, value editors, and restart actions.
- Existing automated GUI/support checks: 77 passed.
- No Qt runtime errors were emitted during capture. Network and ROS process logs remain available through their existing tabs.

## Required fidelity surfaces

- **Fonts and typography:** Noto Sans/DejaVu Sans fallback, 10.5-point application text, clear 11-point panel/table headings, and 11-point Parameter Tuning rows preserve the reference hierarchy while improving readability. Long live-state labels wrap rather than overlap.
- **Spacing and layout rhythm:** the header, connection ribbon, two-column operations area, vertical splitter, and diagnostics tabs match the reference composition. Start and stop actions align in fixed table columns; the parameter table can take the full workspace when needed.
- **Colors and tokens:** the implementation uses the reference's near-black navy surfaces, cool blue actions, green running states, neutral disabled states, and isolated red destructive controls. The light theme uses a restrained white/gray palette with the same semantic colors and sufficient contrast.
- **Image quality and assets:** the packaged AMR application mark is rendered from its existing vector source. The VS Code button uses the installed official VS Code icon. Other controls use system theme or Qt standard icons; no placeholder imagery or handcrafted SVG/CSS art was added.
- **Copy and content:** labels describe actual AMR operations and dependencies. Bringup intentionally no longer displays the map selector; the map remains correctly scoped to Localization. Destructive dependency-aware behavior is stated in the Robot Stack description and button tooltips.
- **Accessibility and resilience:** buttons retain text labels in addition to icons, focus borders are visible, settings and tuning focus modes are keyboard-reachable, text zoom remains available for logs, and the 1120 × 720 minimum window prevents unusable collapse. At 1440 × 900, controls remain visible without horizontal application scrolling.

## Comparison history

### Iteration 1

- [P2] Robot-stack state labels and stop buttons clipped at 1440 × 900.
  - Fix: enabled state-label wrapping, shortened unambiguous row-level stop labels, widened the map selector, and reduced the stop column's minimum width.
- [P2] Mapping name and three actions were cramped in the right panel.
  - Fix: moved the map name to its own labeled row and kept mapping actions aligned beneath it.
- [P2] Parameter Tuning exposed only one group row at the default splitter size.
  - Fix: added **Focus tuning**, which temporarily hides the dashboard and exposes many readable 46-pixel parameter rows with full-width comments and actions.

### Iteration 2

- Post-fix evidence: `mission_control_final_dashboard.png`, `mission_control_parameter_focused.png`, and `mission_control_stack_side_by_side.png`.
- The earlier clipping and parameter-workspace issues are no longer present.
- No actionable P0, P1, or P2 findings remain.

### Iteration 3 — workspace density

- [P2] At a maximized desktop size, the Robot Stack grid distributed surplus
  height above and between its rows while the Tools panel held an empty lower
  region. This reduced the useful Activity & Diagnostics workspace.
  - Fix: stopped the stack table and Tools layout from absorbing surplus
    vertical height, changed the vertical splitter so the operations area keeps
    its content-sized height, and assigned remaining height to diagnostics.
  - Post-fix evidence: `mission_control_compact_workspace.png` and
    `mission_control_spacing_before_after.png` show compact stack rows, no
    unused Tools footer, and a materially larger diagnostics pane.
- No controls clip or overlap at 1440 × 900 after the density change.

## Follow-up polish

- [P3] A future pass could add a compact “last checked” timestamp to the connection ribbon, matching the source more literally. The current live route states already communicate the operational result, so this does not block use.
- [P3] Icon appearance varies slightly with the Linux desktop icon theme. The important VS Code and application icons use their real assets; generic actions deliberately follow the host theme.

## Final result

final result: passed
