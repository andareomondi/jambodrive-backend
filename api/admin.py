from django.contrib import admin

from .models import *

# Register your models here.

admin.site.register(Profile)
admin.site.register(CustomUser)
admin.site.register(Car)
admin.site.register(Booking)
admin.site.register(Review)
admin.site.register(GalleryEvent)
admin.site.register(SupportRequest)
