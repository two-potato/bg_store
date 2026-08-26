def test_shopfront_recommendations_compat_import():
    from shopfront import recommendations
    from shopfront.recommendation import heuristics

    assert recommendations is heuristics
