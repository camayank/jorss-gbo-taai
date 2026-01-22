# Database Migrations

This directory contains SQL migration scripts to evolve the database schema over time.

## Running Migrations

### Apply All Pending Migrations

```bash
python migrations/run_migration.py
```

This will:
1. Check which migrations have been applied
2. Show you the list of pending migrations
3. Ask for confirmation
4. Apply all pending migrations in order

### Apply a Specific Migration

```bash
python migrations/run_migration.py 001_add_user_workflow_columns.sql
```

### Check Migration Status

```bash
python migrations/run_migration.py
```

If all migrations are applied, it will show the status and exit.

## Migration Files

Migrations are numbered sequentially:

- `001_add_user_workflow_columns.sql` - Adds user_id, workflow_type, return_id columns

## Creating New Migrations

1. Create a new SQL file with the next sequential number:
   ```
   002_my_new_migration.sql
   ```

2. Write your migration SQL:
   ```sql
   -- Migration: Brief description
   -- Date: YYYY-MM-DD
   -- Purpose: What this migration does

   ALTER TABLE my_table ADD COLUMN new_column TEXT;
   CREATE INDEX idx_new_column ON my_table(new_column);
   ```

3. Test the migration on a development database first

4. Run the migration:
   ```bash
   python migrations/run_migration.py 002_my_new_migration.sql
   ```

## Rollback

⚠️ **SQLite does not support ALTER TABLE DROP COLUMN before version 3.35.0**

To rollback a migration:
1. Create a new migration that reverses the changes
2. Or restore from a backup

Always backup your database before running migrations:
```bash
cp tax_filing.db tax_filing.db.backup.$(date +%Y%m%d_%H%M%S)
```

## Migration Tracking

Migrations are tracked in the `schema_migrations` table:

```sql
SELECT * FROM schema_migrations ORDER BY applied_at;
```

## Best Practices

1. **Always backup** before running migrations in production
2. **Test migrations** on a copy of the production database first
3. **Keep migrations small** - one logical change per migration
4. **Never modify** existing migration files after they've been applied
5. **Use transactions** - migrations run in a transaction and rollback on error
6. **Document** - include comments explaining what and why

## Example Workflow

```bash
# Backup database
cp tax_filing.db tax_filing.db.backup

# Check status
python migrations/run_migration.py

# Apply migrations
python migrations/run_migration.py

# Verify changes
sqlite3 tax_filing.db "PRAGMA table_info(session_states);"
```

## Troubleshooting

### Migration fails with "table already has column"

The column was added manually or in a previous run. Safe to ignore if the schema matches.

### Migration tracking table missing

Run any migration and it will be created automatically.

### Database locked

Close all connections to the database (stop the web server) before running migrations.
