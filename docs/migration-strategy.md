# Database Migration Strategy: Adding first_name and last_name

## Scenario

API v2 needs `first_name` and `last_name` fields instead of just `username`.
We need to migrate the existing database without losing data.

## Migration Options

### Option A: Kubernetes Job (Recommended for Learning)

Create a batch Job that runs SQL migration commands.
- **Pros**: Declarative, repeatable, version-controlled
- **Cons**: Requires the Job manifest in your repo

### Option B: kubectl exec (Quick Development)

```bash
kubectl exec -it mysql-0 -n mysql-ns -- mysql -u root -prootpassword testdb
```

Then run SQL commands manually.
- **Pros**: Fast for testing
- **Cons**: Not repeatable, error-prone

### Option C: Use a Migration Tool (Production)

Tools like Flyway, Liquibase, Alembic (Python), or golang-migrate.
- **Pros**: Versioned migrations, rollback support
- **Cons**: More complex setup

## Migration Steps

1. Add `first_name` and `last_name` columns (nullable)
2. Populate them from existing `username` data
3. Make `first_name` NOT NULL
4. Update the application code to use new fields
5. Test backward compatibility with older API versions

## Rollback Plan

```sql
ALTER TABLE users DROP COLUMN last_name;
ALTER TABLE users DROP COLUMN first_name;
```

## Data Migration Logic

| Current username | first_name | last_name |
|---|---|---|
| alice | alice | NULL |
| bob.smith | bob | smith |
| charlie.brown | charlie | brown |
