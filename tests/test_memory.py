from app import create_app, db
from app.models.user_memory import UserMemory


def test_user_memory_exists():
    app = create_app()

    with app.app_context():

        UserMemory.query.filter_by(
            user_id=1,
            key="name"
        ).delete()

        db.session.commit()

        memory = UserMemory(
            user_id=1,
            key="name",
            value="تامر محمد"
        )

        db.session.add(memory)
        db.session.commit()

        result = UserMemory.query.filter_by(
            user_id=1,
            key="name"
        ).first()

        assert result is not None
        assert result.value == "تامر محمد"
