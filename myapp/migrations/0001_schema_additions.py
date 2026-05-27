from django.db import migrations


def add_columns_and_tables(apps, schema_editor):
    db_engine = schema_editor.connection.vendor

    if db_engine == 'postgresql':
        schema_editor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='attendance_logs' AND column_name='scanned_out_at'
                ) THEN
                    ALTER TABLE attendance_logs ADD COLUMN scanned_out_at TIMESTAMP WITH TIME ZONE;
                END IF;
            END$$;
        """)
        schema_editor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                admin_id UUID REFERENCES admins(id) ON DELETE SET NULL,
                action VARCHAR(100) NOT NULL,
                target VARCHAR(255),
                description TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """)
    elif db_engine == 'sqlite':
        try:
            schema_editor.execute(
                "ALTER TABLE attendance_logs ADD COLUMN scanned_out_at DATETIME;"
            )
        except Exception:
            pass
        schema_editor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id CHAR(36) PRIMARY KEY,
                admin_id CHAR(36) REFERENCES admins(id),
                action VARCHAR(100) NOT NULL,
                target VARCHAR(255),
                description TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)


def reverse_columns_and_tables(apps, schema_editor):
    db_engine = schema_editor.connection.vendor
    if db_engine == 'postgresql':
        schema_editor.execute(
            "ALTER TABLE attendance_logs DROP COLUMN IF EXISTS scanned_out_at;"
        )
        schema_editor.execute("DROP TABLE IF EXISTS activity_logs;")


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.RunPython(add_columns_and_tables, reverse_columns_and_tables),
    ]
