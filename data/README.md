# data/

Runtime data directory for UNHCR Refugee Statistics.

## Structure

```
data/
├── scripts/
│   ├── unhcr_downloader.py    # Full UNHCR API downloader (all endpoints)
│   ├── enrich_downloader.py   # Targeted per-country enrichment downloader
│   ├── query_data.py          # Runtime query layer (used by agent tools)
│   └── refresh_data.py        # Staleness check + re-download
├── raw/                       # Raw API responses (gitignored, regenerate)
│   └── .gitkeep
└── processed/                 # Merged flat JSON per endpoint (gitignored)
    └── .gitkeep
```

## Setup

```bash
cd data/scripts

# First run — downloads all UNHCR data (~5-7 min):
python3 unhcr_downloader.py --all

# Then enrich countries.json with live stats (~4 min):
python3 enrich_downloader.py
# Output: specs/data/countries_enriched.json

# Annual refresh:
python3 refresh_data.py
```

## Data license

All UNHCR data is published under **CC BY 4.0**.
Source: [UNHCR Refugee Statistics API](https://api.unhcr.org/population/v1/)
Attribution required in any public-facing use.
