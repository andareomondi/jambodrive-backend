# Supabase → Django Schema Mapping

## Overview
This document maps the Supabase database schema to Django ORM models, explaining transformations and differences.

---

## 1. PROFILES TABLE

### Supabase Schema
```sql
CREATE TABLE profiles (
    id UUID PRIMARY KEY,
    updated_at TIMESTAMP,
    full_name TEXT,
    role TEXT DEFAULT 'customer',
    total_bookings INTEGER DEFAULT 0,
    email TEXT UNIQUE,
    phone TEXT,
    profile_image TEXT,
    join_date TIMESTAMP DEFAULT now()
);

-- Foreign key to auth.users
ALTER TABLE profiles ADD CONSTRAINT profiles_id_fkey 
  FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
```

### Django Model
```python
class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE)  # Replaces auth.users FK
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    total_bookings = models.IntegerField(default=0)
    phone = models.CharField(max_length=20)
    profile_image = models.URLField()
    join_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Key Changes
| Supabase | Django | Reason |
|----------|--------|--------|
| `id` UUID FK to `auth.users` | `user` OneToOne to Django `User` | Django's built-in User model replaces Supabase auth |
| `email` (stored in profiles) | `user.email` (from User model) | Avoid duplication; use built-in User field |
| `role` TEXT | `role` CharField with choices | Better type safety |
| Auto-generated UUID | `default=uuid.uuid4` | Manual UUID generation in Django |

### RLS Policies → Django Permissions
Supabase RLS: "Users can update own profile"
→ Django: Use custom permission class `IsProfileOwnerOrAdmin`

---

## 2. CARS TABLE

### Supabase Schema
```sql
CREATE TABLE cars (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    rating NUMERIC DEFAULT 0.0,
    reviews INTEGER DEFAULT 0,
    image TEXT,
    images TEXT[],           -- PostgreSQL array
    type TEXT,
    seats INTEGER NOT NULL,
    transmission transmission_type,
    fuel fuel_type,
    fuel_consumption TEXT,
    features TEXT[],         -- PostgreSQL array
    description TEXT,
    available BOOLEAN DEFAULT true
    chauffered BOOLEAN DEFAULT false
);
```

### Django Model
```python
class Car(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=255)
    model = models.CharField(max_length=255)
    year = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    reviews = models.IntegerField(default=0)
    image = models.URLField()
    images = models.JSONField(default=list)  # PostgreSQL array → JSONField
    car_type = models.CharField(max_length=20, choices=CAR_TYPE_CHOICES)
    seats = models.IntegerField()
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    fuel = models.CharField(max_length=20, choices=FUEL_CHOICES)
    fuel_consumption = models.CharField(max_length=100)
    features = models.JSONField(default=list)  # PostgreSQL array → JSONField
    description = models.TextField()
    available = models.BooleanField(default=True)
    chauffered = models.BooleanField(default=False)
```

### Key Changes
| Supabase | Django | Reason |
|----------|--------|--------|
| `images TEXT[]` (PostgreSQL array) | `images JSONField(default=list)` | JSONField serializes/deserializes automatically |
| `type TEXT` | `car_type CharField` (with choices) | Clearer naming, type safety |
| Enum types | `CharField` + `choices` tuple | Django's standard pattern |
| `features TEXT[]` | `features JSONField(default=list)` | Same as images |

### Queries
```python
# Supabase (TypeScript)
const { data, error } = await supabase
  .from('cars')
  .select('*')
  .eq('available', true)
  .order('price', { ascending: true });

# Django
cars = Car.objects.filter(available=True).order_by('price')
```

---

## 3. BOOKINGS TABLE

### Supabase Schema
```sql
CREATE TABLE bookings (
    id UUID PRIMARY KEY,
    car_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    pickup_date TIMESTAMP NOT NULL,
    return_date TIMESTAMP NOT NULL,
    pickup_location TEXT NOT NULL,
    return_location TEXT NOT NULL,
    total_price NUMERIC NOT NULL,
    status booking_status DEFAULT 'pending',
    insurance BOOLEAN DEFAULT false,
    additional_features TEXT[],
    created_at TIMESTAMP DEFAULT now(),
    days BIGINT,
    
    -- M-Pesa payment fields
    checkout_request_id TEXT UNIQUE,
    mpesa_receipt_number TEXT,
    mpesa_transaction_date TEXT,
    mpesa_phone TEXT,
    paid_amount NUMERIC,
    payment_failure_reason TEXT,
    facilitator_checkout_id TEXT UNIQUE,
    additional_fee_status TEXT,
    additional_fee_receipt TEXT,
    additional_fee_amount NUMERIC,
    additional_fee_reason TEXT,
    notes TEXT,
    
    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE INDEX bookings_checkout_request_id_idx ON bookings(checkout_request_id);
CREATE INDEX bookings_facilitator_checkout_id_idx ON bookings(facilitator_checkout_id);
```

### Django Model
```python
class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='bookings')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='bookings')
    
    pickup_date = models.DateTimeField()
    return_date = models.DateTimeField()
    pickup_location = models.CharField(max_length=255)
    return_location = models.CharField(max_length=255)
    days = models.BigIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    insurance = models.BooleanField(default=False)
    additional_features = models.JSONField(default=list)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # M-Pesa fields
    mpesa_phone = models.CharField(max_length=20, null=True)
    checkout_request_id = models.CharField(max_length=255, null=True, unique=True)
    facilitator_checkout_id = models.CharField(max_length=255, null=True, unique=True)
    mpesa_receipt_number = models.CharField(max_length=100, null=True)
    mpesa_transaction_date = models.CharField(max_length=100, null=True)
    payment_failure_reason = models.TextField(null=True)
    additional_fee_status = models.CharField(max_length=100, null=True)
    additional_fee_receipt = models.CharField(max_length=255, null=True)
    additional_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    additional_fee_reason = models.CharField(max_length=255, null=True)
    
    notes = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['facilitator_checkout_id']),
        ]
```

### Key Changes
| Supabase | Django | Reason |
|----------|--------|--------|
| `car_id`, `profile_id` (UUID FK) | `car`, `profile` (ForeignKey objects) | Django ORM handles relationships |
| Indexes via SQL | `class Meta: indexes = [...]` | Declarative indexing |
| `additional_features TEXT[]` | `JSONField(default=list)` | Better serialization |
| `created_at TIMESTAMP DEFAULT now()` | `DateTimeField(auto_now_add=True)` | Django auto-handles |

### Important: Booking Overlap Logic
```python
# Django: Check if car is available for date range
def is_car_available(car, pickup_date, return_date):
    overlapping = Booking.objects.filter(
        car=car,
        status__in=['confirmed', 'completed'],
        pickup_date__lt=return_date,
        return_date__gt=pickup_date
    )
    return not overlapping.exists()

# Use in serializer validation
def validate(self, data):
    if not is_car_available(data['car'], data['pickup_date'], data['return_date']):
        raise serializers.ValidationError("Car not available for these dates")
    return data
```

---

## 4. REVIEWS TABLE

### Supabase Schema
```sql
CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    car_id UUID,
    profile_id UUID,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    title TEXT,
    comment TEXT,
    date TIMESTAMP DEFAULT now(),
    
    FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);
```

### Django Model
```python
class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='car_reviews')
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=255)
    comment = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['car', 'profile']]  # One review per user per car
```

### Key Changes
| Supabase | Django | Reason |
|----------|--------|--------|
| `CHECK (rating >= 1 AND rating <= 5)` | `validators=[MinValueValidator(1), MaxValueValidator(5)]` | Django validators |
| Constraint via SQL | `unique_together` in Meta | Prevent duplicate reviews |

---

## 5. GALLERY_EVENTS TABLE

### Supabase Schema
```sql
CREATE TABLE gallery_events (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE,
    image_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);
```

### Django Model
```python
class GalleryEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True)
    event_date = models.DateField(null=True)
    image_url = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### No Changes Needed
Direct 1:1 mapping.

---

## 6. SUPPORT_REQUESTS TABLE

### Supabase Schema
```sql
CREATE TABLE support_requests (
    id BIGINT PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    subject TEXT,
    category TEXT,
    message TEXT
);
```

### Django Model
```python
class SupportRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    subject = models.CharField(max_length=255, null=True)
    category = models.CharField(max_length=100, null=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
```

### Key Changes
| Supabase | Django | Reason |
|----------|--------|--------|
| `GENERATED BY DEFAULT AS IDENTITY` | `BigAutoField` | Django's auto-increment |

---

## 7. ENUM TYPES

### Supabase
```sql
CREATE TYPE booking_status AS ENUM ('confirmed', 'pending', 'completed', 'cancelled', 'failed');
CREATE TYPE car_type AS ENUM ('sedan', 'suv', 'coupe', 'hatchback', 'truck');
CREATE TYPE fuel_type AS ENUM ('petrol', 'diesel', 'hybrid', 'electric');
CREATE TYPE transmission_type AS ENUM ('manual', 'automatic');
```

### Django
```python
# In models.py
STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('confirmed', 'Confirmed'),
    ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
    ('failed', 'Failed'),
]

CAR_TYPE_CHOICES = [
    ('sedan', 'Sedan'),
    ('suv', 'SUV'),
    # ... etc
]

# In model field
status = models.CharField(max_length=20, choices=STATUS_CHOICES)
```

---

## 8. DATA MIGRATION

### Steps
1. **Export Supabase data:**
   ```bash
   # Use pg_dump to export data only (not schema)
   pg_dump --data-only postgresql://... > supabase_data.sql
   ```

2. **Transform UUIDs (if needed):**
   - Supabase: UUIDs are text in JSON
   - Django: UUIDs are native type
   - Usually works automatically, but test with sample data

3. **Load into Django PostgreSQL:**
   ```bash
   psql -U postgres -d cosmara < supabase_data.sql
   ```

4. **Verify data:**
   ```python
   python manage.py shell
   >>> from api.models import Car, Booking, Profile
   >>> Car.objects.count()  # Should match Supabase
   >>> Booking.objects.count()
   ```

---

## 9. PERMISSIONS/RLS REPLACEMENT

### Supabase RLS Policies
```sql
CREATE POLICY "Users can read their own bookings" ON bookings 
  FOR SELECT TO authenticated 
  USING (profile_id = auth.uid());

CREATE POLICY "Admins can update bookings" ON bookings 
  FOR UPDATE TO authenticated 
  USING (EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'super_admin'));
```

### Django Equivalent
```python
# In views.py
class BookingViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        if user.profile.role in ['admin', 'super_admin']:
            return Booking.objects.all()
        return user.profile.bookings.all()
    
    def get_permissions(self):
        if self.action == 'update':
            return [IsBookingOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]
```

---

## 10. PERFORMANCE CONSIDERATIONS

### Indexes
Django automatically creates indexes on:
- Primary keys (`id`)
- Foreign keys (`car`, `profile`)
- Fields with `unique=True` or `unique_together`

Add custom indexes for frequently queried fields:
```python
class Meta:
    indexes = [
        models.Index(fields=['checkout_request_id']),
        models.Index(fields=['status', 'pickup_date']),  # Common filter
    ]
```

### Query Optimization
```python
# Bad: N+1 queries
bookings = Booking.objects.all()
for booking in bookings:
    print(booking.car.name)  # Hits DB for each car

# Good: select_related
bookings = Booking.objects.select_related('car', 'profile')
for booking in bookings:
    print(booking.car.name)  # No extra queries
```

---

## Summary Table

| Concept | Supabase | Django |
|---------|----------|--------|
| **Auth Users** | `auth.users` table | Built-in `User` model |
| **User Profiles** | `profiles` with FK to auth | `OneToOne` to User |
| **Enums** | PostgreSQL ENUM types | CharField + choices |
| **Arrays** | PostgreSQL TEXT[] | JSONField |
| **RLS/Permissions** | Row-level security policies | Permission classes |
| **Auto-increment** | `GENERATED AS IDENTITY` | `AutoField`/`BigAutoField` |
| **UUIDs** | UUID type | `UUIDField` |
| **Realtime** | Supabase Realtime | WebSockets (Django Channels) |
| **Timestamps** | `DEFAULT now()` | `auto_now_add=True` |
| **Relationships** | Foreign keys (SQL) | ForeignKey (ORM) |

---

## Testing Data Migration

```python
# test_migration.py
from django.test import TestCase
from api.models import Car, Booking, Profile

class MigrationTestCase(TestCase):
    def test_data_integrity(self):
        # After loading Supabase data
        self.assertGreater(Car.objects.count(), 0)
        self.assertGreater(Booking.objects.count(), 0)
        
        # Check relationships
        booking = Booking.objects.first()
        self.assertIsNotNone(booking.car)
        self.assertIsNotNone(booking.profile)
        
        # Check enum values
        self.assertIn(booking.status, dict(Booking.STATUS_CHOICES))
```

---

This mapping document should help you understand how Supabase concepts translate to Django. Keep it handy during development!
