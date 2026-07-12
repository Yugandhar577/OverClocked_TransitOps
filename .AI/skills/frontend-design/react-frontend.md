---
name: react-frontend-development
description: Use when building or modifying a React frontend using React
  18 + Vite with Tailwind, TanStack Query, Zustand, React Router v6, and
  Axios. Enforces project structure, component patterns, data-fetching
  rules, and UI constraints.
---

# Skill: React Frontend Development

## Stack

-   React 18 + Vite
-   Tailwind CSS (utility-first, no custom CSS unless unavoidable)
-   React Router v6 (client-side routing)
-   TanStack Query (server state, caching, background refetch)
-   Zustand (client-side UI state only --- not for server data)
-   Axios (HTTP client, base instance with interceptors)

---

## Project Structure

    src/frontend/
    ├── src/
    │   ├── components/        # shared, reusable UI components
    │   │   ├── ui/            # primitives: Button, Badge, Spinner, etc.
    │   │   └── layout/        # Navbar, Sidebar, PageWrapper
    │   ├── features/          # feature-scoped folders (see below)
    │   │   ├── events/        # event cluster list + detail
    │   │   ├── summary/       # contrastive summary display
    │   │   └── outlets/       # outlet profile cards
    │   ├── hooks/             # shared custom hooks
    │   ├── lib/               # axios instance, query client, constants
    │   ├── pages/             # route-level components only — thin wrappers
    │   └── App.tsx

**Feature folder structure (consistent across all features):**

    features/events/
    ├── components/    # UI components scoped to this feature
    ├── hooks/         # useEvents, useEventDetail, etc.
    ├── api.ts         # all API calls for this feature
    └── types.ts       # TypeScript types scoped to this feature

---

## Component Rules

### Naming

-   Components: PascalCase (`SummaryCard.tsx`)
-   Hooks: camelCase with `use` prefix (`useEventCluster.ts`)
-   API files: `api.ts` per feature
-   Types: `types.ts` per feature, re-export from feature index if
    shared

### Component shape

``` tsx
// Always typed props, never `any`
interface SummaryCardProps {
  clusterId: string
  version: number
  onExpand?: () => void
}

export function SummaryCard({ clusterId, version, onExpand }: SummaryCardProps) {
  // ...
}
```

### State rules

-   Server data (articles, summaries, clusters) → TanStack Query only,
    never useState
-   UI state (modal open, selected tab, filter value) → useState or
    Zustand
-   Never store derived data in state --- compute it from query results
    inline

---

## Data Fetching Pattern

``` tsx
// features/events/hooks/useEventCluster.ts
import { useQuery } from '@tanstack/react-query'
import { fetchEventCluster } from '../api'

export function useEventCluster(clusterId: string) {
  return useQuery({
    queryKey: ['cluster', clusterId],
    queryFn: () => fetchEventCluster(clusterId),
    staleTime: 60_000,
    retry: 2,
  })
}
```

``` tsx
// In component
const { data, isLoading, isError } = useEventCluster(clusterId)

if (isLoading) return <Spinner />
if (isError) return <ErrorState />
```

Never fetch in useEffect. Always use TanStack Query.

---

## Summary Display Rules

Product-critical constraints:

-   Render summary sections in fixed order:
    1.  Widely Reported Facts\
    2.  Differences in Focus\
    3.  Only Some Outlets Mention\
    4.  Claims / Assertions
-   Claims section must show outlet attribution
-   Never show a trust score, bias rating, or numerical outlet ranking
-   "Only Some Outlets Mention" label must never be renamed to
    "Suppressed by" or "Ignored by"
-   Always show `updated X minutes ago` using `updated_at`
-   If summary status is `suppressed`, render a neutral placeholder
    without exposing suppression reason

---

## Loading & Error States

Every data-dependent component must guard for:

``` tsx
if (isLoading) return <Spinner size="md" />
if (isError) return <ErrorState message="Could not load summary" retry={refetch} />
```

Never render UI with undefined data.

---

## API Layer

``` ts
// lib/axios.ts
import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 10_000,
})

api.interceptors.response.use(
  res => res,
  err => {
    // log to Sentry
    return Promise.reject(err)
  }
)
```

``` ts
// features/events/api.ts
import { api } from '@/lib/axios'
import type { EventCluster } from './types'

export async function fetchEventCluster(id: string): Promise<EventCluster> {
  const res = await api.get(`/clusters/${id}`)
  return res.data
}
```

---

## Tailwind Rules

-   Use Tailwind utilities only
-   No inline styles or external CSS unless unavoidable
-   Responsive breakpoints:\
    `sm:` 640px\
    `md:` 768px\
    `lg:` 1024px
-   Dark mode first
-   Do not hardcode colors --- use semantic tokens (`bg-card`,
    `text-muted-foreground`, etc.)

---

## What Not To Do

-   No `any` types
-   No fetching inside `useEffect`
-   No business logic inside page components
-   No outlet ranking, trust scoring, or bias labeling in UI
-   No direct DOM manipulation
-   Do not create Zustand stores for data already owned by TanStack
    Query
