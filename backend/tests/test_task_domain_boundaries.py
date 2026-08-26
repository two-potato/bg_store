from config.celery import app


def test_background_tasks_have_domain_owners():
    from core.tasks import notify_contact_feedback
    from legacy_shopfront_state.tasks import refresh_recommendation_popularity
    from orders.tasks import emit_checkout_recommendation_feedback, emit_checkout_search_feedback

    assert notify_contact_feedback.name == "core.tasks.notify_contact_feedback"
    assert emit_checkout_search_feedback.name == "orders.tasks.emit_checkout_search_feedback"
    assert emit_checkout_recommendation_feedback.name == "orders.tasks.emit_checkout_recommendation_feedback"
    assert refresh_recommendation_popularity.name == "legacy_shopfront_state.tasks.refresh_recommendation_popularity"


def test_recommendation_beat_schedule_no_longer_targets_shopfront_tasks():
    recommendation_entries = {
        name: entry
        for name, entry in app.conf.beat_schedule.items()
        if name.startswith("recommendations-")
    }

    assert recommendation_entries
    assert all(
        str(entry["task"]).startswith("legacy_shopfront_state.tasks.")
        for entry in recommendation_entries.values()
    )
