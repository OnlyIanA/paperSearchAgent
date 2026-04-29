.PHONY: backend frontend mcp

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 1299

frontend:
	cd frontend && npm run dev -- -H 0.0.0.0 -p 2299

mcp:
	cd backend && python -m app.mcp_server
