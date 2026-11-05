# NEXUS AIS (Stage 0)

Autonomous research, paper-trading and shadow-portfolio system. **No live trading, no broker write access,
no money movement.** Spec: `docs/00_MASTER_ARCHITECTURE.md`. Progress: `docs/MILESTONES.md`.

```
python -m nexus boot      # verify governance lock + config + audit chain, migrate DB, record boot
python -m nexus verify    # verify governance and the audit hash chain
python -m nexus status
python -m nexus lock      # HUMAN ONLY: re-pin governed files after an approved change
python -m pytest tests/nexus
```
Secrets come only from the environment and are never stored, logged or committed.
