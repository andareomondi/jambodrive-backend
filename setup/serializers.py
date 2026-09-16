from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from .models import Profile, Car, Booking, Review, GalleryEvent, SupportRequest


# ============================================================================
# PROFILE SERIALIZERS
# ============================================================================

class ProfileSerializer(serializers.ModelSerializer):
    """User profile serializer"""
    email = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'email', 'full_name', 'role', 'total_bookings',
            'phone', 'profile_image', 'join_date', 'updated_at'
        ]
        read_only_fields = ['id', 'join_date', 'updated_at', 'total_bookings']
    
    def get_email(self, obj):
        """Get email from linked User"""
        return obj.user.email if obj.user else None


class ProfileDetailSerializer(ProfileSerializer):
    """Detailed profile with related bookings"""
    bookings_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    
    class Meta(ProfileSerializer.Meta):
        fields = ProfileSerializer.Meta.fields + ['bookings_count', 'average_rating']
    
    def get_bookings_count(self, obj):
        """Count completed bookings"""
        return obj.bookings.filter(status='completed').count()
    
    def get_average_rating(self, obj):
        """Calculate average rating from user's reviews"""
        reviews = obj.reviews.all()
        if not reviews.exists():
            return None
        return sum(r.rating for r in reviews) / reviews.count()


# ============================================================================
# CAR SERIALIZERS
# ============================================================================

class CarSerializer(serializers.ModelSerializer):
    """Basic car serializer for listings"""
    
    class Meta:
        model = Car
        fields = [
            'id', 'name', 'model', 'year', 'price', 'rating', 'reviews',
            'image', 'images', 'car_type', 'seats', 'transmission',
            'fuel', 'features', 'available' , 'chauffered'
        ]
        read_only_fields = ['id', 'rating', 'reviews']


class CarDetailSerializer(CarSerializer):
    """Detailed car serializer with reviews"""
    car_reviews = serializers.SerializerMethodField()
    price_per_day = serializers.DecimalField(source='price', max_digits=10, decimal_places=2, read_only=True)
    
    class Meta(CarSerializer.Meta):
        fields = CarSerializer.Meta.fields + [
            'fuel_consumption', 'description', 'car_reviews', 'price_per_day'
        ]
    
    def get_car_reviews(self, obj):
        """Get recent reviews for this car"""
        reviews = obj.car_reviews.all()[:5]
        return ReviewSerializer(reviews, many=True).data


class CarAvailabilitySerializer(serializers.Serializer):
    """Check car availability for a date range"""
    car_id = serializers.UUIDField()
    pickup_date = serializers.DateTimeField()
    return_date = serializers.DateTimeField()
    
    def validate(self, data):
        """Validate date range"""
        if data['return_date'] <= data['pickup_date']:
            raise serializers.ValidationError(
                "Return date must be after pickup date"
            )
        if data['pickup_date'] < timezone.now():
            raise serializers.ValidationError(
                "Pickup date cannot be in the past"
            )
        return data


# ============================================================================
# BOOKING SERIALIZERS
# ============================================================================

class BookingSerializer(serializers.ModelSerializer):
    """Basic booking serializer"""
    car_details = CarSerializer(source='car', read_only=True)
    profile_details = ProfileSerializer(source='profile', read_only=True)
    
    class Meta:
        model = Booking
        fields = [
            'id', 'car', 'car_details', 'profile', 'profile_details',
            'pickup_date', 'return_date', 'pickup_location', 'return_location',
            'days', 'total_price', 'paid_amount', 'insurance',
            'additional_features', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'paid_amount', 'days']
    
    def validate(self, data):
        """Validate booking logic"""
        pickup = data['pickup_date']
        return_date = data['return_date']
        
        # Date validation
        if return_date <= pickup:
            raise serializers.ValidationError(
                "Return date must be after pickup date"
            )
        
        if pickup < timezone.now():
            raise serializers.ValidationError(
                "Pickup date cannot be in the past"
            )
        
        # Check for overlapping bookings
        car = data['car']
        overlapping = Booking.objects.filter(
            car=car,
            status__in=['confirmed', 'completed'],
            pickup_date__lt=return_date,
            return_date__gt=pickup
        )
        
        if overlapping.exists():
            raise serializers.ValidationError(
                "Car is not available for the selected dates"
            )
        
        # Calculate days
        delta = return_date - pickup
        data['days'] = delta.days
        
        return data


class BookingDetailSerializer(BookingSerializer):
    """Detailed booking with M-Pesa payment info"""
    
    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + [
            'mpesa_phone', 'checkout_request_id', 'facilitator_checkout_id',
            'mpesa_receipt_number', 'mpesa_transaction_date',
            'additional_fee_status', 'additional_fee_amount', 'additional_fee_reason',
            'payment_failure_reason', 'notes'
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    """Create booking - simplified input"""
    
    class Meta:
        model = Booking
        fields = [
            'car', 'pickup_date', 'return_date', 'pickup_location',
            'return_location', 'insurance', 'additional_features'
        ]
    
    def create(self, validated_data):
        """Create booking and set profile from request user"""
        validated_data['profile'] = self.context['request'].user.profile
        
        # Calculate days and total price
        pickup = validated_data['pickup_date']
        return_date = validated_data['return_date']
        days = (return_date - pickup).days
        validated_data['days'] = days
        
        car = validated_data['car']
        validated_data['total_price'] = car.price * days
        
        validated_data['status'] = 'pending'
        
        return Booking.objects.create(**validated_data)


class BookingUpdateStatusSerializer(serializers.ModelSerializer):
    """Update booking status - admin only"""
    
    class Meta:
        model = Booking
        fields = ['status', 'notes']


class MpesaWebhookSerializer(serializers.ModelSerializer):
    """M-Pesa webhook data handler"""
    
    class Meta:
        model = Booking
        fields = [
            'checkout_request_id', 'facilitator_checkout_id',
            'mpesa_receipt_number', 'mpesa_transaction_date',
            'mpesa_phone', 'paid_amount', 'payment_failure_reason'
        ]
    
    def update(self, instance, validated_data):
        """Update booking with M-Pesa response"""
        instance.mpesa_phone = validated_data.get('mpesa_phone', instance.mpesa_phone)
        instance.mpesa_receipt_number = validated_data.get('mpesa_receipt_number', instance.mpesa_receipt_number)
        instance.mpesa_transaction_date = validated_data.get('mpesa_transaction_date', instance.mpesa_transaction_date)
        instance.paid_amount = validated_data.get('paid_amount', instance.paid_amount)
        
        # If payment successful
        if instance.paid_amount and instance.paid_amount >= instance.total_price:
            instance.status = 'confirmed'
        else:
            instance.payment_failure_reason = validated_data.get('payment_failure_reason')
            instance.status = 'failed'
        
        instance.save()
        return instance


# ============================================================================
# REVIEW SERIALIZERS
# ============================================================================

class ReviewSerializer(serializers.ModelSerializer):
    """Car review serializer"""
    profile_name = serializers.CharField(source='profile.full_name', read_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'car', 'profile', 'profile_name', 'rating', 'title', 'comment', 'date']
        read_only_fields = ['id', 'date']
    
    def validate_rating(self, value):
        """Ensure rating is 1-5"""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Create review - set profile from request user"""
    
    class Meta:
        model = Review
        fields = ['car', 'rating', 'title', 'comment']
    
    def create(self, validated_data):
        """Set profile to current user"""
        validated_data['profile'] = self.context['request'].user.profile
        return Review.objects.create(**validated_data)


# ============================================================================
# GALLERY SERIALIZERS
# ============================================================================

class GalleryEventSerializer(serializers.ModelSerializer):
    """Gallery event serializer"""
    
    class Meta:
        model = GalleryEvent
        fields = ['id', 'title', 'description', 'event_date', 'image_url', 'created_at']
        read_only_fields = ['id', 'created_at']


# ============================================================================
# SUPPORT REQUEST SERIALIZERS
# ============================================================================

class SupportRequestSerializer(serializers.ModelSerializer):
    """Support request serializer"""
    
    class Meta:
        model = SupportRequest
        fields = ['id', 'subject', 'category', 'message', 'created_at']
        read_only_fields = ['id', 'created_at']


# ============================================================================
# SEARCH & FILTER SERIALIZERS
# ============================================================================

class CarSearchSerializer(serializers.Serializer):
    """Search parameters for car listing"""
    pickup_date = serializers.DateTimeField(required=False)
    return_date = serializers.DateTimeField(required=False)
    car_type = serializers.CharField(required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    fuel_type = serializers.CharField(required=False)
    seats = serializers.IntegerField(required=False)
    
    def validate(self, data):
        """Validate search params"""
        if 'pickup_date' in data and 'return_date' in data:
            if data['return_date'] <= data['pickup_date']:
                raise serializers.ValidationError(
                    "Return date must be after pickup date"
                )
        return data
