"""
Repository for Platform model
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..models.platform import Platform


class PlatformRepository:
    """
    Repository class for Platform operations
    """

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, page: int = 1, limit: int = 10) -> List[Platform]:
        """
        Get all platforms with pagination

        Args:
            page (int): Page number
            limit (int): Number of records per page

        Returns:
            List[Platform]: List of platforms
        """
        offset = (page - 1) * limit
        return self.db.query(Platform).offset(offset).limit(limit).all()

    def get_count(self) -> int:
        """
        Get total count of platforms

        Returns:
            int: Total count
        """
        return self.db.query(Platform).count()

    def get_by_id(self, platform_id: int) -> Optional[Platform]:
        """
        Get platform by ID

        Args:
            platform_id (int): Platform ID

        Returns:
            Optional[Platform]: Platform if found, None otherwise
        """
        return self.db.query(Platform).filter(Platform.id_platform == platform_id).first()

    def get_by_name(self, name: str) -> Optional[Platform]:
        """
        Get platform by name

        Args:
            name (str): Platform name

        Returns:
            Optional[Platform]: Platform if found, None otherwise
        """
        return self.db.query(Platform).filter(Platform.name == name).first()
    
    def get_default(self) -> Optional[Platform]:
        """
        Get default platform (where is_default = 1)

        Returns:
            Optional[Platform]: Default platform if found, None otherwise
        """
        return self.db.query(Platform).filter(Platform.is_default == True).first()

    def create(self, platform_data: dict) -> Platform:
        """
        Create a new platform

        Args:
            platform_data (dict): Platform data

        Returns:
            Platform: Created platform
        """
        platform = Platform(**platform_data)
        self.db.add(platform)
        self.db.commit()
        self.db.refresh(platform)
        return platform

    def update(self, platform: Platform, platform_data: dict) -> Platform:
        """
        Update an existing platform

        Args:
            platform (Platform): Platform to update
            platform_data (dict): Updated platform data

        Returns:
            Platform: Updated platform
        """
        for key, value in platform_data.items():
            setattr(platform, key, value)
        
        self.db.commit()
        self.db.refresh(platform)
        return platform

    def delete(self, platform: Platform) -> bool:
        """
        Delete a platform

        Args:
            platform (Platform): Platform to delete

        Returns:
            bool: True if deleted successfully
        """
        try:
            self.db.delete(platform)
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def delete_by_id(self, platform_id: int) -> bool:
        """
        Delete platform by ID

        Args:
            platform_id (int): Platform ID

        Returns:
            bool: True if deleted successfully
        """
        platform = self.get_by_id(platform_id)
        if platform:
            return self.delete(platform)
        return False
