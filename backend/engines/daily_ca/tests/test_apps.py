# engines/daily_ca/tests/test_apps.py
#
# The startup backfill (_startup_backfill, _is_running_under_pytest) has been
# removed from apps.py.  Embeddings are generated automatically by the
# post_save signal in engines/daily_ca/signals.py — no startup logic to test.
#
# Signal tests live in test_signals.py.
