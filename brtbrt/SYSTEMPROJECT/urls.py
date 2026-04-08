from django.contrib import admin
from django.urls import path
from myapp.views import ProductList  # <-- make sure your app name is correct

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/products/', ProductList.as_view(), name='product-list'),  # endpoint
]