# Elasticsearch Index Rebuild — RE-Mat Clowder

A step-by-step guide for safely rebuilding the `clowder` Elasticsearch index when mappings become corrupted or need restructuring.

---

## Overview

The `clowder` index stores ~8,500 documents under a single type `clowder_object`. The physical index is `clowder_v2` (or the next version), exposed via the alias `clowder`. Always rebuild into a new versioned index and swap the alias at the end — never modify the live index in place.

A [postman collection](ClowderElasticSearch.postman_collection.json) is provided for convenience.

---

## Step 1 — Explore the Current State

Before touching anything, understand what's there.

```
GET http://localhost:9200/_cat/indices?v&pretty
GET http://localhost:9200/_cluster/health?pretty
GET http://localhost:9200/clowder/_mapping?pretty
GET http://localhost:9200/clowder/_settings?pretty
GET http://localhost:9200/_aliases?pretty
```

Things to look for:
- Cluster status (yellow = unassigned replicas, usually fine on single node)
- Duplicate or conflicting field types in the mappings
- Which extractors are present under `metadata`
- Whether `numeric_detection` is on (it should be off)

---

## Step 2 — Create the New Index

Create the next versioned index (e.g. `clowder_v3`) with clean settings and mappings.

```
PUT http://localhost:9200/clowder_v3
```

Key settings to always include:

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.mapping.ignore_malformed": true,
    "analysis": {
      "analyzer": {
        "email_analyzer": {
          "type": "custom",
          "tokenizer": "uax_url_email"
        },
        "default": {
          "type": "standard"
        }
      }
    }
  },
  "mappings": {
    "clowder_object": {
      "numeric_detection": false,
      "dynamic": false,
      ...
    }
  }
}
```

**Mapping rules:**
- `numeric_detection: false` — prevents ES from auto-typing numeric-looking strings as numbers
- `dynamic: false` — prevents new unknown fields from being auto-mapped with bad types
- Only include the two active extractor namespaces under `metadata`:
  - `https://re-mat_clowder_ncsa_illinois_edu/api/extractors/remat_experiment_from_excel`
  - `https://re-mat_clowder_ncsa_illinois_edu/api/extractors/remat_parameters_from_txt`
- Map all numeric measurement fields explicitly as `double`
- Map all ID and enum fields with `"index": "not_analyzed"` for exact matching
- Use `"analyzer": "email_analyzer"` on `creator_email`

The response should be `{"acknowledged": true}`.

---

## Step 3 — Reindex

Copy all documents from the live index into the new one.

```
POST http://localhost:9200/_reindex
```

```json
{
  "source": { "index": "clowder" },
  "dest":   { "index": "clowder_v3" }
}
```

Check the response for:
- `"total"` matches your expected doc count
- `"failures": []` — must be empty
- `"created"` == `"total"`, `"updated"` == 0

---

## Step 4 — Verify

**Check index health and doc count:**
```
GET http://localhost:9200/_cat/indices?v&pretty
```
The new index should be `green` with the same doc count as the old one. Deleted doc tombstones from the old index will not carry over — this is expected and correct.

**Spot-check documents:**
```
GET http://localhost:9200/clowder_v3/_search?pretty
{
  "size": 5,
  "query": { "match_all": {} }
}
```

Confirm that `metadata` fields are populated correctly on docs that have extractor output.

---

## Step 5 — Swap the Alias

Atomically move the `clowder` alias from the old index to the new one. If the old index was itself a physical index (not an alias), delete it first, then add the alias.

**If the old `clowder` was an alias:**
```
POST http://localhost:9200/_aliases
{
  "actions": [
    { "remove": { "index": "clowder_v2", "alias": "clowder" } },
    { "add":    { "index": "clowder_v3", "alias": "clowder" } }
  ]
}
```

**If the old `clowder` was a physical index (delete it first):**
```
DELETE http://localhost:9200/clowder

POST http://localhost:9200/_aliases
{
  "actions": [
    { "add": { "index": "clowder_v3", "alias": "clowder" } }
  ]
}
```

**Verify:**
```
GET http://localhost:9200/_aliases?pretty
```

You should see `clowder_v3` with the `clowder` alias attached. All application traffic to `clowder` now routes to `clowder_v3` transparently.

---

## Step 6 — Clean Up

Once you've confirmed the application is working correctly against the new index, delete the old physical index if it still exists:

```
DELETE http://localhost:9200/clowder_v2
```

---

## Common Pitfalls

| Problem | Cause | Fix |
|---|---|---|
| Cluster stays yellow | Replicas can't be assigned on a single node | Set `number_of_replicas: 0` — expected for dev |
| Type conflicts in mappings | `numeric_detection: true` + bad source data | Always set `numeric_detection: false` |
| Unknown fields auto-mapped badly | `dynamic: true` (the default) | Set `dynamic: false` at the index and extractor namespace level |
| Reindex failures | Source doc has a field that conflicts with new explicit mapping | Check `failures[]` in reindex response; adjust mapping or use `ignore_malformed` |
| `Sample Mass (mg)` stored as string | Source data has unit embedded in value (e.g. `"6.150 mg"`) | Leave as `string`; can't be fixed at the mapping level without source data cleanup |

---

## Current Index State (as of May 2026)

| Item | Value |
|---|---|
| Physical index | `clowder_v2` |
| Alias | `clowder` |
| Doc count | ~8,504 |
| Shards / Replicas | 1 / 0 |
| Active extractors | `remat_experiment_from_excel`, `remat_parameters_from_txt` |
| Removed extractors | `remat_batch_experiment_from_excel`, `remat_batch_parameters_from_txt`, `remat_DSC_csv_stripper`, `fake_extractor` |
