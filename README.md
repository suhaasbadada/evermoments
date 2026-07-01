# evermoments

Trusted companion that helps patients remember, recognize, and reconnect.

## Stack

- Web: Next.js 16, React 19, TypeScript, Tailwind CSS v4
- API: FastAPI, SQLAlchemy, Pydantic, Uvicorn
- Monorepo: npm workspaces

## Prerequisites

- Node.js 22+
- npm 10+
- Python 3.12+
- Docker Desktop (optional, for containerized dev)

## Quick Setup

```bash
# 1) Install Node dependencies
npm install

# 2) Create Python virtual environment and install API deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt

# 3) Run both web + api together
npm run dev
```

Web runs on http://localhost:3000
API runs on http://127.0.0.1:8000

## Useful Commands

```bash
# run both apps locally
npm run dev

# run only web
npm run dev:web

# run only api (activate venv first)
npm run dev:api

# web checks
npm run lint:web
npm run build:web
```

## Docker (Optional)

```bash
npm run dev:docker
```

## Environment Notes

- API env file: apps/api/.env
- Web API base URL (optional override): apps/web/.env.local
- Example value: NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
