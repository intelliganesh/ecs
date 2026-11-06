# ECS Applications

Two local applications are included:

- `frontend/`: React + TypeScript + Vite
- `backend/`: FastAPI + SQLAlchemy + Microsoft SQL Server via `pyodbc`

## Run both applications

From this directory:

```bash
./server.sh
```

The script installs dependencies on first run, creates `backend/.env`, and starts both development servers.

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs

## Manual setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

The backend expects Microsoft ODBC Driver 18 for SQL Server to be installed locally. `GET /health` works without a database; `GET /health/db` verifies the database connection.

