import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Profile(models.Model):
    """User profile linked to Django user"""
    
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin'),
        ('facilitator', 'Facilitator'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    total_bookings = models.IntegerField(default=0)
    phone = models.CharField(max_length=20, null=True, blank=True)
    profile_image = models.URLField(null=True, blank=True)
    join_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'profiles'
        ordering = ['-join_date']
    
    def __str__(self):
        return f"{self.full_name or self.user.email} ({self.role})"


class Car(models.Model):
    """Vehicle inventory"""
    
    CAR_TYPE_CHOICES = [
        ('sedan', 'Sedan'),
        ('suv', 'SUV'),
        ('coupe', 'Coupe'),
        ('hatchback', 'Hatchback'),
        ('truck', 'Truck'),
    ]
    
    TRANSMISSION_CHOICES = [
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
    ]
    
    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('hybrid', 'Hybrid'),
        ('electric', 'Electric'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    year = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    reviews = models.IntegerField(default=0)
    image = models.URLField(null=True, blank=True)  # Primary image
    images = models.JSONField(default=list, blank=True)  # Array of image URLs
    car_type = models.CharField(max_length=20, choices=CAR_TYPE_CHOICES, null=True, blank=True)
    seats = models.IntegerField()
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    fuel = models.CharField(max_length=20, choices=FUEL_CHOICES)
    fuel_consumption = models.CharField(max_length=100, null=True, blank=True)
    features = models.JSONField(default=list, blank=True)  # Array of features
    description = models.TextField(null=True, blank=True)
    available = models.BooleanField(default=True)
    chauffered = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'cars'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} {self.model} ({self.year})"
    
    @property
    def is_available(self):
        """Check if car is available (not booked for today)"""
        return self.available


class Booking(models.Model):
    """Car rental bookings"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='bookings')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='bookings')
    
    # Booking dates and locations
    pickup_date = models.DateTimeField()
    return_date = models.DateTimeField()
    pickup_location = models.CharField(max_length=255)
    return_location = models.CharField(max_length=255)
    days = models.BigIntegerField(null=True, blank=True)
    
    # Pricing
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Add-ons
    insurance = models.BooleanField(default=False)
    additional_features = models.JSONField(default=list, blank=True)
    additional_fee_status = models.CharField(max_length=100, null=True, blank=True)
    additional_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    additional_fee_reason = models.CharField(max_length=255, null=True, blank=True)
    additional_fee_receipt = models.CharField(max_length=255, null=True, blank=True)
    
    # M-Pesa payment details
    mpesa_phone = models.CharField(max_length=20, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    facilitator_checkout_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    mpesa_receipt_number = models.CharField(max_length=100, null=True, blank=True)
    mpesa_transaction_date = models.CharField(max_length=100, null=True, blank=True)
    payment_failure_reason = models.TextField(null=True, blank=True)
    
    # Status and notes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['facilitator_checkout_id']),
        ]
    
    def __str__(self):
        return f"Booking {self.id} - {self.car.name} ({self.status})"
    
    def is_overlapping_with(self, other_booking):
        """Check if booking overlaps with another"""
        return not (self.return_date <= other_booking.pickup_date or 
                    self.pickup_date >= other_booking.return_date)


class Review(models.Model):
    """Car reviews and ratings"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='car_reviews')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255, null=True, blank=True)
    comment = models.TextField(null=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'reviews'
        ordering = ['-date']
        unique_together = [['car', 'profile']]  # One review per user per car
    
    def __str__(self):
        return f"Review: {self.car.name} - {self.rating}/5 by {self.profile.full_name}"


class GalleryEvent(models.Model):
    """Gallery/event photos"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    image_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'gallery_events'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.created_at.year})"


class SupportRequest(models.Model):
    """Customer support tickets"""
    
    id = models.BigAutoField(primary_key=True)
    subject = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'support_requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Support: {self.subject} ({self.category})"
