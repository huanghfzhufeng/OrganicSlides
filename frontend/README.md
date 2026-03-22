# OrganicSlides Frontend

This frontend is a React 19 + TypeScript + Vite application for the OrganicSlides workflow.

## Scripts

```bash
npm install
npm run dev
npm run build
npm test -- --run
npm run lint
```

## App Structure

- `src/App.tsx`: top-level authenticated wizard flow
- `src/views/`: step views such as input, research, outline, style, and generation
- `src/components/`: shared UI pieces like buttons, skeletons, and error states
- `src/api/client.ts`: frontend API contract layer
- `src/__tests__/`: Vitest component and client tests

## Notes

- The frontend expects the backend API at `http://localhost:8000/api/v1` in the current setup.
- Style previews are fetched from the backend style sample endpoint.
- The repo-wide testing guide lives in the root [`TESTING.md`](../TESTING.md).
