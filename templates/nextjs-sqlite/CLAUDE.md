# CLAUDE.md â€” Next.js 15 + SQLite SaaS

Production-ready context for Claude Code. Every rule has a reason.

---

## Stack

| Layer | Tech | Version |
|-------|------|---------|
| Framework | Next.js App Router | 15.x |
| Database | better-sqlite3 (local) / Turso (prod) | latest |
| Auth | Lucia v3 | latest |
| Styling | Tailwind CSS | 4.x |
| Validation | Zod | 3.x |
| Email | Resend | latest |
| Payments | Stripe | latest |
| Deployment | Vercel + Turso | â€” |

---

## Project Structure

```
app/
  (auth)/
    login/page.tsx
    signup/page.tsx
  (dashboard)/
    layout.tsx          â† auth guard lives here
    page.tsx
  api/
    webhooks/
      stripe/route.ts
lib/
  db/
    index.ts            â† single db instance export
    migrations/         â† numbered SQL files: 001_init.sql, 002_add_users.sql
    schema.ts           â† TypeScript types mirroring tables
  auth/
    session.ts
  stripe/
    client.ts
components/
  ui/                   â† shadcn/ui components only, never modified
  app/                  â† your components go here, never in ui/
hooks/
types/
  index.ts              â† shared types
```

**Rule:** Never put business logic in `app/` files. Pages fetch, components render, `lib/` does work.

---

## Database Rules

### Migrations

- Files live in `lib/db/migrations/`
- Named: `NNN_description.sql` (e.g., `001_init.sql`, `002_add_subscriptions.sql`)
- Never edit a migration after it runs â€” create a new one
- Run on startup via `lib/db/index.ts` (reads all migration files, applies unapplied ones)
- No ORM. Raw SQL only. Reason: SQLite is simple enough that an ORM adds complexity without benefit.

### Schema conventions

```sql
-- Every table gets these columns
id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
created_at INTEGER NOT NULL DEFAULT (unixepoch()),
updated_at INTEGER NOT NULL DEFAULT (unixepoch())

-- Use INTEGER for booleans: 0/1
-- Use INTEGER for timestamps: unixepoch()
-- Use TEXT for everything else (JSON blobs, enums, UUIDs)
-- No FLOAT â€” use INTEGER cents for money
```

### Queries

```typescript
// lib/db/index.ts â€” single instance
import Database from 'better-sqlite3';
export const db = new Database(process.env.DB_PATH ?? './local.db');
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Always use prepared statements
const getUser = db.prepare('SELECT * FROM users WHERE id = ?');
const user = getUser.get(userId);

// Transactions for multi-step writes
const transfer = db.transaction((from: string, to: string, amount: number) => {
  db.prepare('UPDATE accounts SET balance = balance - ? WHERE id = ?').run(amount, from);
  db.prepare('UPDATE accounts SET balance = balance + ? WHERE id = ?').run(amount, to);
});
```

---

## Folder & Naming Conventions

- **Files:** `kebab-case.ts` always
- **Components:** `PascalCase` export, `kebab-case.tsx` filename
- **Server Actions:** suffix with `Action` â€” `createSubscriptionAction.ts`
- **API routes:** `app/api/resource/route.ts` â€” one file per resource
- **Types:** defined in `types/index.ts` or colocated in `lib/`

---

## Component Patterns

### Server Components (default)

```tsx
// app/(dashboard)/page.tsx
import { db } from '@/lib/db';
import { getSession } from '@/lib/auth/session';

export default async function DashboardPage() {
  const session = await getSession();
  const data = db.prepare('SELECT * FROM items WHERE user_id = ?').all(session.userId);
  return <ItemList items={data} />;
}
```

### Client Components

```tsx
'use client';
// Only when: useState, useEffect, onClick, browser APIs
// Keep them small â€” push data fetching to server parents
```

### Server Actions

```typescript
// lib/actions/items.ts
'use server';
import { db } from '@/lib/db';
import { z } from 'zod';
import { revalidatePath } from 'next/cache';

const CreateItemSchema = z.object({
  name: z.string().min(1).max(100),
});

export async function createItemAction(formData: FormData) {
  const parsed = CreateItemSchema.safeParse({ name: formData.get('name') });
  if (!parsed.success) return { error: parsed.error.flatten() };
  
  db.prepare('INSERT INTO items (name, user_id) VALUES (?, ?)').run(
    parsed.data.name,
    session.userId
  );
  revalidatePath('/dashboard');
  return { success: true };
}
```

---

## Auth Pattern

```typescript
// lib/auth/session.ts
import { cookies } from 'next/headers';
import { db } from '@/lib/db';

export async function getSession() {
  const token = (await cookies()).get('session')?.value;
  if (!token) return null;
  return db.prepare('SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.expires_at > ?')
    .get(token, Math.floor(Date.now() / 1000));
}

// In layout.tsx (dashboard):
const session = await getSession();
if (!session) redirect('/login');
```

---

## Dev Commands

```bash
npm run dev          # start dev server (port 3000)
npm run db:migrate   # run pending migrations
npm run db:studio    # open Drizzle studio (if used) â€” we don't use this
npm run build        # production build
npm run typecheck    # tsc --noEmit
```

---

## Environment Variables

```bash
# .env.local
DB_PATH=./local.db                    # local dev
DATABASE_URL=libsql://...             # Turso prod
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
RESEND_API_KEY=re_...
NEXTAUTH_SECRET=...                   # 32+ random chars
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## What We Don't Do (and Why)

| âŒ Don't | âœ… Do instead | Why |
|----------|--------------|-----|
| Use Prisma or Drizzle | Raw SQL with better-sqlite3 | SQLite is simple. ORMs hide behavior. |
| `useEffect` for data fetching | Server Components | Less JS, faster load, simpler code |
| `any` in TypeScript | Proper types from `types/index.ts` | Errors caught at build time |
| Store secrets in code | `.env.local` only | Security |
| Modify `components/ui/` | Add to `components/app/` | ui/ is re-generated by shadcn |
| `console.log` in production | `lib/logger.ts` wrapper | Structured logs, easy to filter |
| Float for money | Integer cents | Float precision bugs kill SaaS |
| Edit migrations | New migration file | Immutable history |
| Global state (Redux/Zustand) | Server state + URL params | Next.js makes this unnecessary |
| `fetch` in Server Components without caching strategy | Add `cache: 'no-store'` or revalidate | Stale data bugs |

---

## Stripe Webhook Pattern

```typescript
// app/api/webhooks/stripe/route.ts
import Stripe from 'stripe';
import { headers } from 'next/headers';
import { db } from '@/lib/db';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(req: Request) {
  const body = await req.text();
  const sig = (await headers()).get('stripe-signature')!;
  
  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch { return new Response('Bad signature', { status: 400 }); }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object;
    db.prepare('UPDATE users SET plan = ? WHERE stripe_customer_id = ?')
      .run('pro', session.customer);
  }

  return new Response('OK');
}
```

---

## Error Handling

- Server Actions return `{ error: string } | { success: true }` â€” never throw
- API routes return proper HTTP status codes with JSON body
- Use Next.js `error.tsx` for UI error boundaries
- Log errors server-side, show generic message to users

---

## Turso (Production DB)

```typescript
// lib/db/index.ts â€” switches automatically
import { createClient } from '@libsql/client';
import { drizzle } from 'drizzle-orm/libsql'; // only if using Drizzle

// Without Drizzle (preferred):
const client = process.env.DATABASE_URL
  ? createClient({ url: process.env.DATABASE_URL, authToken: process.env.DATABASE_AUTH_TOKEN })
  : null; // falls back to better-sqlite3 locally
```
