# React/Aceternity Component Migration Notes

## Current Status
Inside Imaging MVP is built with **Flask + Jinja templates + vanilla JavaScript**. There is currently no React build infrastructure.

## Requested Components

### #84: LoaderFive Component
**Request:** Replace `loader.js` with Aceternity's `<LoaderFive>` React component.

**Current Solution:** We've created an enhanced vanilla JS loader (`static/loader.js` + `static/loader.css`) that mimics the LoaderFive aesthetic with:
- Multiple concentric spinning rings
- Pulsing core effect
- Smooth animations with cubic-bezier easing
- Color-mix gradients matching the Aceternity style
- No React dependency required

**To use React LoaderFive in future:**
1. Set up a React build pipeline (Vite, Next.js, or Create React App)
2. Install Aceternity UI: `npm install @aceternity/ui`
3. Replace Flask templates with React components
4. Set up Flask as API-only backend

### Projects Page: ThreeDMarquee Component
**Request:** Replace the current marquee with Aceternity's `<ThreeDMarquee>` React component.

**Current Implementation:** The projects page uses CSS-based 2D marquee with:
- Two marquee rows (`.marquee-row-a` and `.marquee-row-b`)
- CSS `@keyframes` for smooth scrolling
- Duplicate image arrays for seamless looping

**Aceternity ThreeDMarquee Features:**
- 3D perspective transforms
- Depth-based scaling and opacity
- Mouse interaction / parallax effects
- GPU-accelerated animations

**Migration Path:**

#### Option 1: Full React Migration (Recommended for long-term)
```bash
# Initialize Next.js project structure
npx create-next-app@latest inside-imaging-nextjs --typescript --tailwind
cd inside-imaging-nextjs
npm install @aceternity/ui framer-motion clsx tailwind-merge

# File structure
inside-imaging-nextjs/
├── app/
│   ├── layout.tsx
│   ├── page.tsx (dashboard)
│   ├── projects/
│   │   └── page.tsx (use ThreeDMarquee here)
│   └── api/
│       └── upload/route.ts (calls Flask backend)
├── components/
│   ├── ui/
│   │   ├── 3d-marquee.tsx (from Aceternity)
│   │   └── loader.tsx (LoaderFive)
│   └── shared/
│       └── navbar.tsx
└── lib/
    └── utils.ts
```

Keep Flask (`app.py`) as backend API:
- Move route logic to API endpoints
- Return JSON instead of rendering templates
- Keep `src/translate.py` and database logic intact

#### Option 2: Hybrid Approach (Islands Architecture)
Embed React islands within Flask templates using Astro or similar:
- Keep most pages as Jinja templates
- Mount React components only where needed (loader, marquee)
- Use build tools to bundle React components separately

```html
<!-- templates/projects.html -->
<div id="marquee-root"></div>
<script type="module" src="/static/dist/marquee-island.js"></script>
```

#### Option 3: Vanilla JS Alternative (Current Approach)
Replicate Aceternity effects without React:
- Use CSS 3D transforms (`transform-style: preserve-3d`)
- Implement parallax with `requestAnimationFrame`
- Create depth illusion with scale + opacity curves

**Example pseudo-code:**
```javascript
// static/marquee-3d.js
const images = document.querySelectorAll('.marquee-card');
images.forEach((img, i) => {
  const depth = Math.sin(Date.now() * 0.001 + i * 0.5) * 100;
  img.style.transform = `translateZ(${depth}px) scale(${1 + depth/500})`;
  img.style.opacity = 0.4 + (depth + 100) / 200 * 0.6;
});
```

## Recommendation

For a production-ready app with Aceternity components:
1. **Short-term:** Continue with enhanced vanilla JS implementations (current approach)
2. **Long-term:** Migrate to Next.js App Router + Flask API backend
   - Better performance (SSR, code splitting)
   - Full Aceternity UI library access
   - Modern React patterns (Server Components, Suspense)
   - Tailwind CSS utility classes
   - TypeScript for better maintainability

## Migration Timeline Estimate

**Phase 1 (2-3 weeks):**
- Set up Next.js project structure
- Migrate navbar, footer, theme switcher to React
- Keep Flask backend API-only
- Implement authentication flow

**Phase 2 (2-3 weeks):**
- Migrate dashboard, projects, statistics pages
- Integrate Aceternity components (LoaderFive, ThreeDMarquee)
- Build upload flow with progress tracking

**Phase 3 (1-2 weeks):**
- Migrate result page with Three.js brain viewer
- Add interactive charts (recharts or Victory)
- Polish animations and transitions

**Phase 4 (1 week):**
- Testing, bug fixes, performance optimization
- Deploy (Vercel for Next.js, existing hosting for Flask)
- Documentation updates

## Questions to Consider

1. **Deployment:** Where will the Next.js app be hosted? (Vercel, Netlify, self-hosted?)
2. **Authentication:** Migrate to NextAuth.js or keep Flask sessions?
3. **Database:** Direct access from Next.js API routes or proxy through Flask?
4. **Styling:** Fully adopt Tailwind CSS or keep current CSS approach?
5. **Budget:** Do component library costs (Aceternity Pro?) fit the budget?

---

**Last Updated:** October 22, 2025  
**Status:** Vanilla JS workarounds implemented. React migration planned but not started.
