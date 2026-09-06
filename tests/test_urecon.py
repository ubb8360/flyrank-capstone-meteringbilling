from app.jobs import usage_recon


def test_reconciliation_retries_then_succeeds(monkeypatch):
    attempts = {
        "count": 0
    }

    sleep_calls = []

    def fake_reconcile_usage():
        attempts["count"] += 1

        if attempts["count"] < 3:
            raise RuntimeError("Temporary database failure")

    def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(
        usage_recon,
        "reconcile_usage",
        fake_reconcile_usage,
    )

    monkeypatch.setattr(
        usage_recon.time,
        "sleep",
        fake_sleep,
    )

    usage_recon.run_with_retries()

    assert attempts["count"] == 3

    assert sleep_calls == [
        usage_recon.RETRY_DELAY_SECONDS,
        usage_recon.RETRY_DELAY_SECONDS,
    ]