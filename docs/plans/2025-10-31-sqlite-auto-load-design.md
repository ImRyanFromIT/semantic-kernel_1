# SQLite Auto-Load Design

**Date**: 2025-10-31
**Status**: Approved
**Goal**: Automatically load `data/srm_index.csv` into SQLite when starting the chatbot with `VECTOR_STORE_TYPE=sqlite`

## Overview

When running `run_chatbot.py` with SQLite as the vector store, automatically load SRM data from `data/srm_index.csv` during startup. This ensures the SQLite store is populated with fresh data every time the chatbot starts.

## Architecture

### High-Level Flow

```
run_chatbot.py startup
  ↓
Check VECTOR_STORE_TYPE from .env
  ↓
If 'sqlite':
  - Create SQLiteSearchStore (already done by factory)
  - Create SQLiteDataLoader
  - Load data/srm_index.csv
  - If error: STOP startup with clear message
  - If success: Print count of loaded records
  ↓
Continue normal startup
```

### Files to Create/Modify

1. **New**: `src/data/sqlite_data_loader.py` - SQLite-specific data loader
2. **Modify**: `run_chatbot.py` - Update `startup_event()` to handle SQLite

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Data loading strategy | Always load on startup | Simple, ensures fresh data, matches in_memory pattern |
| Loader implementation | New SQLiteDataLoader class | Clean separation, won't affect existing code |
| Error handling | Fail fast | Forces immediate fix of data issues during development |
| Record creation | Simple objects matching CSV structure | Works with existing SQLiteSearchStore expectations |

## Implementation Details

### SQLiteDataLoader Class

**File**: `src/data/sqlite_data_loader.py`

```python
class SQLiteDataLoader:
    """Load SRM data from srm_index.csv for SQLite store."""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def load_and_index(self, csv_path: str) -> int:
        """Load CSV and index in SQLite. Returns record count."""
```

**Record Creation Pattern**:

```python
class SRMIndexRecord:
    """Simple record matching srm_index.csv structure."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
```

**CSV Processing Logic**:

1. Check if `csv_path` exists → raise `FileNotFoundError` if not
2. Open CSV with `csv.DictReader` (handles encoding automatically)
3. For each row, create `SRMIndexRecord` with all CSV columns:
   - `id` = row['SRM_ID']
   - `SRM_ID` = row['SRM_ID']
   - `Name` = row['Name']
   - `Description` = row['Description']
   - `Team` = row['Team']
   - `Type` = row['Type']
   - `URL_Link` = row['URL_Link']
   - `TechnologiesTeamWorksWith` = row.get('TechnologiesTeamWorksWith', '')
   - `owner_notes` = '' (empty, for future use)
   - `hidden_notes` = '' (empty, for future use)
4. Collect all records into a list
5. Call `await vector_store.upsert(records)`
6. Return count

**Error Handling**:
- File not found → `FileNotFoundError` with clear message
- CSV malformed → Let python's csv module raise its exception (fail fast)
- No try/except wrapping (errors bubble up to startup_event)

### Integration with run_chatbot.py

**Location**: `run_chatbot.py` lines 142-156 (the data loading section in `startup_event()`)

**Current Code**:
```python
store_type = os.getenv('VECTOR_STORE_TYPE', 'azure_search').lower()

if store_type == 'in_memory':
    # Load SRM catalog from CSV for in-memory store
    print("[*] Loading SRM catalog from CSV...")
    data_loader = SRMDataLoader(app.state.vector_store)
    num_records = await data_loader.load_and_index("data/srm_catalog.csv")
    print(f"[+] Loaded and indexed {num_records} SRM records")
else:
    # Azure AI Search - data already exists in the index
    print("[*] Using existing Azure AI Search index...")
    await app.state.vector_store.ensure_collection_exists()
    print("[+] Azure AI Search index ready")
```

**New Code**:
```python
store_type = os.getenv('VECTOR_STORE_TYPE', 'sqlite').lower()

if store_type == 'sqlite':
    # Load SRM index from CSV for SQLite store
    print("[*] Loading SRM data from srm_index.csv...")
    from src.data.sqlite_data_loader import SQLiteDataLoader
    data_loader = SQLiteDataLoader(app.state.vector_store)
    num_records = await data_loader.load_and_index("data/srm_index.csv")
    print(f"[+] Loaded and indexed {num_records} SRM records")

elif store_type == 'in_memory':
    # Load SRM catalog from CSV for in-memory store
    print("[*] Loading SRM catalog from CSV...")
    data_loader = SRMDataLoader(app.state.vector_store)
    num_records = await data_loader.load_and_index("data/srm_catalog.csv")
    print(f"[+] Loaded and indexed {num_records} SRM records")

else:
    # Azure AI Search - data already exists in the index
    print("[*] Using existing Azure AI Search index...")
    await app.state.vector_store.ensure_collection_exists()
    print("[+] Azure AI Search index ready")
```

**Changes**:
1. Add `if store_type == 'sqlite':` branch at the top (before in_memory)
2. Import `SQLiteDataLoader`
3. Load from `data/srm_index.csv` instead of `data/srm_catalog.csv`
4. Keep existing in_memory and azure_search branches unchanged

## Startup Behavior

**Success Path**:
```
[*] Creating vector store...
[*] Using SQLite FTS5 store (db_path: :memory:)
[+] Vector store created
[*] Loading SRM data from srm_index.csv...
[+] Loaded and indexed 55 SRM records
```

**Failure Path** (CSV missing):
```
[*] Creating vector store...
[+] Vector store created
[*] Loading SRM data from srm_index.csv...
FileNotFoundError: SRM data file not found: data/srm_index.csv
(Startup stops here)
```

**Performance Impact**:
- Startup time increase: ~1-2 seconds for 55 records
- Acceptable for development/testing use

## Testing Strategy

1. **Unit Test**: Test `SQLiteDataLoader.load_and_index()` with sample CSV
2. **Integration Test**: Start chatbot, verify data loaded
3. **Error Test**: Remove CSV, verify startup fails with clear message
4. **Manual Test**: Query the chatbot to confirm searches work

## Future Enhancements (Out of Scope)

- Conditional loading (only if DB empty) for persistent SQLite files
- Support for incremental updates
- Data validation/transformation during load
- Progress reporting for large datasets

## References

- Working demo: `demo_srm_search.py` (proven record creation pattern)
- Existing loader: `src/data/data_loader.py` (pattern reference)
- SQLite store: `src/memory/sqlite_search_store.py` (field expectations)
