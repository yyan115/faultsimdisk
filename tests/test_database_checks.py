"""Regression checks for database validation; no module or root access needed."""

import subprocess
import unittest
from pathlib import Path


COMMON = Path(__file__).resolve().parents[1] / "scripts/database-test-common.sh"
SQLITE_IO_ERROR = "Error: stepping, disk I/O error (10)"
POSTGRES_IO_ERROR = 'PANIC:  could not fdatasync file "000000010000000000000001": Input/output error'


class DatabaseChecks(unittest.TestCase):
    def run_shell(self, body, *args):
        return subprocess.run(
            [
                "bash", "-c",
                'set -euo pipefail\nsource "$1"\nshift\n' + body,
                "database-check-test", str(COMMON), *map(str, args),
            ],
            text=True, capture_output=True, timeout=5,
        )

    def check_failure(self, database, rc, output, log=""):
        if database == "sqlite":
            body = 'line=$(sqlite_failure_line "$1" "$2"); printf "%s\\n" "$line"'
        else:
            body = 'line=$(postgres_failure_line "$1" "$2" "$3"); printf "%s\\n" "$line"'
        return self.run_shell(body, rc, output, log)

    def test_timing_success_returns_only_elapsed_time(self):
        result = self.run_shell(
            'elapsed=$(time_command_ms bash -c "$1"); printf "%s\\n" "$elapsed"',
            "echo command-output",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"^\d+\n$")

    def test_timing_failure_propagates_from_command_substitution(self):
        for command in ["exit 23", "sleep 0.05; echo transaction-failed >&2; exit 23"]:
            with self.subTest(command=command):
                result = self.run_shell(
                    'elapsed=$(time_command_ms bash -c "$1"); echo FALSE-PASS',
                    command,
                )
                self.assertEqual(result.returncode, 23, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_sqlite_accepts_storage_error(self):
        result = self.check_failure("sqlite", 10, SQLITE_IO_ERROR)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), SQLITE_IO_ERROR)

    def test_sqlite_rejects_success_and_unrelated_failures(self):
        for rc, output in [
            (0, SQLITE_IO_ERROR),
            (1, "Error: no such table: events"),
            (1, "Error: database is locked (5)"),
            (127, "sqlite3: command not found"),
            (1, ""),
        ]:
            with self.subTest(rc=rc, output=output):
                result = self.check_failure("sqlite", rc, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_postgres_accepts_storage_error_from_client(self):
        result = self.check_failure("postgres", 2, POSTGRES_IO_ERROR)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), POSTGRES_IO_ERROR)

    def test_postgres_accepts_disconnect_with_server_storage_error(self):
        result = self.check_failure(
            "postgres", 2, "server closed the connection unexpectedly",
            "LOG: preceding entry\n2026-09-27 06:04:27 UTC [21] " + POSTGRES_IO_ERROR,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), POSTGRES_IO_ERROR)

    def test_postgres_rejects_success_timeout_and_command_errors(self):
        for rc in [0, 124, 125, 126, 127, 137, 143]:
            with self.subTest(rc=rc):
                result = self.check_failure("postgres", rc, POSTGRES_IO_ERROR, POSTGRES_IO_ERROR)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")

    def test_postgres_rejects_unrelated_errors_and_unconfirmed_disconnects(self):
        for output in [
            "psql: error: connection failed: No such file or directory",
            "server closed the connection unexpectedly",
            'ERROR: relation "events" does not exist',
            "FATAL: password authentication failed",
            "",
        ]:
            with self.subTest(output=output):
                result = self.check_failure("postgres", 2, output, "LOG: database system is ready")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
