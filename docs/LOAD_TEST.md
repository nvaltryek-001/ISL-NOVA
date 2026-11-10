# Load test

**What was run.** `scripts/load_test.py` against a local server on the build
sandbox (**2 vCPU**, Python 3.13, SQLite, uvicorn with **2 workers**, model
`lstm-20261110T111537Z-s7` installed, rate limit raised for the test). Each
simulated user loops over 10 % `GET /health`, 40 % vocabulary search and 50 %
`POST /predict/sequence` with real held-out INCLUDE landmark sequences (the
24-sequence sample attached to the model release). 60 seconds per run.
Raw results: [`docs/load-test/`](load-test/).

| Concurrent users | Requests | Throughput | Errors | Predict p50 / p95 / p99 | Search p50 / p95 |
|---:|---:|---:|---:|---|---|
| 4 | 4,960 | **82.4 req/s** | 0 % | 73.5 / 188.5 / 263.3 ms | 7.6 / 30.9 ms |
| 16 | 5,684 | **93.9 req/s** | 0 % | 251.9 / 439.0 / 551.5 ms | 66.9 / 156.5 ms |

**Reading.** On 2 vCPU the server saturates at roughly 90 requests per second
with this mix (about 45 recognitions per second); beyond that, more users only
add queueing latency, with no errors. A recognition costs about 20–25 ms of CPU
(feature extraction + LSTM), so capacity scales with cores: add uvicorn workers
(`--workers` = cores) and, for several machines, `REDIS_URL` so the rate limit
and the job queue are shared.

**Limits of this test.** Client and server ran on the same 2 vCPU machine, so
the client took CPU from the server; numbers on dedicated hardware will be
higher. SQLite, not PostgreSQL. No video upload or training load. The free
Render demo (0.1 CPU) is far smaller and was **not** load-tested.

Reproduce:

```bash
RATE_LIMIT_PER_MINUTE=1000000 uvicorn app.main:app --app-dir backend --port 8000 --workers 2   # model installed
python scripts/load_test.py --base http://127.0.0.1:8000 --users 16 --seconds 60 --out load.json
```
