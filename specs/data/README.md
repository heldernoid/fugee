# specs/data/

Curated reference data for the Refuge country recommendation system.

## Files

| File | Description |
|---|---|
| `countries.json` | Master country dataset — 146 signatories + 23 non-signatories. Curated layer with asylum procedures, legal aid orgs, processing times, tier ratings. |
| `countries_enriched.json` | Generated — `countries.json` + UNHCR API stats (acceptance rates, application volumes, refugee populations). Run `data/scripts/enrich_downloader.py` to produce. |

## countries.json schema

```json
{
  "_meta": { ... },
  "signatories": {
    "KEN": {
      "name", "iso3", "flag", "tier",
      "convention": { "1951", "1967", "oau_1969", "year", "notes" },
      "asylum_system": {
        "body", "unhcr_present", "unhcr_office", "procedure",
        "work_right", "education_right", "movement",
        "processing_months": { "min", "max", "typical" },
        "appeal", "legal_aid", "orgs", "steps", "docs_required"
      },
      "profile": { "languages", "hosts", "integration", "safety", "economic_access" },
      "stats": {
        "acceptance_rate_recent",
        "total_protection_rate_recent",
        "applications_last_year",
        "refugee_population_total",
        "data_year"
      }
    }
  },
  "non_signatories": {
    "UAE": {
      "tier": "non_signatory_viable_temporary",
      "alternative_pathways": { ... },
      "strategic_guidance": "..."
    }
  }
}
```

## Tier system

| Tier | Description |
|---|---|
| 1 | Major active system — full procedures, legal aid, contacts |
| 2 | Active system — moderate volume or significant for specific profiles |
| 3 | Functioning but low volume, primarily transit or origin |
| 4 | Signatory in name only — micro-state, collapsed, or non-functional |

Non-signatory tiers: `non_signatory_viable_temporary`, `non_signatory_skilled_only`,
`non_signatory_resettlement_pipeline`, `non_signatory_not_recommended`.
