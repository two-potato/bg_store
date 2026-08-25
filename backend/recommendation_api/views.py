from __future__ import annotations

from shopfront.api.views_recommendations import RecommendationCartAPIView as LegacyRecommendationCartAPIView
from shopfront.api.views_recommendations import RecommendationCheckoutAPIView as LegacyRecommendationCheckoutAPIView
from shopfront.api.views_recommendations import RecommendationHomeAPIView as LegacyRecommendationHomeAPIView
from shopfront.api.views_recommendations import RecommendationProductAPIView as LegacyRecommendationProductAPIView
from shopfront.api.views_recommendations import (
    RecommendationProductSectionAPIView as LegacyRecommendationProductSectionAPIView,
)
from shopfront.api.views_recommendations import RecommendationReorderAPIView as LegacyRecommendationReorderAPIView
from shopfront.api.views_recommendations import (
    RecommendationSearchRecoveryAPIView as LegacyRecommendationSearchRecoveryAPIView,
)


class RecommendationHomeAPIView(LegacyRecommendationHomeAPIView):
    pass


class RecommendationProductAPIView(LegacyRecommendationProductAPIView):
    pass


class RecommendationProductSectionAPIView(LegacyRecommendationProductSectionAPIView):
    pass


class RecommendationCartAPIView(LegacyRecommendationCartAPIView):
    pass


class RecommendationCheckoutAPIView(LegacyRecommendationCheckoutAPIView):
    pass


class RecommendationReorderAPIView(LegacyRecommendationReorderAPIView):
    pass


class RecommendationSearchRecoveryAPIView(LegacyRecommendationSearchRecoveryAPIView):
    pass
