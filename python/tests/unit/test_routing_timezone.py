from datetime import datetime, timezone

from jarvis_ai.orchestrator.routing import try_extract_set_reminder_args


def test_dentist_appointment_utc() -> None:
    args = try_extract_set_reminder_args("my dentist is on April 12 at 3pm", timezone_name="UTC")
    assert args is not None
    assert "T15:00:00" in args["due_at"]


def test_dentist_appointment_asia_kolkata() -> None:
    args = try_extract_set_reminder_args("my dentist is on April 12 at 3pm", timezone_name="Asia/Kolkata")
    assert args is not None
    assert args["due_at"].endswith("Z")
    assert "T09:30:00" in args["due_at"]


def test_dentist_appointment_dst_new_york_edt() -> None:
    fixed_now = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    args = try_extract_set_reminder_args(
        "my dentist is on July 10 at 3pm",
        timezone_name="America/New_York",
        now=fixed_now,
    )
    assert args is not None
    assert "T19:00:00" in args["due_at"]


def test_dentist_appointment_dst_new_york_est() -> None:
    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    args = try_extract_set_reminder_args(
        "my dentist is on February 10 at 3pm",
        timezone_name="America/New_York",
        now=fixed_now,
    )
    assert args is not None
    assert "T20:00:00" in args["due_at"]
