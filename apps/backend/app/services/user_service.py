from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate


class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()
    
    def get_by_id(self, user_id: str) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def create(self, user_data: UserCreate) -> User:
        db_user = User(
            telegram_id=user_data.telegram_id,
            name=user_data.name
        )
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
    
    def get_or_create(self, telegram_id: int, name: Optional[str] = None) -> User:
        user = self.get_by_telegram_id(telegram_id)
        if not user:
            user_create = UserCreate(telegram_id=telegram_id, name=name)
            user = self.create(user_create)
        return user

    def get_by_whatsapp_phone(self, phone: str) -> Optional[User]:
        return self.db.query(User).filter(User.whatsapp_phone == phone).first()

    def get_or_create_whatsapp(self, phone: str, name: Optional[str] = None) -> User:
        user = self.get_by_whatsapp_phone(phone)
        if not user:
            user = User(whatsapp_phone=phone, name=name)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        elif name and not user.name:
            user.name = name
            self.db.commit()
        return user
