from django.db.models import Avg
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .models import (
    Booking,
    Car,
    CustomUser,
    GalleryEvent,
    Profile,
    Review,
    SupportRequest,
)
from .serializers import (
    BookingCreateSerializer,
    BookingDetailSerializer,
    BookingSerializer,
    BookingUpdateStatusSerializer,
    CarAvailabilitySerializer,
    CarCreateUpdateSerializer,
    CarDetailSerializer,
    CarSerializer,
    GalleryEventSerializer,
    MpesaWebhookSerializer,
    ProfileDetailSerializer,
    ProfileSerializer,
    ReviewCreateSerializer,
    ReviewSerializer,
    SupportRequestSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
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
# AUTHENTICATION VIEWSET
# ============================================================================

class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints"""
    permission_classes = [permissions.AllowAny]
    
    @extend_schema(
        request=UserRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                description="User registered successfully",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "user": {
                                "id": 1,
                                "email": "john@example.com",
                                "first_name": "John",
                                "second_name": "Doe"
                            },
                            "token": "abc123def456xyz789...",
                            "message": "User registered successfully"
                        }
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Validation error",
                examples=[
                    OpenApiExample(
                        "Error Response",
                        value={
                            "email": ["Email already registered"],
                            "password": ["Passwords do not match"]
                        }
                    )
                ]
            )
        },
        tags=["Authentication"],
        summary="Register a new user",
        description="Create a new user account. Requires first_name, second_name, email, password, and password_confirm.",
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """
        Register a new user
        
        Expected payload:
        {
            "first_name": "John",
            "second_name": "Doe",
            "email": "john@example.com",
            "password": "secure_password",
            "password_confirm": "secure_password"
        }
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'second_name': user.second_name,
                },
                'token': token.key,
                'message': 'User registered successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(
                description="Login successful",
                examples=[
                    OpenApiExample(
                        "Success Response",
                        value={
                            "user": {
                                "id": 1,
                                "email": "john@example.com",
                                "first_name": "John",
                                "second_name": "Doe",
                                "profile": {
                                    "id": "uuid...",
                                    "role": "customer",
                                    "full_name": None
                                }
                            },
                            "token": "abc123def456xyz789...",
                            "message": "Login successful"
                        }
                    )
                ]
            ),
            401: OpenApiResponse(
                description="Authentication failed",
                examples=[
                    OpenApiExample(
                        "Error Response",
                        value={
                            "error": "Invalid email or password"
                        }
                    )
                ]
            )
        },
        tags=["Authentication"],
        summary="Login user",
        description="Authenticate a user with email and password. Returns authentication token.",
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """
        User login
        
        Expected payload:
        {
            "email": "shadrackandare@gmail.com",
            "password": "admin1234"
        }
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user.check_password(password):
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user.is_active:
                return Response(
                    {'error': 'User account is disabled'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            token, created = Token.objects.get_or_create(user=user)
            profile = user.profile
            
            return Response({
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'second_name': user.second_name,
                    'profile': {
                        'id': str(profile.id),
                        'role': profile.role,
                        'full_name': profile.full_name
                    }
                },
                'token': token.key,
                'message': 'Login successful'
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# PROFILE VIEWSET
# ============================================================================

class ProfileViewSet(viewsets.ModelViewSet):
    """
    Profile management
    
    list: Get all profiles (admin)
    retrieve: Get profile details
    update/partial_update: Update own profile
    """
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role']
    search_fields = ['full_name', 'user__email', 'phone']
    ordering_fields = ['-join_date', 'full_name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProfileDetailSerializer
        return ProfileSerializer
    
    def get_permissions(self):
        if self.action == 'list':
            permission_classes = [IsAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_object(self):
        """Return current user's profile if no pk provided"""
        if self.kwargs.get('pk') == 'me':
            return self.request.user.profile
        return super().get_object()


# ============================================================================
# CAR VIEWSET
# ============================================================================

class CarViewSet(viewsets.ModelViewSet):
    """
    Car management
    
    list: Browse available cars
    retrieve: Get car details with images and reviews
    create/update/destroy: Admin only
    """
    queryset = Car.objects.all()
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['car_type', 'transmission', 'fuel', 'available']
    search_fields = ['name', 'model', 'description']
    ordering_fields = ['price', 'rating', 'year', 'name']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CarDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CarCreateUpdateSerializer
        return CarSerializer
    
    def get_queryset(self):
        """Filter available cars for non-admin users"""
        queryset = Car.objects.all()
        
        if not (self.request.user and self.request.user.is_authenticated and 
                self.request.user.profile.role in ['admin', 'super_admin']):
            queryset = queryset.filter(available=True)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def check_availability(self, request):
        """Check if car is available for date range"""
        serializer = CarAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        car_id = serializer.validated_data['car_id']
        pickup_date = serializer.validated_data['pickup_date']
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
            return_date__gt=pickup_date
        ).exists()
        
        return Response({
            'car_id': car_id,
            'available': not overlapping,
            'pickup_date': pickup_date,
            'return_date': return_date,
            'message': 'Car is available' if not overlapping else 'Car is not available for selected dates'
        })
    
    @action(detail=True, methods=['get'])
    def images(self, request, pk=None):
        """Get all images for a specific car"""
        car = self.get_object()
        images = []
        
        if car.images:
            for image in car.images:
                image_url = image.url if hasattr(image, 'url') else str(image)
                images.append(request.build_absolute_uri(image_url))
        
        return Response({
            'car_id': car.id,
            'car_name': car.name,
            'primary_image': request.build_absolute_uri(car.image.url) if car.image else None,
            'images': images,
            'total_images': len(images)
        })
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured/top-rated cars"""
        cars = Car.objects.filter(available=True).order_by('-rating')[:10]
        serializer = CarSerializer(cars, many=True, context={'request': request})
        return Response(serializer.data)


# ============================================================================
# BOOKING VIEWSET
# ============================================================================

class BookingViewSet(viewsets.ModelViewSet):
    """
    Booking management
    
    list: Get user's bookings
    create: Make a new booking
    retrieve: Get booking details
    update/destroy: Admin/owner only
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'car']
    ordering_fields = ['-created_at', 'pickup_date']
    
    def get_queryset(self):
        """Return user's bookings or all if admin"""
        user = self.request.user
        if user.profile.role in ['admin', 'super_admin']:
            return Booking.objects.all()
        return Booking.objects.filter(profile=user.profile)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action == 'retrieve':
            return BookingDetailSerializer
        elif self.action == 'update_status':
            return BookingUpdateStatusSerializer
        return BookingSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsBookingOwnerOrAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def create(self, request, *args, **kwargs):
        """Create a new booking"""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(BookingSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin])
    def update_status(self, request, pk=None):
        """Update booking status (admin only)"""
        booking = self.get_object()
        serializer = BookingUpdateStatusSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BookingDetailSerializer(booking).data)
    
    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def mpesa_webhook(self, request, pk=None):
        """Handle M-Pesa payment webhook"""
        booking = self.get_object()
        
        if booking.profile.user != request.user and not (
            request.user.is_authenticated and request.user.profile.role in ['admin', 'super_admin']
        ):
            return Response(
                {'error': 'Not authorized'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not booking:
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
# AUTHENTICATION ENDPOINTS
# ============================================================================

@extend_schema(
    request=None,
    responses={
        200: OpenApiResponse(
            description="Logout successful",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={"message": "Logout successful"}
                )
            ]
        )
    },
    tags=["Authentication"],
    summary="Logout user",
    description="Delete user's authentication token and logout.",
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    """
    Logout user - delete token
    """
    try:
        request.user.auth_token.delete()
        return Response(
            {'message': 'Logout successful'},
            status=status.HTTP_200_OK
        )
    except:
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_400_BAD_REQUEST
        )


@extend_schema(
    request=None,
    responses={
        200: OpenApiResponse(
            description="Current user details",
            examples=[
                OpenApiExample(
                    "Success Response",
                    value={
                        "user": {
                            "id": 1,
                            "email": "john@example.com",
                            "first_name": "John",
                            "second_name": "Doe",
                            "is_active": True,
                            "profile": {
                                "id": "uuid...",
                                "role": "customer",
                                "full_name": None,
                                "phone": None,
                                "total_bookings": None
                            }
                        }
                    }
                )
            ]
        )
    },
    tags=["Authentication"],
    summary="Get current user",
    description="Retrieve currently logged-in user details.",
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    """Get currently logged-in user details"""
    user = request.user
    profile = user.profile
    
    return Response({
        'user': {
            'id': user.id,
            'email': user.email,
            'first_name': user.first_name,
            'second_name': user.second_name,
            'is_active': user.is_active,
            'profile': {
                'id': str(profile.id),
                'role': profile.role,
                'full_name': profile.full_name,
                'phone': profile.phone,
                'total_bookings': profile.total_bookings,
            }
        }
    }, status=status.HTTP_200_OK)


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
