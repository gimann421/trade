# NEXUS AIS v2.0
## Autonomous Investment System — Master Architecture & Operating Specification

**Version:** 2.0.0  
**Status:** Foundational build specification  
**Development environment:** Claude Code  
**Operating model:** Always-on research, autonomous experimentation, paper trading, and shadow portfolio management  
**Initial live-trading authority:** None  
**Primary objective:** Maximize long-term portfolio growth and expected terminal wealth

---

# 0. Executive mandate

NEXUS AIS is an always-on, multi-agent investment research and portfolio-management system. It continuously observes markets, discovers opportunities and strategies, forms hypotheses, tests them, challenges its own conclusions, paper trades approved experiments, shadow-manages the owner's actual portfolio, measures outcomes, and updates its research priorities.

NEXUS is not a chatbot that periodically comments on markets. It is a persistent software system with scheduled and event-driven jobs, durable state, versioned strategies, reproducible research, a decision ledger, portfolio simulators, monitoring, and a human-readable dashboard.

## 0.1 Governing objective: growth

NEXUS's governing objective is to maximize long-term portfolio growth, expressed operationally as maximizing expected terminal wealth and compound growth over the owner's stated horizon.

The system should seek the highest expected growth opportunities it can identify across the permitted research universe. It should not confuse:
- low volatility with success;
- benchmark-relative outperformance with absolute wealth creation;
- high trade frequency with productivity;
- a high backtest return with a validated edge;
- a profitable isolated strategy with an improvement to the total portfolio.

Growth is not permission for ruin. A strategy with a material probability of catastrophic or unrecoverable loss can reduce expected terminal wealth even if its upside scenario is spectacular. NEXUS therefore has mandatory survival controls: leverage limits, liquidity constraints, concentration controls, drawdown response rules, data integrity checks, and independent risk vetoes. These controls protect the compounding objective; they do not replace it with a low-risk objective.

**Prime directive:** Allocate each marginal dollar to the opportunity with the highest defensible expected contribution to long-term portfolio growth, after costs, taxes, financing, liquidity effects, path dependency, and portfolio interactions.

**Motto:** Every dollar must earn its place.

## 0.2 Initial authority boundary

From initial deployment, NEXUS may:
- research any supported market or asset class;
- generate and evaluate investment hypotheses;
- run historical, statistical, scenario, and simulation tests;
- create and manage simulated strategy accounts;
- record timestamped hypothetical trades;
- maintain a shadow-managed version of the owner's real portfolio;
- recommend hypothetical buys, sells, holds, hedges, and reallocations;
- compare its shadow portfolio with the actual portfolio;
- update its research priorities and non-governing model parameters under controlled validation.

From initial deployment, NEXUS must not:
- submit, modify, or cancel real brokerage orders;
- move, withdraw, or transfer money;
- access payment credentials;
- represent a hypothetical order as an actual fill;
- grant itself new permissions;
- alter its own promotion criteria or safety limits;
- use unverified holdings or stale prices as if they were current.

The owner remains the ultimate authority. Any future live authority requires a separate, explicit, documented authorization and a staged approval process.

---

# 1. Relationship to original NEXUS

NEXUS AIS v2.0 extends the existing NEXUS Investment Operating System. It preserves the original process philosophy and specialist roles while adding persistent software infrastructure, quantitative research, backtesting, simulation, paper trading, shadow portfolio management, monitoring, and staged autonomy.

## 1.1 Preserved principles

The following original principles remain foundational:
1. Every holding, reserve asset, new opportunity, and decision to maintain allocation competes for capital.
2. Evaluate the specific funding source, not merely whether the destination is attractive.
3. Optimize expected after-tax terminal wealth rather than headline return alone.
4. Distinguish decision quality from short-term outcome.
5. Treat taxes, spreads, market impact, fees, complexity, liquidity, and opportunity cost as portfolio friction.
6. Treat reserve capital as a real position with yield, risk, liquidity, and option value.
7. Do not force consensus among specialists.
8. State uncertainty and avoid false precision.
9. Use fresh, reliable evidence and distinguish facts, estimates, interpretations, and inferences.
10. Learn from outcomes without overfitting or rewriting core rules after a small sample.
11. Keep an auditable decision journal and persistent opportunity leaderboard.
12. Human authority and execution boundaries remain explicit.

## 1.2 Existing agents retained

- **PRISM** — technicals, market structure, timing, liquidity, breadth, volatility.
- **ATLAS** — fundamentals, valuation, economics, quality, long-term expected return.
- **ORION** — portfolio construction, capital allocation, sizing, funding sources.
- **SENTINEL** — risk, taxes, liquidity, correlation, financing, implementation, failure analysis.
- **HORIZON** — macro, news, catalysts, cross-market developments, new opportunity discovery.
- **MERIDIAN** — CIO synthesis, dynamic action hurdle, portfolio-level decision and final recommendation.

## 1.3 New roles and services

- **QUANT LAB** — hypothesis generation, quantitative research, statistical testing, strategy development.
- **RED TEAM** — independent adversarial review; tries to falsify a strategy, data set, backtest, or investment thesis.
- **VALIDATION COMMITTEE** — determines whether evidence meets promotion criteria. It cannot be the strategy author.
- **EXECUTION SIMULATOR** — estimates fills, slippage, fees, financing, market impact, contract rolls, and settlement.
- **PAPER PORTFOLIO MANAGER** — manages isolated simulated strategy accounts.
- **SHADOW PORTFOLIO MANAGER** — maintains a simulated copy of the owner's actual portfolio and records what NEXUS would have changed.
- **RISK GATE** — deterministic, non-LLM control service that blocks actions outside policy.
- **AUDIT ENGINE** — immutable decision, data, model, and simulated-order record.

An agent may be implemented as a separate process or as a distinct role executed by one model. The implementation must preserve role separation, independent evidence, dissent, and auditability.

---

# 2. Investment universe: broad discovery mandate

NEXUS has an intentionally broad research mandate. It should search for opportunities across all markets for which it can obtain sufficiently reliable data and legally permitted access.

## 2.1 Research categories

1. **Equities:** US and international listed shares, large/mid/small/micro caps where data quality permits, ADRs, emerging and developed markets.
2. **Funds and indices:** ETFs, mutual funds, index products, sector, thematic, factor, country, leveraged and inverse products.
3. **Fixed income and credit:** sovereign debt, Treasuries, bills, corporate credit, high yield, municipal debt, inflation-linked securities, rates products and bond funds.
4. **Commodities:** precious and industrial metals, energy, agriculture, livestock, commodity funds, spot-linked products, and futures curves.
5. **Derivatives:** listed options, index options, futures, options on futures, volatility products, swaps or other instruments only where data, access, contract specifications, and legal review are adequate.
6. **Currencies:** spot FX, currency futures, forwards, currency funds, and cross-currency relative value.
7. **Digital assets:** cryptocurrencies, spot products, exchange-traded products, and derivatives where lawful and accessible.
8. **Prediction and event markets:** political, economic, financial, sports, weather, and other event contracts, subject to platform rules, jurisdiction, contract resolution, liquidity, and legal eligibility.
9. **Alternative strategies:** trend following, carry, value, momentum, quality, mean reversion, statistical arbitrage, pairs, relative value, event-driven, merger arbitrage, volatility, market-neutral, seasonality, and systematic macro.
10. **Cross-market and macro:** rates/FX/equity/commodity relationships, volatility surfaces, credit spreads, liquidity regimes, inter-market hedges, and capital rotation.
11. **New markets:** any new asset class or contract type may enter the research queue after a data, mechanics, legality, custody, and risk review.

## 2.2 Research is broader than eligibility to trade

Each instrument receives a capability classification:

- **R0 — Discover only:** may be researched, but reliable pricing or contract data is insufficient for meaningful simulation.
- **R1 — Research and backtest:** historical data and mechanics are adequate for research; no live or paper execution simulation yet.
- **R2 — Paper eligible:** reliable timestamps, prices, contract terms, and plausible execution assumptions support paper trading.
- **R3 — Shadow eligible:** may be used in a shadow portfolio with validated holdings/prices and appropriate accounting.
- **R4 — Future live eligible:** only after jurisdiction, product, broker, custody, operational, and owner-authorization checks. This status is unavailable at launch.

The system must never pretend that "everything" means every instrument is equally understood or safely tradable. Research breadth is the default; operational permissions are earned instrument by instrument.

## 2.3 Instrument registry

Every instrument record should include:
- canonical instrument ID and symbols;
- asset class, subclass, exchange, currency, timezone;
- trading calendar and session;
- contract multiplier and tick size where applicable;
- expiration, settlement, exercise, delivery, and roll rules;
- margin and financing model where relevant;
- corporate-action handling;
- liquidity classification;
- data sources and freshness;
- jurisdiction and access status;
- R0-R4 capability classification;
- known failure modes and special risk rules.

---

# 3. System architecture

## 3.1 Logical architecture

```text
Market / Fundamentals / Macro / News / Alternative Data / Owner Portfolio
                                |
                         DATA INGESTION
                                |
                    NORMALIZATION & QUALITY GATES
                                |
                 CANONICAL TIME-SERIES + EVENT STORE
                                |
         +----------------------+----------------------+
         |                      |                      |
   DISCOVERY ENGINE        PORTFOLIO STATE        RESEARCH MEMORY
         |                      |                      |
   QUANT LAB / AGENTS       SHADOW MANAGER          STRATEGY LIBRARY
         |                      |                      |
   HYPOTHESIS REGISTRY      PORTFOLIO SNAPSHOT       DECISION JOURNAL
         |                      |                      |
   BACKTEST ENGINE         PAPER LEDGER             PERFORMANCE STORE
         |                      |                      |
   RED TEAM / VALIDATION   RISK GATE                AUDIT ENGINE
         |                      |                      |
   STRATEGY PROMOTION      SIMULATED ORDERS          DASHBOARD / ALERTS
         +----------------------+----------------------+
                                |
                         MERIDIAN CIO
                                |
                   OWNER REPORTS / APPROVAL GATES
```

## 3.2 Core services

1. **Orchestrator:** schedules jobs, dispatches agents, handles retries, enforces timeouts, records run IDs.
2. **Data ingestion:** collects market, fundamental, macro, news, alternative and portfolio data.
3. **Data quality service:** validates timestamps, missing values, stale observations, corporate actions, symbol mappings, contract rolls and source conflicts.
4. **Canonical data store:** durable normalized data with source lineage.
5. **Research engine:** discovers anomalies, screens markets, generates hypotheses and maintains experiments.
6. **Backtest engine:** event-driven and vectorized testing with point-in-time data controls.
7. **Simulation engine:** paper orders, fill models, cash, positions, financing, margin and settlement.
8. **Portfolio engine:** actual portfolio snapshot, shadow portfolio, strategy sleeves, consolidated exposure.
9. **Risk gate:** deterministic pre-trade and portfolio-level checks.
10. **Agent runtime:** PRISM, ATLAS, ORION, SENTINEL, HORIZON, MERIDIAN, QUANT LAB, RED TEAM.
11. **Memory and journal:** strategy registry, experiment history, decisions, predictions, disagreements, policy versions.
12. **Monitoring:** service health, data health, strategy health, risk alerts, drift and system failures.
13. **Dashboard and reporting:** current state, performance, experiments, proposed decisions, alerts, and audit trail.

## 3.3 Suggested technology approach

Claude Code is the development environment, not the always-on runtime. The system must continue running when Claude Code is closed.

Use a modular, replaceable stack. A sensible initial implementation:
- Python for research, data science, backtesting and portfolio services.
- PostgreSQL for canonical relational state and audit metadata.
- Parquet files plus object storage for historical market data and experiment artifacts.
- Redis or a durable task queue for job dispatch and short-lived coordination.
- A scheduler/workflow orchestrator for recurring and event-driven jobs.
- FastAPI or equivalent for internal APIs.
- A web dashboard for portfolio, research and operations.
- Docker containers for reproducible local and cloud deployment.
- Git for version control; automated tests and CI for deployment controls.

Specific vendors are implementation choices, not constitutional dependencies. Avoid a brittle architecture tied to one model provider, broker, market-data vendor, or cloud.

## 3.4 Model-provider independence

Claude models may be the primary reasoning layer. NEXUS should nevertheless separate:
- model prompts and role definitions;
- data retrieval;
- deterministic calculations;
- portfolio state;
- risk checks;
- execution simulation;
- audit records.

A model change must not silently change accounting, risk limits, or order-state logic. Deterministic services own those functions.

## 3.5 Always-on scheduling

Use event-driven monitoring and scheduled research, not expensive LLM calls every second.

Example initial cadence:
- Market data: according to instrument session and vendor update frequency.
- Data-quality checks: after each ingestion batch and before every decision.
- Risk monitor: on new prices, portfolio changes, and configured thresholds.
- Discovery scans: daily or several times per session depending on asset class.
- Strategy research: scheduled batches, with event-triggered work for major dislocations.
- Full shadow portfolio review: daily and after material events.
- Strategy performance review: daily metrics, weekly diagnostics, monthly validation review.
- Governance review: quarterly and before any permission expansion.

Cadence is configurable by market, data cost, and strategy horizon. The scheduler must log missed jobs and never imply a check ran when it did not.

---

# 4. Agent charters and decision protocol

## 4.1 PRISM — Market structure and timing
Analyze price, trend, breadth, volume, volatility, liquidity, market microstructure, technical regimes, entry quality and execution conditions. Do not infer fundamental value from chart patterns.

## 4.2 ATLAS — Fundamentals and expected return
Analyze valuation, cash flows, business quality, balance sheets, growth, capital intensity, index composition, factor exposures, credit quality, yield curves, and expected return distributions. Explicitly separate facts from assumptions.

## 4.3 ORION — Portfolio construction
Evaluate marginal contribution to the whole portfolio, funding source, position sizing, correlation, concentration, factor and asset-class exposures, opportunity cost, and capital allocation across strategy sleeves.

## 4.4 SENTINEL — Risk, tax and implementation
Independently identify loss mechanisms, leverage, liquidity, financing, counterparty, settlement, tax, wash-sale, assignment, gap, tail, model, operational, and regulatory risks. It can block an action on a hard constraint.

## 4.5 HORIZON — Macro and discovery
Monitor rates, inflation, employment, policy, geopolitics, earnings, regulation, commodity supply/demand, market structure, new listings, prediction-market events, catalysts and cross-asset dislocations. Distinguish structural changes from headline noise.

## 4.6 QUANT LAB — Strategy research
Generate falsifiable hypotheses, identify data requirements, propose features and signals, define benchmark comparisons, create reproducible experiments, and submit candidates for adversarial review. It cannot self-certify its strategies.

## 4.7 RED TEAM — Independent challenge
Try to disprove the thesis and the backtest. Search for look-ahead bias, survivorship bias, selection bias, leakage, multiple testing, unstable parameters, regime dependence, impossible fills, hidden leverage, capacity limits, and missing costs. Its incentives must favor finding flaws, not agreeing.

## 4.8 VALIDATION COMMITTEE
Review experimental design, out-of-sample evidence, robustness, economic rationale, paper-trading record, capacity, and operational reliability. It must be independent from the strategy author and must record pass/fail/defer with reasons.

## 4.9 MERIDIAN — CIO and portfolio manager
Synthesize the committee, set the dynamic action hurdle, compare each candidate with its exact funding source, decide whether to allocate in simulation, explain dissent, and report the expected contribution to terminal wealth. MERIDIAN cannot override the Constitution, deterministic risk gate, or owner permissions.

## 4.10 Disagreement protocol
Each specialist records:
- vote or recommendation;
- confidence;
- supporting evidence;
- strongest counterargument;
- key uncertainty;
- conditions that would change its view.

MERIDIAN must explain material disagreement. No majority-vote shortcut. A hard risk or data-quality failure cannot be outvoted.

---

# 5. Continuous operating loop

NEXUS repeats this loop continuously:

1. **Observe:** ingest current data and portfolio state.
2. **Validate:** check freshness, integrity, lineage, calendars and instrument mechanics.
3. **Discover:** scan broadly for new opportunities, anomalies, catalysts and strategy ideas.
4. **Hypothesize:** formulate testable explanations and predicted behavior.
5. **Research:** obtain primary evidence and quantify assumptions.
6. **Backtest:** test historical behavior with realistic costs and point-in-time data.
7. **Challenge:** Red Team attempts to falsify the result.
8. **Validate:** independent review decides whether the strategy merits further testing.
9. **Paper trade:** eligible strategies create timestamped simulated orders.
10. **Shadow manage:** evaluate the actual portfolio and maintain a parallel hypothetical portfolio.
11. **Measure:** compare actual, shadow and strategy sleeves.
12. **Learn:** update estimates, confidence and research priorities under version control.
13. **Reallocate research effort:** focus compute and data spend on the highest-value unresolved questions.
14. **Repeat.**

NEXUS should be active without being noisy. No-trade is a valid outcome. Research activity, alerts and agent calls should be prioritized by expected information value.

---

# 6. Quantitative research and hypothesis registry

Every strategy or investment thesis must be registered before testing.

## 6.1 Required hypothesis record

- Unique hypothesis ID and version.
- Authoring agent and timestamp.
- Asset universe and eligibility classification.
- Economic or behavioral rationale.
- Signal definition, features and parameters.
- Expected holding period and turnover.
- Entry, exit, sizing and risk logic.
- Benchmark and alternative explanations.
- Data sources, licenses and timestamps.
- Training, validation and holdout periods.
- Known biases and limitations.
- Expected capacity and liquidity needs.
- Costs, taxes, financing and margin assumptions.
- Conditions under which the hypothesis should fail.
- Pre-registered success criteria.
- Code commit, data snapshot and environment version.

A hypothesis must be falsifiable. "This asset will go up" is not a research hypothesis.

## 6.2 Research categories

NEXUS may investigate:
- cross-sectional and time-series momentum;
- value, quality, profitability, growth and size;
- trend following and managed futures;
- carry and term structure;
- mean reversion and statistical arbitrage;
- pairs and relative value;
- event-driven and catalyst strategies;
- volatility and options structures;
- seasonality and calendar effects;
- macro regime allocation;
- commodity curve and roll strategies;
- FX and rates relationships;
- prediction-market probability mispricing;
- portfolio hedging and tail-risk strategies;
- alternative data signals;
- hybrid discretionary/quantitative theses.

These are research categories, not assumptions that any strategy has a persistent edge.

## 6.3 Research prioritization

Prioritize ideas by:
- plausible economic rationale;
- potential contribution to portfolio growth;
- data availability and reliability;
- novelty relative to existing strategies;
- testability and falsifiability;
- expected research cost;
- potential capacity;
- diversification or correlation benefit;
- likelihood that the effect survives implementation costs.

Do not reward agents for generating many weak strategies.

---

# 7. Backtesting and validation standards

Backtests are research evidence, not proof of future profitability.

## 7.1 Mandatory controls

Every backtest must address:
- point-in-time data and availability timestamps;
- survivorship bias;
- look-ahead bias;
- selection and universe bias;
- corporate actions and delistings;
- symbol and contract mapping;
- futures rolls and expiration;
- options exercise, assignment and expiration;
- realistic bid/ask spreads and slippage;
- commissions, exchange fees and financing;
- market impact and capacity;
- borrow availability and borrow costs;
- margin and liquidation mechanics;
- taxes where material;
- settlement and trading calendars;
- missing data and stale prices;
- overlapping positions and portfolio interactions;
- parameter search and multiple-testing effects.

If a material control cannot be modeled, the limitation must be stated and the strategy cannot be promoted beyond the permitted research tier.

## 7.2 Test design

Use, where appropriate:
1. In-sample development period.
2. Validation period.
3. Untouched out-of-sample holdout.
4. Walk-forward or rolling-origin evaluation.
5. Multiple market regimes.
6. Stress periods and synthetic shocks.
7. Sensitivity to parameter changes.
8. Alternative data sources or instrument proxies.
9. Capacity and execution sensitivity.
10. Benchmark and simple baseline comparisons.

Never repeatedly tune against the same holdout and continue calling it out-of-sample.

## 7.3 Metrics

Report metrics appropriate to the strategy, including:
- CAGR and total return;
- volatility and downside volatility;
- maximum drawdown, drawdown duration and recovery;
- Sharpe, Sortino and Calmar ratios;
- win rate, payoff ratio and expectancy;
- turnover and holding period;
- exposure, leverage and gross/net notional;
- tail loss and expected shortfall;
- skewness and return concentration;
- time in market and cash usage;
- transaction cost and financing sensitivity;
- benchmark-relative and absolute contribution;
- capacity and liquidity;
- performance by regime and subperiod;
- calibration of predicted probabilities;
- tax-aware return where the data supports it.

No single metric is sufficient. NEXUS must show the return path and distribution, not just a headline Sharpe or CAGR.

## 7.4 Strategy promotion tiers

- **Q0 — Idea:** untested hypothesis.
- **Q1 — Research complete:** rationale and data audit complete.
- **Q2 — Backtest candidate:** preliminary historical result.
- **Q3 — Independently challenged:** Red Team review complete; flaws addressed or disclosed.
- **Q4 — Out-of-sample validated:** pre-registered criteria passed across holdout/walk-forward and robustness tests.
- **Q5 — Paper eligible:** execution model, risk limits, instrument mechanics and operational monitoring approved.
- **Q6 — Paper demonstrated:** sufficient live paper observations and operational evidence.
- **Q7 — Live review eligible:** eligible for human consideration only; never automatic live authority.

Promotion requires documented evidence. No strategy may promote itself. Minimum observation counts and durations must be specified per strategy class before the paper test begins, not chosen after seeing results.

## 7.5 Learning without overfitting

NEXUS may update:
- forecasts and uncertainty estimates;
- research priorities;
- model parameters under controlled experiments;
- strategy status;
- instrument eligibility;
- execution assumptions when new evidence supports a change.

It must not silently rewrite:
- the Constitution;
- risk limits;
- promotion criteria;
- data-quality rules;
- owner permissions;
- historical decision records.

Every material change must be versioned and compared against the prior version.

---

# 8. Paper-trading engine

## 8.1 Core rule: pre-register before outcome

Every hypothetical trade must be recorded before the subsequent market outcome is known.

At decision time, NEXUS records:
- unique trade ID;
- strategy and version;
- portfolio/sleeve ID;
- decision timestamp and timezone;
- data snapshot IDs;
- instrument and contract;
- side, intended quantity and sizing logic;
- order type and intended price;
- assumed fill model;
- stop, exit, hedge or invalidation rules;
- fees, spread, slippage and financing assumptions;
- rationale, confidence and dissent;
- risk-gate result.

The system must not backdate trades or claim that it would have entered at a price that was not available after the decision timestamp.

## 8.2 Simulation modes

The engine chooses the appropriate mode by instrument:

- **Liquid equities and ETFs:** market/limit order simulation with bid/ask, latency assumptions, partial fills, fees and market impact.
- **Less liquid equities:** conservative spread and participation assumptions; reject unrealistic fills.
- **Options:** contract-level data, bid/ask, implied volatility, Greeks, expiration, exercise, assignment, early exercise and liquidity.
- **Futures:** contract multiplier, tick size, margin, expiration, roll, settlement and delivery rules.
- **Commodities:** spot/futures distinction, curve structure, contango/backwardation, roll yield, collateral and delivery restrictions.
- **FX:** pair conventions, pip value, rollover/financing, session liquidity and spread.
- **Digital assets:** venue-specific fees, funding, custody/venue risk assumptions, fragmented liquidity and 24/7 calendar.
- **Prediction markets:** exact contract wording, price/probability interpretation, fees, spread, liquidity, resolution source, settlement timing and platform rules.
- **Illiquid or unsupported instruments:** timestamped hypothetical decision ledger only, with conservative mark assumptions; no claim of realistic executable performance.

## 8.3 Paper ledger states

`PROPOSED → ACCEPTED_BY_SIMULATOR → PARTIALLY_FILLED → FILLED → OPEN → REDUCED/CLOSED → SETTLED`

Alternative states include `REJECTED`, `CANCELED`, `EXPIRED`, `UNPRICEABLE`, `DATA_INVALID`, and `NEEDS_REVIEW`.

The simulator must preserve the original order and all subsequent state transitions. A simulated fill is never an actual brokerage fill.

## 8.4 Paper portfolio accounting

Maintain:
- cash and currency balances;
- positions and tax-lot analogues where useful;
- realized and unrealized P&L;
- dividends, coupons, distributions and corporate actions;
- fees, financing, borrow and margin;
- collateral and cash interest;
- contract expirations, rolls and settlements;
- open orders and partial fills;
- daily NAV and exposure snapshots.

Use independent reconciliation checks. P&L must reconcile to cash, position changes, corporate actions, financing and fees.

---

# 9. Shadow portfolio management

Shadow management is a first-class feature from the initial deployment.

## 9.1 Three parallel records

1. **Actual portfolio:** the owner's confirmed real holdings, cash flows and fills.
2. **Shadow-managed portfolio:** a simulated portfolio initialized from the actual portfolio snapshot, then changed only by NEXUS's timestamped hypothetical decisions.
3. **Autonomous strategy sleeves:** independent paper accounts for strategies discovered and tested by NEXUS.

Keep these ledgers separate. Do not merge simulated trades into actual holdings.

## 9.2 Shadow process

At initialization:
- ingest a user-confirmed brokerage statement, holdings export or equivalent source;
- record as-of timestamp, quantities, cash, cost basis and known tax lots;
- record open orders and unsettled transactions if available;
- mark every missing or estimated field;
- create an immutable initial portfolio snapshot.

On each shadow decision:
- compare every holding and reserve asset against alternatives;
- score maintain allocation as an active alternative;
- identify exact funding source for each proposed rotation;
- estimate taxes and friction when data supports it;
- record proposed trade before price outcome;
- simulate execution with conservative assumptions;
- calculate resulting portfolio exposures and expected growth;
- retain a complete before/after audit trail.

When actual portfolio changes, create a new actual snapshot. Do not overwrite the old state. NEXUS should explicitly decide whether to reset, merge, or maintain a parallel shadow path; the choice must be logged.

## 9.3 Shadow comparison

Report:
- actual portfolio total return and money-weighted return where possible;
- shadow portfolio return;
- difference in terminal value;
- contribution from allocation, selection, timing, cash, taxes and costs where measurable;
- drawdown and volatility;
- concentration and factor exposures;
- turnover and estimated friction;
- decisions that helped and hurt;
- decisions not taken and their counterfactual outcomes;
- confidence intervals and limitations.

Use matched starting capital, cash flows, valuation timestamps and fee/tax assumptions. Do not claim skill from unmatched comparisons.

---

# 10. Growth-focused portfolio objective and scoring

## 10.1 Primary measurement

Primary objective: maximize expected long-term terminal wealth.

Report expected terminal wealth as a range or distribution where possible, with:
- central estimate;
- upside and downside scenarios;
- probability assumptions;
- key drivers;
- uncertainty and model limitations.

Also report CAGR, drawdown, tail risk, liquidity, taxes and financing because these affect whether the growth path can be sustained.

## 10.2 Capital allocation test

Every proposed change must answer:
1. What is the exact capital source?
2. What is the destination?
3. What is the expected incremental growth contribution?
4. What is the probability and magnitude of permanent impairment?
5. What are taxes, spreads, financing, fees and other friction?
6. How does it change portfolio concentration, correlation and liquidity?
7. Does it beat holding the current position or reserve capital?
8. What evidence would invalidate it?
9. What is the opportunity cost of waiting?
10. What is the effect on expected terminal wealth of the total portfolio?

## 10.3 Scoring

Retain the original NEXUS 0-10 opportunity score as a decision aid, with explicit confidence and key drivers. Extend it for cross-asset strategies and instrument mechanics. The score is not a substitute for scenario analysis or the deterministic risk gate.

Default dimensions:
- expected long-term return / growth contribution;
- valuation or price attractiveness;
- thesis durability and evidence;
- portfolio fit and marginal growth contribution;
- timing and market structure;
- liquidity and execution;
- tax and financing efficiency;
- catalysts and information advantage;
- asymmetry and optionality.

The weighting may differ by asset class and strategy type. Changes must be documented and versioned.

---

# 11. Risk, safety and operational controls

Risk controls exist to prevent ruin, not to make NEXUS timid.

## 11.1 Independent deterministic risk gate

Before every simulated order, the Risk Gate checks:
- instrument capability tier;
- valid and fresh data;
- position and portfolio exposure;
- gross and net leverage;
- concentration and correlated exposure;
- liquidity and expected market impact;
- margin and collateral;
- loss and drawdown thresholds;
- strategy and sleeve limits;
- contract-specific risks;
- jurisdiction and product eligibility;
- unresolved operational or reconciliation failures.

LLM agents cannot override the Risk Gate.

## 11.2 Launch safety rules

- No live order API credentials.
- No withdrawal or transfer permissions.
- Brokerage credentials must never appear in prompts, source control, logs or agent memory.
- Use read-only portfolio access where possible.
- Store secrets in a proper secrets manager.
- Enforce role-based access and least privilege.
- Require multi-factor authentication for administrative access.
- Maintain an emergency stop that halts new simulated orders and all future live-capability pathways.
- Preserve audit logs independently of agent memory.
- If prices, holdings, contract mechanics or data lineage are uncertain, block affected actions or mark them unpriceable.
- Do not allow agents to modify risk limits, approval gates or promotion standards.

## 11.3 Kill switch and degraded modes

The owner must be able to:
- pause all agents;
- pause one strategy;
- disable one asset class or data source;
- stop new simulated orders;
- freeze portfolio recommendations;
- switch to read-only reporting;
- export the full decision and trade ledger.

On critical data or system failure, NEXUS should fail closed for new simulated orders and recommendations that depend on the failed component. It may continue safe monitoring and clearly labeled diagnostics.

---

# 12. Performance, learning and accountability

## 12.1 Three scoreboards

Maintain separate scoreboards for:
1. Actual portfolio.
2. Shadow-managed portfolio.
3. Each autonomous strategy sleeve.

Also maintain a consolidated view, but never let consolidated results hide a failing sleeve or strategy.

## 12.2 Evaluate both outcome and process

Measure:
- growth and terminal wealth;
- risk and drawdown;
- implementation realism;
- calibration and forecast accuracy;
- decision quality at the time;
- contribution to total portfolio;
- performance by regime;
- cost and tax estimates versus realized/simulated;
- operational reliability;
- strategy decay and capacity;
- frequency of invalid or rejected decisions.

Do not reward agents for trade count, bullishness, number of strategies, or short-term return alone.

## 12.3 Researcher leaderboard

Evaluate agents on:
- quality of falsifiable hypotheses;
- predictive calibration;
- reproducibility;
- robustness across regimes;
- ability to identify failure modes;
- useful discoveries;
- incremental portfolio contribution;
- quality of uncertainty estimates.

A researcher whose idea is disproven through a rigorous test can still receive process credit. A lucky unsupported prediction should not.

## 12.4 Permanent decision memory

Store:
- all hypotheses and versions;
- all backtests and artifacts;
- all paper trades and fills;
- all shadow decisions;
- agent votes and dissent;
- data snapshots and source lineage;
- model and prompt versions;
- strategy promotion decisions;
- policy changes and approvals;
- performance reviews and postmortems.

Never erase the original thesis or original decision record. Append corrections and outcome notes.

---

# 13. Staged autonomy and capital authorization

## Stage 0 — Build and verify
- No brokerage write access.
- Data pipeline, accounting, simulator and audit tests.
- Synthetic and historical test environments.
- Verify reproducibility and system recovery.

## Stage 1 — Autonomous research and paper trading
- NEXUS runs continuously.
- It discovers, tests, challenges and paper trades eligible strategies.
- It maintains strategy sleeves and performance records.
- No real portfolio changes.

## Stage 2 — Shadow management
- Load confirmed actual portfolio.
- NEXUS maintains the parallel shadow portfolio.
- It makes timestamped hypothetical decisions and compares outcomes.
- No real orders.

## Stage 3 — Human-reviewed live pilot (future, not enabled)
- Requires explicit owner authorization.
- Only specifically approved instruments and strategies.
- Small, pre-defined capital allocation.
- Human approves every real order initially.
- Read-only or narrowly scoped broker integration until independently reviewed.

## Stage 4 — Bounded delegated execution (future, not enabled)
- Requires separate written authorization and operational, legal, broker and security review.
- Explicit instrument whitelist, position caps, leverage caps, turnover caps, loss limits and order limits.
- Independent risk service has veto authority.
- No withdrawals or transfers.
- Human kill switch and incident procedures.
- Continuous audit and periodic reauthorization.

No stage advancement is automatic. A profitable short period is not sufficient. The owner explicitly authorizes any live-capital stage.

---

# 14. Dashboard and reporting

The dashboard should provide:

## Executive overview
- actual, shadow and paper portfolio values;
- growth and drawdown;
- cash and exposure;
- current market regime;
- current NEXUS operating state;
- system/data health;
- top opportunities;
- top risks and alerts.

## Research lab
- hypothesis queue;
- experiment status;
- backtest results;
- Red Team findings;
- promotion tier;
- research cost and priority.

## Paper trading
- open simulated positions and orders;
- realized/unrealized P&L;
- fill assumptions;
- fees, slippage, financing;
- trade history and strategy sleeve comparisons.

## Shadow portfolio
- actual versus shadow holdings;
- proposed changes;
- decision history;
- counterfactual performance;
- funding-source comparisons;
- post-decision exposure.

## Risk center
- leverage, concentration, liquidity and drawdown;
- instrument eligibility;
- data warnings;
- risk-gate blocks;
- operational incidents.

## Audit and governance
- decision journal;
- agent dissent;
- model and prompt versions;
- strategy promotion history;
- policy changes;
- permission state.

---

# 15. Repository structure for Claude Code

Suggested initial repository:

```text
nexus-ais/
├── README.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── CHANGELOG.md
├── docs/
│   ├── 00_MASTER_ARCHITECTURE.md
│   ├── 01_CONSTITUTION.md
│   ├── 02_AGENT_CHARTERS.md
│   ├── 03_OPERATING_LOOP.md
│   ├── 04_RESEARCH_STANDARDS.md
│   ├── 05_BACKTEST_STANDARDS.md
│   ├── 06_PAPER_TRADING.md
│   ├── 07_SHADOW_PORTFOLIO.md
│   ├── 08_RISK_AND_SAFETY.md
│   ├── 09_GOVERNANCE_AND_PROMOTION.md
│   └── 10_CLAUDE_CODE_BUILD_PLAN.md
├── config/
│   ├── app.yaml
│   ├── schedules.yaml
│   ├── asset_universe.yaml
│   ├── risk_limits.yaml
│   └── data_sources.yaml
├── agents/
│   ├── prism/
│   ├── atlas/
│   ├── orion/
│   ├── sentinel/
│   ├── horizon/
│   ├── quant_lab/
│   ├── red_team/
│   └── meridian/
├── services/
│   ├── orchestrator/
│   ├── ingestion/
│   ├── data_quality/
│   ├── instrument_registry/
│   ├── research/
│   ├── backtesting/
│   ├── execution_simulator/
│   ├── paper_portfolio/
│   ├── shadow_portfolio/
│   ├── risk_gate/
│   ├── accounting/
│   ├── audit/
│   └── notifications/
├── api/
├── dashboard/
├── data/
│   ├── schemas/
│   └── fixtures/
├── strategies/
│   ├── hypotheses/
│   ├── validated/
│   └── retired/
├── portfolios/
│   ├── actual_snapshot/
│   ├── shadow/
│   └── paper_sleeves/
├── memory/
│   ├── decision_journal/
│   ├── agent_dissent/
│   ├── research_notes/
│   └── postmortems/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── accounting/
│   ├── backtest_integrity/
│   ├── risk_gate/
│   └── end_to_end/
└── infra/
    ├── docker/
    ├── deployment/
    └── monitoring/
```

The repository can begin as a modular monolith. Split into independent services only when reliability, scale or operational boundaries justify it.

---

# 16. Implementation roadmap

Build in dependency order. Do not begin by creating many autonomous agents before the data, accounting, and audit foundations exist.

## Milestone 1 — Specification and project skeleton
- Create repository and configuration.
- Convert this document into governing files.
- Define data contracts, database schema and event types.
- Add secrets handling, logging, testing and CI.
- Add a no-live-trading permission invariant.

**Acceptance:** project boots locally; tests run; no secrets are committed; live trading is technically unavailable.

## Milestone 2 — Instrument registry and data foundation
- Implement canonical instrument identifiers.
- Add market calendar and asset-specific contract metadata.
- Add initial market-data adapters.
- Store source, timestamp, timezone, and ingestion lineage.
- Build stale-data and quality checks.

**Acceptance:** reproducible historical and current snapshots; invalid/stale data is detectable and blocks dependent decisions.

## Milestone 3 — Portfolio accounting and shadow state
- Implement holdings, cash, transactions, corporate actions and open orders.
- Import a confirmed portfolio snapshot.
- Add immutable snapshot history.
- Build shadow portfolio ledger.
- Add reconciliation tests.

**Acceptance:** holdings and NAV reconcile to supplied records within documented tolerances; shadow ledger never changes actual ledger.

## Milestone 4 — Simulator and paper ledger
- Implement order lifecycle.
- Add conservative fill models by supported instrument class.
- Add fees, spread, slippage, financing, margin and settlement.
- Add accounting reconciliation.

**Acceptance:** deterministic replay produces the same result from the same data, code and configuration; no look-ahead in fills.

## Milestone 5 — Research and backtest framework
- Hypothesis registry.
- Reproducible experiment runner.
- Walk-forward and holdout support.
- Bias and robustness checks.
- Strategy artifacts and promotion workflow.

**Acceptance:** each result is reproducible and has a complete data/code/config lineage; promotion requires independent review.

## Milestone 6 — Agent layer
- Implement role contracts and structured outputs.
- Connect agents to research and portfolio APIs.
- Add dissent and Red Team workflow.
- Keep deterministic calculations outside LLM responses.

**Acceptance:** each agent's output is logged; MERIDIAN cannot bypass risk gate or permissions.

## Milestone 7 — Continuous orchestration
- Add scheduler, event triggers, retries and idempotency.
- Add health monitoring and notifications.
- Add pause/resume and kill switch.
- Deploy to always-on runtime.

**Acceptance:** system survives restarts, records missed jobs, prevents duplicate simulated orders, and can be safely paused.

## Milestone 8 — Dashboard and performance attribution
- Executive view.
- Research and paper-trading views.
- Shadow portfolio comparison.
- Risk and audit views.

**Acceptance:** actual, shadow and strategy performance are separately visible and reconcilable.

## Milestone 9 — Shadow validation period
- Operate with real portfolio snapshot and paper-only authority.
- Review decisions, data gaps, execution realism and system failures.
- Calibrate only under versioned governance.

**Acceptance:** owner receives a transparent operating history; no automatic promotion to live authority.

---

# 17. Initial Claude Code instructions

Use the following as the first implementation task after placing this specification in the repository:

> Read `docs/00_MASTER_ARCHITECTURE.md` completely. Treat it as the governing product and system specification. Do not implement live trading, broker write access, money movement, withdrawals, or transfer capabilities. Build NEXUS AIS in dependency order, starting with repository skeleton, configuration, typed domain models, database migrations, event/audit schema, instrument registry, data-quality contracts, and tests. Before adding LLM agents, build deterministic portfolio accounting, immutable snapshots, risk-gate interfaces, and a paper-trading ledger. Preserve separation between actual holdings, shadow portfolio, and autonomous strategy sleeves. Every simulated decision and order must be timestamped and reproducible. Never fabricate data or claim a job ran when it did not. If an implementation choice is ambiguous, document the tradeoff and choose the simplest reliable, testable design. Do not silently weaken requirements. Create a milestone checklist and report acceptance-test results at each stage.

## 17.1 Claude Code working rules

- Work in small, testable milestones.
- Read the relevant governing documents before changing behavior.
- Propose a plan before large architectural changes.
- Do not invent API capabilities or data entitlements.
- Keep provider-specific code behind adapters.
- Never place secrets in prompts, code, logs, fixtures or Git.
- Add tests for every accounting, risk and state-transition rule.
- Preserve migration paths and backward compatibility.
- Do not mark a milestone complete without running its tests.
- Record assumptions, limitations and unresolved questions.

---

# 18. Initial operating configuration

The following settings are intentionally left configurable rather than guessed:

- Actual brokerage/custodian and read-only data connection.
- Confirmed portfolio snapshot and tax-lot data.
- Portfolio base currency and tax jurisdiction.
- Owner's investment horizon and liquidity requirements.
- Maximum acceptable drawdown and other survival constraints.
- Initial market-data vendors and licenses.
- Cloud provider, budget and uptime target.
- Prediction-market and digital-asset platform eligibility.
- Notification channel and escalation preferences.

Until confirmed, use synthetic fixtures and public or properly licensed market data for development. Do not infer the owner's current holdings from an old portfolio pack or treat an ETF-only profile as the aggressive-growth mandate.

---

# 19. Definition of done for the initial system

NEXUS AIS v2.0 initial release is complete when it can:

1. Run continuously in an always-on environment.
2. Ingest and validate data across its configured research universe.
3. Maintain an instrument registry and distinguish research from paper eligibility.
4. Discover and register falsifiable hypotheses.
5. Run reproducible backtests with point-in-time controls.
6. Subject candidates to independent adversarial review.
7. Operate multiple paper strategy sleeves.
8. Record every hypothetical decision before the market outcome.
9. Maintain a separate shadow-managed version of the owner's actual portfolio.
10. Reconcile cash, positions, simulated fills and portfolio NAV.
11. Compare actual, shadow and strategy performance.
12. Explain decisions, funding sources, friction, dissent and uncertainty.
13. Preserve permanent audit and research memory.
14. Pause safely and fail closed on critical data or operational errors.
15. Operate with no real-trading or money-movement permissions.

**The initial release is not complete merely because agents can talk to one another. It is complete when its data, accounting, simulation, audit and safety controls are reliable enough that its research conclusions can be trusted and independently checked.**

---

# 20. Constitutional statement

NEXUS AIS exists to grow capital over time.

It should search relentlessly, question accepted assumptions, discover new strategies, test them rigorously, and allocate simulated capital to the best opportunities it can defend. It should not be loyal to an asset, strategy, market, agent, model, or prior recommendation. It should be loyal to evidence and the owner's growth objective.

It must distinguish a real edge from noise, a valid paper fill from an imaginary one, a strong strategy from a lucky backtest, and a high expected return from a path that risks permanent ruin.

**Research broadly. Test ruthlessly. Record everything. Learn continuously. Compound intelligently.**
