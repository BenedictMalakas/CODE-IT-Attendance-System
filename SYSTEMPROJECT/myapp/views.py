from rest_framework.views import APIView
from rest_framework.response import Response

class ProductList(APIView):
    def get(self, request):
        products = [
            {"id": 1, "name": "Shoes"},
            {"id": 2, "name": "Hat"}
        ]
        return Response(products)