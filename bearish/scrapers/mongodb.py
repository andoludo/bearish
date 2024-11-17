import os

from pymongo import MongoClient

class MongoDBCLient:
    def __init__(self, collection_name):
        self.client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
        self.db = self.client["bearish"]
        self.collection = self.db[collection_name]

    def create(self, data):
        return self.collection.insert_one(data)

    def create_many(self, data):
        return self.collection.insert_many(data)

    def read(self, query):
        return self.collection.find(query)

    def update(self, query, new_data):
        return self.collection.update_one(query, {"$set": new_data})

    def delete(self, query):
        return self.collection.delete_one(query)