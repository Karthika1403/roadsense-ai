# RoadSense AI
Predictive-maintenance platform prototype for motorcycles. **Independent portfolio project using simulated data; not affiliated with Royal Enfield.**

## Run
```
cd backend && pip install -r requirements.txt
python ../ml/train.py            # optional: trains risk model (else rule fallback is used)
uvicorn app.main:app --reload    # docs at http://localhost:8000/docs
pytest -q                        # tests
```
Or `docker compose up --build`. Frontend: open `frontend/index.html` (standalone simulator demo).
Deploy: API + Postgres on Render (set DATABASE_URL, SECRET_KEY, CORS), frontend on Vercel.

## API
`POST /api/v1/auth/register`, `/auth/login` (JWT) · `GET/POST /api/v1/vehicles` · `POST /vehicles/{id}/telemetry` · `POST /vehicles/{id}/simulate?fault=heat|batt|bear` · `GET /vehicles/{id}/health` · `GET /vehicles/{id}/alerts`

## Data honesty
Tags: `roadsense_simulated` (live), `ai4i_synthetic`, `cmapss_simulated` (benchmarks). The bundled model is trained on threshold-labelled simulated data, so its scores show the pipeline works, not real-world skill. Health scores are rule-based. LSTM RUL and SHAP remain stretch goals.

## Images
`frontend/assets/bike.jpg` is optional. Add a photo you have rights to (e.g. from official brand media pages).
