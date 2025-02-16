from django.test import TestCase
from django.contrib.auth import get_user_model
from core import models
from django.utils import timezone
from unittest.mock import patch


def create_user(email='user@gmail.com', password='123456'):
    return get_user_model().objects.create_user(email, password)


class ModelTests(TestCase):
    def test_create_user_with_email_successful(self):
        email = 'test@gmail.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
        )
        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        sample_emails = [
            ['test1@gmail.com', 'test1@gmail.com'],
            ['Test2@gmail.com', 'Test2@gmail.com'],
            ['TEST3@gmail.com', 'TEST3@gmail.com'],
            ['test4@gmail.COM', 'test4@gmail.com'],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, 'sample123')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'test123')

    def test_create_superuser(self):
        user = get_user_model().objects.create_superuser(
            'test@gmail.com',
            'test123',
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_create_movie(self):
        movie = models.Movie.objects.create(
            movie_title='Sample Movie Title',
            release_date=None,
        )
        self.assertEqual(str(movie), movie.movie_title)

    def test_create_tag(self):
        user = create_user()
        tag = models.Tag.objects.create(user=user, tag_name='Tag1')

        self.assertEqual(str(tag), tag.tag_name)

    def test_create_rating(self):
        user = models.User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        movie = models.Movie.objects.create(
            movie_title='Sample Movie Title',
             
            release_date=None,
        )
        rating = models.Rating.objects.create(
            user=user,
            movie=movie,
            rating=5,
            timestamp=timezone.now())
        self.assertEqual(rating.user, user)
        self.assertEqual(rating.movie, movie)
        self.assertEqual(rating.rating, 5)

    @patch('core.models.uuid.uuid4')
    def test_movie_file_name_uuid(self, mock_uuid):
        uuid = 'test-uuid'
        mock_uuid.return_value = uuid
        file_path = models.movie_image_file_path(None, 'example.jpg')

        self.assertEqual(file_path, f'uploads/movie/{uuid}.jpg')
