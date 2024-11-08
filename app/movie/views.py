from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)

from rest_framework import viewsets
from rest_framework import mixins
from rest_framework import status

from rest_framework.decorators import action
from rest_framework.response import Response

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import render

from core.models import Movie
from core.models import Tag
from core.models import Rating
from core.models import Genre
from movie import serializers


all_movies = [
  {
    "movie_id": 1,
    "movie_title": "The Empire Strikes Back1",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL":
    "https://nisum.udemy.com/",
    "image":
    "https://filmfare.wwmindia.com/content/2019/nov/tanhaji21573992197.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
  {
    "movie_id": 2,
    "movie_title": "The Empire Strikes Back2",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL":
    "https://nisum.udemy.com/",
    "image":
    "https://filmfare.wwmindia.com/content/2019/nov/tanhaji21573992197.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
  {
    "movie_id": 3,
    "movie_title": "string3",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL":
    "https://nisum.udemy.com/",
    "image": "https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
  {
    "movie_id": 4,
    "movie_title": "string4",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL":
    "https://nisum.udemy.com/",
    "image": "https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
  {
    "movie_id": 5,
    "movie_title": "string4",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL":
    "https://nisum.udemy.com/",
    "image": "https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
  {
    "movie_id": 6,
    "movie_title": "string4",
    "release_date": "2024-11-07",
    "video_release_date": "2024-11-07",
    "IMDb_URL": "https://nisum.udemy.com",
    "image": "https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg",
    "genres": [],
    "tags": [],
    "avg_rating":4
  },
]


def home(request):
    return render(request, 'home.html', {
        "movies": all_movies
    })


def movie_detail(request, movie_id):
    identified_movie = next(movie for movie in all_movies
                            if movie['movie_id'] == movie_id)
    return render(request, 'movie_detail.html', {
        "movie": identified_movie
    })


def welcome(request):
    return render(request, 'welcome.html')


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'tags',
                OpenApiTypes.STR,
                description='Comma separated list of tag IDs to filter',
            ),
        ]
    )
)
class MovieViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.MovieDetailSerializer
    queryset = Movie.objects.all()

    def _params_to_ints(self, qs):
        return [int(str_id) for str_id in qs.split(',')]

    def get_queryset(self):
        tags = self.request.query_params.get('tags')
        queryset = self.queryset
        if tags:
            tag_ids = self._params_to_ints(tags)
            queryset = queryset.filter(tags__tag_id__in=tag_ids)
        return queryset.order_by('-movie_id').distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.MovieSerializer
        elif self.action == 'upload_image':
            return serializers.MovieImageSerializer
        return self.serializer_class

    @action(methods=['POST'], detail=True, url_path='upload-image')
    def upload_image(self, request, pk=None):
        movie = self.get_object()
        serializer = self.get_serializer(movie, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                'assigned_only',
                OpenApiTypes.INT, enum=[0, 1],
            ),
        ]
    )
)
class TagViewSet(mixins.DestroyModelMixin,
                 mixins.UpdateModelMixin,
                 mixins.ListModelMixin,
                 viewsets.GenericViewSet):
    serializer_class = serializers.TagSerializer
    queryset = Tag.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        assigned_only = bool(
            int(self.request.query_params.get('assigned_only', 0))
        )
        queryset = self.queryset
        if assigned_only:
            queryset = queryset.filter(movie__isnull=False)

        return queryset.filter(
            user=self.request.user
        ).order_by('-tag_name').distinct()


class RatingViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.RatingSerializer
    queryset = Rating.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user)


class GenreViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.GenreSerializer
    queryset = Genre.objects.all()
