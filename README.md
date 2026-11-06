# jobmarket

Reproducible, observable data pipeline for the Ukrainian IT job market:
daily scraping into an immutable bronze layer, silver cleaning/dedup/SCD2, gold marts in dbt.

Status: day 1 scaffold. The full plan lives in the Obsidian vault (`~/Documents/Projects/Dataward`).

## Quick start

```bash
make install
make lint
make test
```
