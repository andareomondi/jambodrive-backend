from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularSwaggerView, SpectacularAPIView
from . import views

# Initialize the DefaultRouter
router = DefaultRouter()

# Register ViewSets - DRF auto-generates CRUD endpoints
router.register(r'profiles', views.ProfileViewSet, basename='profile')
router.register(r'cars', views.CarViewSet, basename='car')
router.register(r'bookings', views.BookingViewSet, basename='booking')
router.register(r'reviews', views.ReviewViewSet, basename='review')
router.register(r'gallery', views.GalleryEventViewSet, basename='gallery-event')
router.register(r'support', views.SupportRequestViewSet, basename='support-request')

# URL patterns
urlpatterns = [
    # API Router endpoints
    path('', include(router.urls)),
    
    # Health check
    path('health/', views.health_check, name='health-check'),
    
    # Admin stats
    path('stats/', views.api_stats, name='api-stats'),
    
    # Swagger/OpenAPI documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API authentication
    path('auth/', include('rest_framework.urls')),
]


# ============================================================================
# ENDPOINT REFERENCE
# ============================================================================
"""
PROFILES:
  GET    /profiles/                    - List all profiles
  POST   /profiles/                    - Create profile (admin)
  GET    /profiles/{id}/               - Get profile details
  PUT    /profiles/{id}/               - Update profile (owner/admin)
  PATCH  /profiles/{id}/               - Partial update
  DELETE /profiles/{id}/               - Delete profile (admin)
  GET    /profiles/me/                 - Get current user profile
  GET    /profiles/{id}/bookings/      - Get user's bookings
  GET    /profiles/{id}/reviews/       - Get user's reviews

CARS:
  GET    /cars/                        - List available cars (with filters)
  POST   /cars/                        - Create car (admin)
  GET    /cars/{id}/                   - Get car details with reviews
  PUT    /cars/{id}/                   - Update car (admin)
  PATCH  /cars/{id}/                   - Partial update (admin)
  DELETE /cars/{id}/                   - Delete car (admin)
  POST   /cars/search/                 - Advanced search with date range
  POST   /cars/availability/           - Check availability for dates

BOOKINGS:
  GET    /bookings/                    - List user's bookings (or all for admin)
  POST   /bookings/                    - Create new booking
  GET    /bookings/{id}/               - Get booking details
  PUT    /bookings/{id}/               - Update booking (admin)
  PATCH  /bookings/{id}/               - Partial update
  DELETE /bookings/{id}/               - Delete booking (admin)
  PATCH  /bookings/{id}/update_status/ - Update booking status (admin)
  PATCH  /bookings/{id}/cancel/        - Cancel booking (user/admin)
  GET    /bookings/upcoming/           - Get upcoming bookings
  GET    /bookings/history/            - Get booking history

REVIEWS:
  GET    /reviews/                     - List reviews (filterable by car, rating)
  POST   /reviews/                     - Create review
  GET    /reviews/{id}/                - Get review details
  DELETE /reviews/{id}/                - Delete review (admin)

GALLERY:
  GET    /gallery/                     - List gallery events
  POST   /gallery/                     - Create event (admin)
  GET    /gallery/{id}/                - Get event details
  PUT    /gallery/{id}/                - Update event (admin)
  DELETE /gallery/{id}/                - Delete event (admin)

SUPPORT:
  GET    /support/                     - List support requests (admin)
  POST   /support/                     - Submit support request

WEBHOOKS:
  POST   /bookings/mpesa_callback/    - M-Pesa payment webhook

DOCUMENTATION:
  GET    /schema/                      - OpenAPI schema
  GET    /docs/                        - Swagger UI documentation
  GET    /health/                      - Health check
  GET    /stats/                       - API stats (admin)
"""
