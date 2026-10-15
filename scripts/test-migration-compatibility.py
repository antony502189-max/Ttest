"""Regression checks for rollback protection without database dependencies."""
import ast
import runpy
import unittest
from pathlib import Path

guard = runpy.run_path(str(Path(__file__).with_name("check-migration-compatibility.py")))
Migration = guard["Migration"]
inspect = guard["inspect_future_migration"]
ancestor_tables = guard["new_ancestor_tables"]


def migration(revision, parent, operations):
    source = "def upgrade():\n" + "\n".join("    " + line for line in operations.splitlines())
    return Migration(Path(revision + ".py"), ast.parse(source), revision, (parent,) if parent else ())


class RollbackProtectionTests(unittest.TestCase):
    def test_frozen_history_is_not_reinterpreted_as_future_ddl(self):
        migrations = {
            'old': migration('old', None, "op.create_table('payment_orders')"),
            'deployed': migration('deployed', 'old', "op.drop_constraint('ck', 'payment_orders')"),
            'future': migration('future', 'deployed', "op.drop_constraint('ck', 'payment_orders')"),
        }
        errors = guard['inspect_unreleased_migrations'](migrations, {'old', 'deployed'})
        self.assertEqual(len(errors), 1)
        self.assertIn('future.py', errors[0])
        self.assertEqual(guard['inspect_unreleased_migrations'](migrations, set(migrations)), [])

    def test_constraints_on_unreleased_ancestor_table_are_allowed(self):
        for operation in (
            "op.drop_constraint('ck', 'payment_orders', type_='check')",
            "op.create_check_constraint('ck', 'payment_orders', 'amount > 0')",
            "op.create_unique_constraint('uq', 'payment_orders', ['intent'])",
            "op.create_foreign_key('fk', 'payment_orders', 'users', ['owner'], ['id'])",
        ):
            with self.subTest(operation=operation):
                self.assertEqual(inspect(migration('next', 'new', operation), {'payment_orders'}), [])

    def test_existing_and_unknown_table_constraints_stay_forbidden(self):
        for table in ("'users'", "table_name"):
            operation = f"op.drop_constraint('ck', {table}, type_='check')"
            self.assertTrue(inspect(migration('next', 'new', operation), {'payment_orders'}))

    def test_destructive_operations_and_raw_sql_stay_forbidden_even_on_new_table(self):
        for operation in (
            "op.drop_table('payment_orders')",
            "op.drop_column('payment_orders', 'amount')",
            "op.execute('ALTER TABLE payment_orders DROP CONSTRAINT ck')",
            "op.execute('DELETE FROM payment_orders')",
            "op.create_check_constraint('ck', 'payment_orders', 'true', schema='other')",
        ):
            with self.subTest(operation=operation):
                self.assertTrue(inspect(migration('next', 'new', operation), {'payment_orders'}))

    def test_only_direct_unreleased_ancestor_tables_are_eligible(self):
        migrations = {
            'old': migration('old', None, "op.create_table('users')"),
            'new': migration('new', 'old', "op.create_table('payment_orders')"),
            'next': migration('next', 'new', "op.create_table('same_revision')"),
            'unrelated': migration('unrelated', 'old', "op.create_table('other_branch')"),
        }
        self.assertEqual(ancestor_tables(migrations, 'next', {'old'}), {'payment_orders'})
        self.assertEqual(ancestor_tables(migrations, 'next', {'old', 'new'}), set())

    def test_conditional_or_schema_qualified_creation_is_not_eligible(self):
        for operation in ("if enabled:\n    op.create_table('payment_orders')",
                          "op.create_table('payment_orders', schema='other')"):
            migrations = {
                'old': migration('old', None, 'pass'),
                'new': migration('new', 'old', operation),
                'next': migration('next', 'new', 'pass'),
            }
            self.assertEqual(ancestor_tables(migrations, 'next', {'old'}), set())


if __name__ == '__main__':
    unittest.main()
