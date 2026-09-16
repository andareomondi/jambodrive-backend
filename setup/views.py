from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg
from django.utils import timezone
from datetime import timedelta

from .models import Profile, Car, Booking, Review, GalleryEvent, SupportRequest
from .serializers import (
    ProfileSerializer, ProfileDetailSerializer,
    CarSerializer, CarDetailSerializer, CarAvailabilitySerializer,
    BookingSerializer, BookingDetailSerializer, BookingCreateSerializer,
    BookingUpdateStatusSerializer, MpesaWebhookSerializer,
    ReviewSerializer, ReviewCreateSerializer,
    GalleryEventSerializer,
    SupportRequestSerializer,
    CarSearchSerializer
)


# ============================================================================
# PERMISSIONS
# ============================================================================

class IsProfileOwnerOrAdmin(permissions.BasePermission):
    """Allow access only to profile owner or admin"""
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user or request.user.profile.role in ['admin', 'super_admin']


class IsBookingOwnerOrAdmin(permissions.BasePermission):
    """Allow access only to booking owner or admin"""
    
    def has_object_permission(self, request, view, obj):
        return obj.profile.user == request.user or request.user.profile.role in ['admin', 'super_admin']


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read for all, write for admins only"""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and \
               request.user.profile.role in ['admin', 'super_admin']


class IsAdmin(permissions.BasePermission):
    """Admin only access"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and \
               request.user.profile.role in ['admin', 'super_admin']


# ============================================================================
# PROFILE VIEWSET
# ============================================================================

class ProfileViewSet(viewsets.ModelViewSet):
    """
    Profile management
    
    list: Get all profiles (public)
    retrieve: Get profile details
    update: Update own profile or admin update
    me: Get current user profile
    """
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['full_name', 'user__email']
    ordering_fields = ['join_date', 'total_bookings']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProfileDetailSerializer
        return ProfileSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            permission_classes = [IsProfileOwnerOrAdmin]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user's profile"""
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def bookings(self, request, pk=None):
        """Get user's booking history"""
        profile = self.get_object()
        bookings = profile.bookings.all()
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get user's reviews"""
        profile = self.get_object()
        reviews = profile.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)


# ============================================================================
# CAR VIEWSET
# ============================================================================

class CarViewSet(viewsets.ModelViewSet):
    """
    Car inventory management
    
    list: Browse available cars with filters
    retrieve: Get car details with reviews
    create/update/destroy: Admin only
    search: Advanced search with date range
    availability: Check availability for dates
    """
    queryset = Car.objects.filter(available=True)
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['car_type', 'fuel', 'transmission', 'seats']
    search_fields = ['name', 'model', 'description']
    ordering_fields = ['price', 'rating', 'year']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CarDetailSerializer
        return CarSerializer
    
    @action(detail=False, methods=['post'])
    def search(self, request):
        """Advanced car search"""
        serializer = CarSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cars = self.get_queryset()
        
        # Filter by car type
        if 'car_type' in serializer.validated_data:
            cars = cars.filter(car_type=serializer.validated_data['car_type'])
        
        # Filter by max price
        if 'max_price' in serializer.validated_data:
            cars = cars.filter(price__lte=serializer.validated_data['max_price'])
        
        # Filter by fuel type
        if 'fuel_type' in serializer.validated_data:
            cars = cars.filter(fuel=serializer.validated_data['fuel_type'])
        
        # Filter by seats
        if 'seats' in serializer.validated_data:
            cars = cars.filter(seats__gte=serializer.validated_data['seats'])
        
        # Filter by availability for dates
        if 'pickup_date' in serializer.validated_data:
            pickup = serializer.validated_data['pickup_date']
            return_date = serializer.validated_data['return_date']
            
            # Exclude cars with overlapping bookings
            unavailable_cars = Booking.objects.filter(
                status__in=['confirmed', 'completed'],
                pickup_date__lt=return_date,
                return_date__gt=pickup
            ).values_list('car_id', flat=True)
            
            cars = cars.exclude(id__in=unavailable_cars)
        
        serializer = self.get_serializer(cars, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def availability(self, request):
        """Check car availability for a date range"""
        serializer = CarAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        car_id = serializer.validated_data['car_id']
        pickup = serializer.validated_data['pickup_date']
        return_date = serializer.validated_data['return_date']
        
        try:
            car = Car.objects.get(id=car_id)
        except Car.DoesNotExist:
            return Response(
                {'error': 'Car not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check for overlapping bookings
        overlapping = Booking.objects.filter(
            car=car,
            status__in=['confirmed', 'completed'],
            pickup_date__lt=return_date,
            return_date__gt=pickup
        ).exists()
        
        return Response({
            'car_id': car_id,
            'pickup_date': pickup,
            'return_date': return_date,
            'available': not overlapping,
            'price_per_day': str(car.price),
            'total_days': (return_date - pickup).days,
            'estimated_total': str(car.price * (return_date - pickup).days)
        })


# ============================================================================
# BOOKING VIEWSET
# ============================================================================

class BookingViewSet(viewsets.ModelViewSet):
    """
    Booking management
    
    list: User's bookings (or all for admin)
    create: Create new booking
    retrieve: Get booking details
    update: Update booking (status, notes)
    cancel: Cancel booking
    mpesa_callback: Handle M-Pesa webhook
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'car']
    ordering_fields = ['-created_at', 'pickup_date']
    
    def get_queryset(self):
        user = self.request.user
        if user.profile.role in ['admin', 'super_admin']:
            return Booking.objects.all()
        return user.profile.bookings.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action == 'update_status':
            return BookingUpdateStatusSerializer
        elif self.action == 'mpesa_callback':
            return MpesaWebhookSerializer
        elif self.action == 'retrieve':
            return BookingDetailSerializer
        return BookingSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update_status', 'update', 'partial_update']:
            permission_classes = [IsBookingOwnerOrAdmin]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        elif self.action == 'mpesa_callback':
            permission_classes = [permissions.AllowAny]  # Webhook from M-Pesa
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Create booking with validation"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            BookingDetailSerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['patch'], permission_classes=[IsBookingOwnerOrAdmin])
    def update_status(self, request, pk=None):
        """Update booking status (admin)"""
        booking = self.get_object()
        serializer = BookingUpdateStatusSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BookingDetailSerializer(booking).data)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsBookingOwnerOrAdmin])
    def cancel(self, request, pk=None):
        """Cancel a booking"""
        booking = self.get_object()
        
        if booking.status in ['completed', 'cancelled']:
            return Response(
                {'error': f'Cannot cancel booking with status {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save()
        
        return Response(
            BookingDetailSerializer(booking).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def mpesa_callback(self, request):
        """
        Handle M-Pesa payment webhook
        
        Expected payload:
        {
            "checkout_request_id": "...",
            "facilitator_checkout_id": "...",
            "mpesa_receipt_number": "...",
            "mpesa_phone": "...",
            "paid_amount": 5000,
            "mpesa_transaction_date": "20240101120000"
        }
        """
        try:
            checkout_request_id = request.data.get('checkout_request_id')
            booking = Booking.objects.get(checkout_request_id=checkout_request_id)
        except Booking.DoesNotExist:
            return Response(
                {'error': 'Booking not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MpesaWebhookSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            BookingDetailSerializer(booking).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get user's upcoming bookings"""
        bookings = self.get_queryset().filter(
            pickup_date__gte=timezone.now(),
            status__in=['confirmed', 'pending']
        ).order_by('pickup_date')
        
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get user's booking history"""
        bookings = self.get_queryset().filter(
            status__in=['completed', 'cancelled']
        ).order_by('-created_at')
        
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


# ============================================================================
# REVIEW VIEWSET
# ============================================================================

class ReviewViewSet(viewsets.ModelViewSet):
    """
    Review management
    
    list: Get reviews for a car
    create: Post a review
    destroy: Delete own review (admin)
    """
    queryset = Review.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['car', 'rating']
    ordering_fields = ['-date', 'rating']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReviewCreateSerializer
        return ReviewSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action == 'destroy':
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Create review (one per user per car)"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(ReviewSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


# ============================================================================
# GALLERY VIEWSET
# ============================================================================

class GalleryEventViewSet(viewsets.ModelViewSet):
    """
    Gallery event management
    
    list: Browse gallery
    create/update/destroy: Admin only
    """
    queryset = GalleryEvent.objects.all()
    serializer_class = GalleryEventSerializer
    permission_classes = [IsAdminOrReadOnly]
    ordering_fields = ['-event_date', '-created_at']


# ============================================================================
# SUPPORT VIEWSET
# ============================================================================

class SupportRequestViewSet(viewsets.ModelViewSet):
    """
    Support request management
    
    create: Submit support request
    list: View submissions (admin)
    """
    queryset = SupportRequest.objects.all()
    serializer_class = SupportRequestSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]


# ============================================================================
# HEALTH CHECK & STATS
# ============================================================================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """API health check endpoint"""
    return Response({
        'status': 'ok',
        'timestamp': timezone.now()
    })


@api_view(['GET'])
@permission_classes([IsAdmin])
def api_stats(request):
    """API statistics (admin only)"""
    return Response({
        'total_cars': Car.objects.count(),
        'total_bookings': Booking.objects.count(),
        'confirmed_bookings': Booking.objects.filter(status='confirmed').count(),
        'total_users': Profile.objects.count(),
        'total_reviews': Review.objects.count(),
        'average_car_rating': Car.objects.aggregate(Avg('rating'))['rating__avg']
    })
