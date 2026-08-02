# Stage 2 Information Architecture and User Flows

## PRD Contents

The Product Requirements Document must include:

- **Product Vision:** Problem Statement, Objectives, Success Metrics, Out of Scope, Assumptions, Dependencies, Open Questions
- **Stakeholders:** Primary, Secondary, Internal, External
- **Personas:** Reference PER IDs
- **Epics:** Reference EP IDs
- **Capabilities:** Reference CAP IDs
- **Features:** Each feature MUST contain: Feature ID, Name, Description, Originating REQ IDs, Priority, Dependencies, Success Criteria

## User Stories

Each story must follow the format: *As a [persona]... I want... So that...*

Include: Story ID, Priority, Requirement References, Acceptance Criteria IDs. Every story must reference at least one REQ-ID from Stage 1.

## Information Architecture

Define the logical structure of the product: Navigation hierarchy, Content grouping, Logical organization, Page hierarchy, Route hierarchy, Information relationships.

Example structure:

```
Dashboard
├── Projects
├── Reports
├── Settings
└── Profile
```

Every information architecture decision must support user flows and be traceable to requirements.

## Navigation Model

Define all navigation patterns and interactions:

- Global Navigation: Main menu, top-level routes
- Context Navigation: Secondary menus, sub-sections
- Breadcrumbs: Hierarchical position indicators
- Tabs: Grouped related content
- Drawers: Slide-out panels
- Modals: Overlay dialogs
- Wizard Navigation: Step-by-step flows
- Deep Linking: Direct navigation to specific screens
- Back Navigation: Return paths and history

## User Flows

Every flow must contain:

- Flow ID: Unique identifier (UF-###)
- Goal: What the user is trying to accomplish
- Actors: Personas involved
- Preconditions: State before the flow starts
- Main Flow: Happy path step-by-step
- Alternative Flow: Secondary paths
- Exception Flow: Error handling
- Postconditions: Expected state after completion
- Referenced Requirements: Originating REQ-IDs
- Referenced Screens: SCR-IDs involved
- Referenced Features: FEAT-IDs involved

## Screen Specifications

Every screen must include:

- Screen ID: Unique identifier (SCR-###)
- Purpose: What this screen accomplishes
- Entry Conditions: How the user arrives
- Exit Conditions: How the user leaves
- Layout: Visual structure and regions
- Navigation: Available navigation paths
- Displayed Information: Data elements shown
- Available Actions: Buttons, forms, interactions
- Business Rules: Conditional logic
- Permissions: Access control rules
- Responsive Behaviour: Layout changes across breakpoints
- Accessibility Notes: WCAG compliance details

**States:** Every screen must document behavior in Loading, Empty, Success, Error, Offline, and Permission Denied states.

## Wireframes

Text-based wireframes only. No drawings. No images. Describe:

- Header: Logo, title, navigation links
- Sidebar: Primary navigation, filters
- Body: Main content area
- Cards: Information containers
- Tables: Tabular data layouts
- Forms: Input fields and validation
- Buttons: Call-to-action elements
- Search: Query interfaces
- Filters: Data refinement controls
- Pagination: Result navigation
- Dialogs: Modal content
- Notifications: System messages
- Footer: Secondary links, metadata
