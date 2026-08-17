from app import db
from app.models.user_memory import UserMemory


class MemoryService:

    @staticmethod
    def save(user_id, key, value):
        memory = UserMemory.query.filter_by(
            user_id=user_id,
            key=key
        ).first()

        if memory:
            if memory.value != value:
                memory.value = value
        else:
            memory = UserMemory(
                user_id=user_id,
                key=key,
                value=value
            )
            db.session.add(memory)

        db.session.commit()


    @staticmethod
    def get(user_id, key):
        memory = UserMemory.query.filter_by(
            user_id=user_id,
            key=key
        ).first()

        if memory:
            return memory.value

        return None


    @staticmethod
    def all(user_id):
        return UserMemory.query.filter_by(
            user_id=user_id
        ).all()
