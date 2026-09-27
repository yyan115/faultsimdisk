#!/usr/bin/env bash

# Explicit returns keep failures visible inside command substitutions.
time_command_ms() {
	local start_ns end_ns
	start_ns=$(date +%s%N) || return "$?"
	"$@" >/dev/null || return "$?"
	end_ns=$(date +%s%N) || return "$?"
	printf '%s\n' "$(( (end_ns - start_ns) / 1000000 ))"
}

sqlite_failure_line() {
	local rc="$1" output="$2" line
	if (( rc == 0 )); then
		echo "FAIL: SQLite transaction succeeded with write_fail_pct=100" >&2
		return 1
	fi
	if ! line=$(grep -F -m1 'disk I/O error' <<< "$output"); then
		printf 'FAIL: expected a SQLite I/O error, got exit %s:\n%s\n' "$rc" "$output" >&2
		return 1
	fi
	printf '%s\n' "$line"
}

postgres_failure_line() {
	local rc="$1" output="$2" new_log="$3" line
	case "$rc" in
		0)
			echo "FAIL: PostgreSQL transaction succeeded with write_fail_pct=100" >&2
			return 1
			;;
		124|137)
			echo "FAIL: PostgreSQL transaction timed out or was killed" >&2
			return 1
			;;
		1|2|3) ;;
		*)
			printf 'FAIL: PostgreSQL command exited unexpectedly (%s):\n%s\n' "$rc" "$output" >&2
			return 1
			;;
	esac

	# A server PANIC may leave the client with only a disconnect message.
	# The caller supplies only log entries written during fault injection.
	if ! line=$(grep -E -o -m1 '(ERROR|FATAL|PANIC):.*Input/output error.*' <<< "$output
$new_log"); then
		printf 'FAIL: no PostgreSQL storage I/O error was recorded:\n%s\n%s\n' "$output" "$new_log" >&2
		return 1
	fi
	printf '%s\n' "$line"
}
