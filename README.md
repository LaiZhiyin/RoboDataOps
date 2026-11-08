<!-- Generated from portfolio/content.json. Run script/build_portfolio.py. -->

# RoboDataOps

**From trajectory evidence to the next collection decision.**

RoboDataOps connects complete-episode evidence, human acceptance decisions, task coverage and limited collection budgets for robotics data leads, operators and ML engineers.

[English](https://github.com/laizhiyin/RoboDataOps/blob/main/README.md) · [中文](https://github.com/laizhiyin/RoboDataOps/blob/main/README.zh-CN.md) · [HTML 1.1.0](https://laizhiyin.github.io/RoboDataOps/?lang=en) · [GitHub Actions](https://github.com/laizhiyin/RoboDataOps/actions) · [Codespaces](https://codespaces.new/laizhiyin/RoboDataOps?quickstart=1)

## [▶ WATCH THE PRODUCT DEMO — CLICK TO PLAY (~90 seconds)](https://laizhiyin.github.io/RoboDataOps/?lang=en#demo)

[![▶ CLICK THIS IMAGE TO PLAY THE ENGLISH PRODUCT WALKTHROUGH](https://laizhiyin.github.io/RoboDataOps/assets/video-preview-en.png)](https://laizhiyin.github.io/RoboDataOps/?lang=en#demo)

**[▶ Click here to watch the English walkthrough](https://laizhiyin.github.io/RoboDataOps/?lang=en#demo)** · [Open the MP4 video directly](https://laizhiyin.github.io/RoboDataOps/assets/robodataops-demo-en.mp4)

Click the play-button thumbnail above to open the video player, then press ▶. English interface, captions and narration.

30 seconds: the problem · 2 minutes: a decision · 5–10 minutes: inspect the evidence

[**92** passing software tests](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json) | [**87.49%** core package line coverage](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json) | [**100 / 100** exhaustive oracle matches](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/validation.json) | [**105** public baseline / compatibility episodes](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/v1-evidence.json)

[Evidence for metrics](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json)

## After delivery, what should the team do next?

Teams need to decide which episodes count for a stated use, which tasks remain under-covered and where to spend the next collection budget. File counts, finding counts and accepted episode counts differ.

The product provides traceable acceptance and collection decisions. Reduced review effort, rework and policy improvements are hypotheses awaiting real user and operational studies.

- **Data leads**: Inspect coverage, unresolved risk, budget alternatives and delivery shortfalls.

- **Collection and QA operators**: Locate episode/frame evidence, record reasons and export versioned collection tasks.

- **ML engineers**: Check platform, dimensions, FPS and action semantics before training.

## Every accepted episode has a traceable reason.

The main walkthrough uses 100 explicitly synthetic fault episodes. Inspect NaN evidence, then dismiss the low-motion signal for EP 64 with a reason and recalculate coverage. A useful waiting action is not automatically discarded.

Compare equal-budget, benefit/cost greedy and integer optimization under identical inputs. Save immutable plans with provenance, rules, reviews and constraints. Reconcile incoming data without double credit, then create a cumulative snapshot with lineage and recompute total gaps.

- **01 Read and audit**: A thin LeRobot v3 adapter reconstructs complete episodes and checks declared versus actual dtype, dimensions, indices and timing.

- **02 Inspect and review**: Individual/bulk confirmation, dismissal, deferral and reopening preserve append-only history. Video seeking moves action/state cursors.

- **03 Plan and explain**: Save/import/export scenarios; compare strategies; recalculate budget/capacity counterfactuals and explicit attempt-cost yield assumptions.

- **04 Receive and accumulate**: Require matching source/contracts, prevent duplicate credit, preserve lineage and carry reviews only for unchanged evidence.

## Know what the evidence cannot establish.

Shared Parquet/MP4 shards are not episodes. Five LIBERO simulation clips retain original camera paths, metadata intervals, transformations and SHA256. Missing downloads, decoding errors and sampled checks remain distinct. Metadata-based playback is not physical synchronization certification.

ALOHA checks a second contract: 14 action channels at 50 FPS, compared with LIBERO's 7 at 10 FPS. Units, absolute/delta control and coordinate frames remain unknown without supporting evidence. Matching dimensions do not establish matching semantics.

Technical acceptance does not prove task success or training value. Targets, prices, priorities and capacity default to simulated inputs; actual estimates require rationale. Cumulative artifacts preserve original IDs for analysis and are not reindexed training splits.

- **Mutually exclusive states**: Blocked, then incomplete mandatory checks, then unresolved review, otherwise accepted. Multiple findings never subtract the same episode twice. [State reduction](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/metrics.py)

- **Separate evidence sources**: Synthetic faults test software; public simulation samples test compatibility; hypothetical costs demonstrate decisions. [Design decisions](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/decisions.md)

## Follow a product decision into code and counterexamples.

Python/PyArrow reads columnar data, DuckDB/SQL aggregates acceptance, SciPy/HiGHS solves integer allocation, Streamlit provides the local workbench and FFmpeg handles video. GitHub Pages hosts this bilingual static case study with precomputed teaching interactions; run the Python app locally, in Docker or Codespaces.

Minimize normalized weighted residual gaps L = Σ wᵢ(dᵢ−xᵢ)/dᵢ with integer 0≤xᵢ≤min(dᵢ,capᵢ) and Σcᵢxᵢ≤budget. Money uses integer cents. Independent checks verify feasibility and distinguish proven optimality, a feasible incumbent, timeout without a solution and infeasibility. The objective measures quantity coverage, not robot capability.

- **Embodied data / Python**: Complete episodes, evidence rules, explicit action contracts and verified clip provenance. [quality.py](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/quality.py)

- **SQL / acceptance semantics**: Reduce once per episode before task aggregation. [coverage.sql](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/sql/coverage.sql)

- **Quantitative decisions**: Integer optimization, two baselines, counterfactuals and an independent exhaustive oracle. [planning.py](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/planning.py)

- **Engineering / regression**: Locked dependencies, checksums, append-only audits, transactions, receipt concurrency protection, CLI and remote CI. [Regression counterexamples](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/tests/test_review_regressions.py)

- **Product thinking**: User jobs, acceptance boundaries, research protocols and release scope. [PRD](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/PRD.md)

- **An actual engineering iteration**: Receipt checks had a cross-connection race. A process-level transaction lock and concurrency regression fixed it. A mismatched video interval also guards evidence generation. These are engineering review findings, not user interviews. [Observation, change, recheck](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/iteration-log.md)

## Report the denominator with every result.

One hundred small controlled cases compare optimal objectives against an independent exhaustive oracle, with 300 feasibility checks across three strategies. Ties are retained. Synthetic quality uses fixed controlled regressions with legitimate static negatives; an independently frozen test set is not yet established; injection recovery is not real-world accuracy.

Pinned public samples comprise 100 LIBERO episodes / 16,048 frames / five tasks and five ALOHA compatibility episodes. A separate 20-episode held-out public pool simulates incoming delivery. Five clips cover listed first-camera intervals only. Technical checks do not create a human quality gold standard.

Not yet conducted: 3–5-person user comparisons, 30–50 independently annotated episodes, robot training/rollouts or a real collection-cost pilot. Empty study templates, descriptive-analysis CLI and protocols are provided. Empty templates cannot produce results.

- **Software and optimizer evidence**: Environment, dependencies, seeds, samples, oracle results and unperformed studies are recorded. [Validation report](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/validation.md)

- **Actual browser checks**: Desktop, 390px mobile, synchronized video seeking and cumulative workflow checks. [Browser evidence](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/browser-smoke.json)

- **User and training protocols**: Counterbalance task order and record time/errors. Fix preprocessing, budgets and at least three training seeds; separate filtering from allocation ablations. [Protocols and blank templates](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/research/README.md)

## Reproduce the workflow with attributed data.

Use Python 3.12 and uv; install system FFmpeg for video. Curated offline analysis caches are included. First dependency installation needs network access. The workbench opens in English; use Language / 语言 in the sidebar to switch to Chinese. The CLI supports --lang en / --lang zh. Language changes preserve data, rules, reviews and budgets; raw data and audit JSON stay unchanged.

Try review, budget comparison, public clips and cumulative snapshots. With LIBERO and public_delivery, the simulation grows from 100 to 120 episodes, four per task. This is reserved public data, not newly captured delivery. GitHub Pages cannot run the Streamlit backend.

- **Data acquisition and licensing**: Pinned revisions, selection, checksums and data licenses are recorded in each cache's NOTICE. fetch-libero and prepare_evidence.py reproduce acquisition; video downloads total about 80MB and are optional. [LIBERO attribution](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/data/public_sample/NOTICE.md)

- **Architecture and limits**: CLI and UI share domain logic. Persistent mode uses var/workbench.duckdb; demo mode isolates sessions. Multi-process serving, authorization and large jobs remain pilot-driven extensions. [Architecture](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/architecture.md)

```bash
git clone https://github.com/laizhiyin/RoboDataOps.git
cd RoboDataOps
uv sync --frozen
ROBODATAOPS_DEMO_MODE=1 uv run streamlit run app.py

uv run robodataops audit --source data/public_sample --db :memory:
uv run robodataops plan --source data/demo --budget 800 --db :memory:
uv run python -m robodataops.validation
uv run pytest -q --cov=robodataops --cov-fail-under=80
uv run python script/build_portfolio.py --check
docker compose up --build
```

## Show explainable capability and honest ownership.

This is an AI-assisted project. New implementation covers workflows, the thin adapter, acceptance, evidence linkage, planning, cumulative lineage and validation tools. Open-source components supply the ecosystem, storage, solver and UI foundations. Using HiGHS is not inventing an optimization algorithm, and generated code alone does not prove independent coding ability.

The candidate should personally rehearse three changes: add a rule with a valid negative; change SQL and prove no double count; add a business constraint and explain the solver result. Describe personal decisions and hands-on contributions according to actual experience. No interview, internship or ownership percentage is fabricated.

Next priorities are real task feedback and independent labels, followed by small policy experiments. Add server databases, permissions, object storage, background jobs and supplier scheduling when a real pilot needs them.

- **Contributions and licenses**: Project code is MIT; datasets and third-party components retain their own licenses. [Attribution](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/contributions.md)

- **Remaining external validation**: User studies, actual costs, training value and commercial adoption have separate completion criteria. [Next validation steps](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/NEXT_STEPS.md)

## Static budget teaching case

Precomputed by the same Python planning module. Costs and weights are simulated; changing the web budget does not call a live backend.

| Budget / CNY | Equal loss | Greedy loss | Optimal loss |
|---:|---:|---:|---:|
| 200 | 3.550 | 3.500 | 3.450 |
| 350 | 2.800 | 2.900 | 2.800 |
| 500 | 2.150 | 2.200 | 2.150 |
| 800 | 0.950 | 0.950 | 0.900 |
