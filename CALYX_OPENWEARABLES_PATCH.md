# Calyx OpenWearables patch

Expose safe WHOOP cycle temporal metadata needed by Calyx.

Custom endpoint: `GET /api/v1/users/{user_id}/providers/whoop/cycles`

Numeric calorie source remains: `GET /api/v1/users/{user_id}/timeseries` with `types=active_energy`.

Upstream dependency: `Whoop247Data.get_cycle_data()`. This patch does not change OAuth, webhooks, or kilojoule-to-kcal normalization.
