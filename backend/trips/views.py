from rest_framework.decorators import api_view
from rest_framework.response import Response

from .errors import TripError
from .serializers import AnalyzeRequestSerializer
from .services.analysis import analyze_trip


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def analyze(request):
    serializer = AnalyzeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": "Invalid input.", "details": serializer.errors}, status=400)
    try:
        result = analyze_trip(serializer.validated_data)
    except TripError as exc:
        return Response({"error": str(exc)}, status=422)
    return Response(result)