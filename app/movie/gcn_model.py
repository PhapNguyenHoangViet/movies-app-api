import torch
from torch.nn import functional as F
import torch.optim as optim
from torch_geometric.nn import GCNConv
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from sklearn.preprocessing import LabelEncoder
from django.db import connection
import pandas as pd
import numpy as np
import os
from core.models import User
from django.db.models import Max
from core.models import User

num_user_id = User.objects.aggregate(Max('user_id'))['user_id__max']

class GCN(torch.nn.Module):
    def __init__(self, num_features, hidden_channels):
        super(GCN, self).__init__()
        # Thêm nhiều lớp convolution
        self.conv1 = GCNConv(num_features, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels // 2)
        self.conv3 = GCNConv(hidden_channels // 2, hidden_channels)
        self.dropout = torch.nn.Dropout(0.5)
    
    def forward(self, x, edge_index, edge_attr):
        x = F.relu((self.conv1(x, edge_index, edge_weight=edge_attr)))
        x = self.dropout(x)
        x = F.relu((self.conv2(x, edge_index, edge_weight=edge_attr)))
        x = self.dropout(x)
        x = self.conv3(x, edge_index, edge_weight=edge_attr)
        return x


class MovieRecommender:
    def __init__(self, model_path=None):
        checkpoint = torch.load(model_path)
        self.num_features = checkpoint['conv1.lin.weight'].shape[1]
        self.hidden_channels = checkpoint['conv1.lin.weight'].shape[0]
        
        self.model = self._create_gcn_model()
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def _create_gcn_model(self):
        return GCN(
            num_features=self.num_features, 
            hidden_channels=self.hidden_channels
        )
    
    def load_model(self, model_path):
        try:
            self.model.load_state_dict(torch.load(model_path))
            self.model.eval()
            print(f"Loaded model from {model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
    
    def save_model(self, model_path):
        try:
            torch.save(self.model.state_dict(), model_path)
            print(f"Model saved to {model_path}")
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def update_model(self, 
                     ratings_data, 
                     feature_matrix, 
                     model_path,
                     epochs=50, 
                     learning_rate=0.0005, 
                     weight_decay=1e-5):
        try:
            train_data = self._create_interaction_graph(ratings_data, feature_matrix)
            train_loader = DataLoader([train_data], batch_size=1)
            
            optimizer = optim.AdamW(
                self.model.parameters(), 
                lr=learning_rate, 
                weight_decay=weight_decay
            )
            criterion = torch.nn.MSELoss()
            
            self.model.train()
            for epoch in range(epochs):
                total_loss = 0
                for data in train_loader:
                    optimizer.zero_grad()
                    out = self.model(data.x, data.edge_index, data.edge_attr)
                    edge_scores = (out[data.edge_index[0]] * out[data.edge_index[1]]).sum(dim=1)
                    loss = torch.sqrt(criterion(edge_scores, data.edge_attr.to(torch.float)))
                    loss.backward()
                    optimizer.step()
                    total_loss += loss.item()
                
                train_loss = total_loss / len(train_loader)
                if (epoch + 1) % 2 == 0:
                    print(f'Epoch {epoch + 1}, Train Loss: {train_loss:.4f}')
            
            self.model.eval()
            self.save_model(model_path)
            return train_loss
         
        except Exception as e:
            print(f"Model update error: {e}")
            return None
        
    def update_with_new_ratings(self, new_ratings, feature_matrix, model_path, epochs=5):
        if new_ratings.empty:
            print("No new ratings to update.")
            return

        train_data = self._create_interaction_graph(new_ratings, feature_matrix)
        train_loader = DataLoader([train_data], batch_size=1)
        optimizer = optim.AdamW(self.model.parameters(), lr=0.0005, weight_decay=1e-5)
        criterion = torch.nn.MSELoss()

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for data in train_loader:
                optimizer.zero_grad()
                out = self.model(data.x, data.edge_index, data.edge_attr)
                edge_scores = (out[data.edge_index[0]] * out[data.edge_index[1]]).sum(dim=1)
                loss = torch.sqrt(criterion(edge_scores, data.edge_attr.to(torch.float)))
                loss.backward()
                optimizer.step()
                total_loss += loss.item()

            train_loss = total_loss / len(train_loader)
            print(f"Epoch {epoch + 1}, Train Loss: {train_loss:.4f}")

        self.model.eval()
        self.save_model(model_path)

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE core_rating 
                SET processed = TRUE
                WHERE rating_id IN (%s)
            """ % ', '.join(map(str, new_ratings['rating_id'].tolist())))
        print("Updated ratings processed status.")
    
    def auto_update_model(self, model_path):
        try:
            new_ratings = self.get_new_ratings(batch_size=5)
            
            if len(new_ratings) >= 5:
                print(f"Found {len(new_ratings)} new ratings. Updating model...")
                _, _, _, feature_matrix = self.prepare()

                self.update_with_new_ratings(
                    new_ratings=new_ratings,
                    feature_matrix=feature_matrix,
                    model_path=model_path,
                    epochs=50
                )
                
                print("Model updated successfully!")
                return True
            else:
                print(f"Only {len(new_ratings)} new ratings found. Waiting for more ratings...")
                return False
                
        except Exception as e:
            print(f"Error in auto update: {e}")
            return False
        
    def get_recommendations(self, user_id, top_k=10):
        try:
            users, items, ratings, feature_matrix = self.prepare()
            train_data = self._create_interaction_graph(ratings, feature_matrix)
            self.model.eval()
            
            with torch.no_grad():
                rated_movies = set(ratings[ratings['user_id'] == user_id]['movie_id'].values)
                out = self.model(train_data.x, train_data.edge_index, train_data.edge_attr)
                user_embedding = out[user_id]
                num_users = len(users)
                num_items = len(items)
                item_embeddings = out[num_users:num_users + num_items]
                
                scores = torch.matmul(user_embedding.unsqueeze(0), item_embeddings.t()).squeeze()
                scores = scores.cpu().numpy()
                
                movie_scores = [(i + 1, float(score)) for i, score in enumerate(scores)]  # Cộng 1 vào movie_id
                unrated_movies = [(i, score) for i, score in movie_scores if (i-1) not in rated_movies]
                
                recommendations = sorted(unrated_movies, key=lambda x: x[1], reverse=True)[:top_k]
                
                return recommendations
                
        except Exception as e:
            print(f"Error getting recommendations: {e}")
            return []


    def _create_interaction_graph(self, ratings, features):
        user_ids = ratings['user_id'].values
        item_ids = ratings['movie_id'].values + num_user_id
        ratings_values = ratings['rating'].values
                
        edge_index = torch.tensor([
            np.concatenate([user_ids, item_ids]),
            np.concatenate([item_ids, user_ids])
        ], dtype=torch.long)
        
        edge_attr = torch.tensor(
            np.concatenate([ratings_values, ratings_values]), 
            dtype=torch.float
        )
        
        graph_data = Data(
            x=features, 
            edge_index=edge_index, 
            edge_attr=edge_attr
        )
        
        return graph_data

    def fetch_data_as_dataframe(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)
        
    def get_new_ratings(self, batch_size=5):
        query = f"""
            SELECT * 
            FROM core_rating 
            WHERE processed = FALSE
            ORDER BY timestamp ASC
            LIMIT {batch_size}
        """
        return self.fetch_data_as_dataframe(query)

    def prepare(self):
        query_movies = "SELECT movie_id, movie_title, release_date, overview, runtime, keywords, director,caster FROM core_movie ORDER BY movie_id ASC"
        query_ratings = "SELECT user_id, movie_id, rating, timestamp FROM core_rating"
        query_users = "SELECT user_id, age, sex, occupation FROM core_user"
        query_movie_genres = """
            SELECT m.movie_id, string_agg(g.genre_name, ', ') AS genres
            FROM core_movie_genres mg
            JOIN core_movie m ON m.movie_id = mg.movie_id
            JOIN core_genre g ON g.genre_id = mg.genre_id
            GROUP BY m.movie_id
        """
        items = self.fetch_data_as_dataframe(query_movies)
        ratings = self.fetch_data_as_dataframe(query_ratings)
        users = self.fetch_data_as_dataframe(query_users)
        movie_genres = self.fetch_data_as_dataframe(query_movie_genres)
        items = items.merge(movie_genres, on="movie_id", how="left")
        
        users['user_id']=users['user_id']-1
        items['movie_id']=items['movie_id']-1
        ratings['user_id']=ratings['user_id']-1
        ratings['movie_id']=ratings['movie_id']-1
        genre_list = [
            'unknown', 'Action', 'Adventure', 'Animation', "Children's", 'Comedy', 'Crime', 'Documentary', 
            'Drama', 'Fantasy', 'Film-Noir', 'Horror', 'Musical', 'Mystery', 'Romance', 'Sci-Fi', 
            'Thriller', 'War', 'Western'
        ]
        def genres_to_one_hot(genres, genre_list):
            genre_flags = {genre: 0 for genre in genre_list}
            if pd.notna(genres):
                for genre in genres.split(', '):
                    if genre in genre_flags:
                        genre_flags[genre] = 1
            return genre_flags
        genre_one_hot = items['genres'].apply(lambda x: pd.Series(genres_to_one_hot(x, genre_list)))
        items = pd.concat([items.drop(columns=['genres']), genre_one_hot], axis=1)
        
        ratings['timestamp'] = pd.to_datetime(ratings['timestamp'], unit='s')
        ratings['day_of_week'] = ratings['timestamp'].dt.dayofweek
        ratings['hour'] = ratings['timestamp'].dt.hour
        ratings['time_of_day'] = pd.cut(ratings['hour'],
                                        bins=[0, 6, 12, 18, 24],
                                        labels=[0, 1, 2, 3],
                                        include_lowest=True)

        
        users['sex'] = LabelEncoder().fit_transform(users['sex'])
        users['occupation'] = LabelEncoder().fit_transform(users['occupation'])
        bins = [0, 18, 30, 45, 60, 100]
        labels = list(range(len(bins)-1))
        users['age'] = pd.cut(users['age'], bins=bins, labels=labels, right=False)
        user_features = pd.get_dummies(users, columns=['age', 'sex', 'occupation'])
        user_features = user_features.drop(['user_id'], axis=1).astype(float)
        user_features = torch.tensor(user_features.values, dtype=torch.float)

        item_features = items.to_numpy()
        item_features = item_features[:, -19:]
        item_features = item_features.astype(float)
        item_features = torch.tensor(item_features, dtype=torch.float)


        feature_matrix = torch.cat([
            torch.cat([user_features, torch.zeros(len(user_features), item_features.shape[1])], dim=1),
            torch.cat([torch.zeros(len(item_features), user_features.shape[1]), item_features], dim=1)
        ])

        return users, items, ratings, feature_matrix
