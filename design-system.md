> Standalone web repository: Section 12 documents the active responsive web design. Earlier Flutter mappings describe the source project. See [SOURCE.md](SOURCE.md) for extraction history.

# SDU Campus Assistant Design System

**Version:** 1.0
**Platform:** Responsive React web application; historical mobile guidance retained below
**Design language:** SDU institutional identity with Material 3 foundations
**Status:** Implemented course-project design system

## 1. Purpose

This design system keeps the SDU Campus Assistant visually consistent, easy to navigate, and suitable for students, teachers, administrators, and campus visitors. The interactive campus map is the centre of the product; supporting screens should help users return to a location or route with as little friction as possible.

The system is based on five principles:

1. **Map first:** location discovery and navigation remain the primary experience.
2. **Clear hierarchy:** each screen has one obvious primary action.
3. **Role aware:** personal and administrative actions appear only when the current role permits them.
4. **Accessible by default:** readable contrast, large touch targets, and step-free route information are always considered.
5. **SDU branded:** navy, blue, gold, and the official 30th-anniversary mark establish the visual identity.

## 2. Brand assets

| Asset | Usage | Repository path |
|---|---|---|
| SDU 30th-anniversary logo | Welcome and authentication branding | `assets/images/sdu_30_logo.png` |
| SDU campus map | Interactive map background | `assets/images/campus_map.jpg` |

### Logo rules

- Preserve the original proportions; never stretch or skew the logo.
- Place it on a light, uncluttered background.
- Keep clear space around it equal to at least one quarter of its displayed width.
- Do not recolour, add shadows, or place other elements over it.
- Use the anniversary logo for the course-project release; it can later be replaced without changing the screen layout.

## 3. Colour system

### Core colours

| Token | Hex | Flutter token | Primary use |
|---|---:|---|---|
| SDU Navy | `#101A4D` | `AppColors.navy` | Headings, identity, active navigation, high-emphasis surfaces |
| Action Blue | `#156DE5` | `AppColors.blue` | Primary buttons, links, selected map pins, focused inputs |
| Anniversary Gold | `#D5A14A` | `AppColors.gold` | Saved-place state and restrained brand accents |
| Canvas | `#F5F7FC` | `AppColors.background` | Application background |
| Ink | `#111827` | `AppColors.ink` | Primary body text |
| Muted | `#68708A` | `AppColors.muted` | Secondary text, supporting icons, metadata |
| Surface | `#FFFFFF` | Material surface | Cards, sheets, fields, navigation surfaces |

### Supporting colours

| Token | Hex | Use |
|---|---:|---|
| Pale Blue | `#E4EEFF` | Icon containers, numbered route steps, selection support |
| Role Blue | `#DDE9FF` | Role chip background |
| Navy Surface | `#314079` | Icon containers on navy cards |
| Navy Muted | `#BCC6E7` | Secondary text on navy cards |
| Border | `#E4E8F2` | Input and low-emphasis control borders |
| Success | `#15803D` | Valid ID and successful completion states |
| Error | `#B42318` | Validation errors and destructive warnings |

### Colour usage rules

- Blue is reserved for actions and active navigation; it should not decorate non-interactive content.
- Gold indicates a saved place or anniversary branding, not a general warning state.
- Navy provides hierarchy and institutional identity.
- Text on white or Canvas should use Ink, Navy, or Muted according to importance.
- Never communicate status by colour alone; pair colour with an icon and descriptive text.

## 4. Typography

The Flutter theme requests **SF Pro Display** and falls back to the device's system sans-serif when that family is unavailable. Typography is intentionally compact and mobile-first.

| Style | Size | Weight | Use |
|---|---:|---:|---|
| Display | 32 px | 800 | Welcome message and major empty-state statement |
| Page title | 24–25 px | 800 | Screen and bottom-sheet titles |
| Section title | 18–20 px | 700–800 | Saved places, map sections, administration groups |
| Card title | 16 px | 700–800 | Location, schedule, and announcement cards |
| Body | 15–16 px | 400–500 | Main descriptive content |
| Label | 13–14 px | 600–700 | Buttons, fields, chips, and navigation labels |
| Metadata | 11–13 px | 400–600 | Time, distance, floor, status, and supporting details |

### Writing rules

- Use sentence case: “Create account”, not “Create Account”.
- Use direct actions: “Log in”, “Save place”, “Start route”.
- Use friendly validation: “Enter your 9-digit SDU ID”.
- Avoid technical backend terms in the mobile interface.
- Keep route instructions short and action-led: “Continue through the central atrium.”

## 5. Spacing, shape, and elevation

### Spacing scale

Use an 8-point base grid while allowing 4-point adjustments for compact elements.

| Token | Value | Typical use |
|---|---:|---|
| `space-1` | 4 px | Icon-to-label micro spacing |
| `space-2` | 8 px | Closely related content |
| `space-3` | 12 px | List and field internals |
| `space-4` | 16 px | Standard component gap |
| `space-5` | 20 px | Card and page padding |
| `space-6` | 24 px | Section separation |
| `space-8` | 32 px | Major layout separation |

### Shape

| Element | Radius |
|---|---:|
| Cards | 20 px |
| Input fields and search | 18 px |
| Primary/secondary buttons | 16–18 px |
| Chips | Pill / full radius |
| Map pins and avatars | Circular |
| Bottom sheets | Platform Material 3 default with drag handle |

### Elevation

- Standard cards are flat (`elevation: 0`) and rely on spacing and background contrast.
- Floating map controls and search use a soft shadow to remain readable over the map.
- Bottom sheets provide the primary layered interaction for location details and route steps.

## 6. Core components

### Buttons

**Primary button**

- Action Blue background with white label and icon.
- Used once per decision area for the main action: Log in, Create account, Route, Submit.
- Minimum height: 52 px; minimum touch target: 48 × 48 px.

**Secondary button**

- White or transparent surface with visible border.
- Used for alternatives such as Create account, Cancel, and report actions.

**Text button**

- Used for low-emphasis actions such as Demo access or switching between login and registration.

### Input fields

- White fill, 18 px radius, and subtle Border colour.
- Focus state uses a 1.5 px Action Blue border.
- ID input accepts exactly nine digits and shows a green confirmation icon when valid.
- Password fields provide a visibility toggle.
- Error text must explain the correction, not expose server terminology.

### Cards

- White surface, 20 px radius, no default elevation.
- Use Navy cards only for high-priority role content such as next class or administration.
- Keep one primary interaction per card; trailing icons represent supporting actions.

### Chips

- Role chips use Role Blue with Navy text.
- Category chips filter map content and clearly distinguish selected/unselected states.
- Status chips always include readable text.

### Navigation bar

The main navigation contains four destinations:

1. **Map** — default and primary workspace.
2. **Assistant** — natural-language campus questions.
3. **Updates** — public announcements and events.
4. **Profile** — role, saved places, preferences, schedules, or guest login prompts.

The active destination uses a filled icon; inactive destinations use outlined icons.

### Bottom sheets

Bottom sheets preserve map context and are used for:

- Location details
- Search results
- Route steps
- Timetables
- Demo account access

Every bottom sheet should have a clear title, drag handle, safe-area spacing, and a visible dismissal path.

## 7. Interactive map language

### Map pins

- Default pin: white circle, Navy icon, 2 px Navy border.
- Selected pin: Action Blue fill with white icon and increased size.
- Saved pin: 3 px Anniversary Gold border.
- Each pin uses a category icon so meaning is not colour-dependent.

### Routes

- Active route: Action Blue line with a white underlay for contrast against the map.
- Route summary shows destination, estimated time, distance, and access to step details.
- Accessible route mode must explicitly say “Avoid stairs and use elevators”.
- When accessible routing is fully connected, its time and instructions must visibly change rather than relying on the switch alone.

### Location detail sheet

The information order is:

1. Category and location name
2. Block and floor
3. Opening hours
4. Contact information
5. Accessibility status
6. Role-allowed actions

Registered users see Save and Report actions. Guests see the public Route action only.

## 8. Role-aware interface rules

| Capability | Guest | Student | Teacher | Administrator |
|---|:---:|:---:|:---:|:---:|
| Map, search, public details | Yes | Yes | Yes | Yes |
| Public route and accessible route option | Yes | Yes | Yes | Yes |
| Saved places | No | Yes | Yes | Yes |
| Saved accessibility preference | No | Yes | Yes | Yes |
| Next class and timetable | No | Yes | No | Manage/view as required |
| Teaching schedule | No | No | Yes | Manage/view as required |
| Submit information report | No | Yes | Yes | Yes |
| Administration tools | No | No | No | Yes |

Hidden capabilities should be removed from guest layouts rather than displayed as disabled controls. The guest Profile screen explains which public features are available and offers Log in and Create account actions.

## 9. Interaction states

Every interactive component should account for:

| State | Treatment |
|---|---|
| Default | Standard surface, label, and icon |
| Pressed | Material ripple/pressed feedback |
| Focused | Action Blue outline |
| Selected | Filled or highlighted state plus icon/text change |
| Loading | Disable repeated action and show progress indicator |
| Success | Clear confirmation message and optional Success icon |
| Error | Friendly inline message using Error colour |
| Empty | Explain what is missing and how to add or discover it |
| Disabled | Reduced emphasis; use only when hiding would harm understanding |

## 10. Accessibility standards

- Minimum touch target: 48 × 48 logical pixels.
- Support Dynamic Type/text scaling without clipped controls.
- Use semantic labels for icon-only controls.
- Maintain at least WCAG AA contrast for normal text.
- Do not use colour as the only indicator of saved, selected, valid, or error state.
- Provide accessible entrances/elevators in location details and route steps.
- Keep route steps numbered and written in plain language.
- Respect safe areas and avoid placing essential controls under device system UI.

## 11. Implementation mapping

| Design-system area | Main implementation |
|---|---|
| Global colours and Material theme | `lib/src/theme.dart` |
| Welcome, login, and registration | `lib/src/screens/entry_screens.dart` |
| Map pins, location sheets, and routes | `lib/src/screens/map_screen.dart` |
| Role-aware profile and saved places | `lib/src/screens/profile_screen.dart` |
| Main navigation | `lib/src/screens/home_shell.dart` |
| Data and role models | `lib/src/models.dart` |

New screens should use the existing `AppColors`, Material 3 theme, spacing scale, and role rules rather than introducing isolated styles.


## 12. Responsive web implementation — current standard

React in `web/src/` is the active frontend; the Flutter mappings above remain historical. The web palette uses navy `#172c59`, map blue `#2563eb`, restrained anniversary gold and pale blue-grey surfaces. It uses the supplied `assets/images/sdu_30_logo.png`, system sans typography, rounded cards and shared shadcn-style Button/Dialog components built on Radix Slot/Dialog and Tailwind CSS v4. No recreated university logo is used.

Desktop: persistent 218px navigation, 320px search/details panel and remaining map canvas. Compact desktop/tablet: icon rail with a visible identity header. Narrow screens: bottom navigation, identity header and a dismissible 55vh explore/details sheet, leaving map context visible. Profile remains reachable on all widths. Name/role and initials identify signed-in accounts; Guest is explicit. Controls have focus states and text labels; map SVG targets also support Enter/Space. Search, saves, forms and requests show loading/error/empty states. Errors have retry paths or allow form resubmission.

The SVG background remains transparent over a theme-matched dotted canvas. Interactive room rectangles and POI markers are drawn once from catalogue geometry. Category selection filters markers; location selection/search switches floors. Explicit zoom in/out/fit and floor buttons supplement pan/pinch gestures through react-zoom-pan-pinch. Gold dashed route ends mean approximate doorway connections. Routes are framed and draw only the selected floor; directions offer floor-switch buttons. Map fit returns to the full schematic.

The older route-summary guidance about estimated metres/minutes is superseded: **show no distance or time until a measured scale exists**. Profile is the single location for the saved avoid-stairs preference. Step-free approaches are not certified. Hours/contact and unknown map positions use honest unconfirmed/unmapped states.
