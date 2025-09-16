"""
Script to initialize PrestaShop platform in platforms table
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal
from src.models.platform import Platform


def init_prestashop_platform():
    """Initialize PrestaShop platform entry"""
    
    db = SessionLocal()
    
    try:
        # Check if PrestaShop platform already exists
        existing_platform = db.query(Platform).filter(Platform.id_platform == 1).first()
        
        if existing_platform:
            print(f"PrestaShop platform already exists: {existing_platform.name}")
            print(f"Current URL: {existing_platform.url}")
            print(f"Current API Key: {existing_platform.api_key[:10] + '...' if existing_platform.api_key else 'Not set'}")
            
            # Ask if user wants to update
            update = input("Do you want to update the configuration? (y/n): ").lower().strip()
            if update == 'y':
                new_url = input("Enter PrestaShop API URL (e.g., https://yourstore.com/api): ").strip()
                new_api_key = input("Enter PrestaShop API Key: ").strip()
                
                if new_url:
                    existing_platform.url = new_url
                if new_api_key:
                    existing_platform.api_key = new_api_key
                
                db.commit()
                print("PrestaShop platform updated successfully!")
            else:
                print("No changes made.")
        else:
            # Create new PrestaShop platform
            print("Creating new PrestaShop platform...")
            
            url = input("Enter PrestaShop API URL (e.g., https://yourstore.com/api): ").strip()
            api_key = input("Enter PrestaShop API Key: ").strip()
            
            if not url or not api_key:
                print("Error: Both URL and API Key are required!")
                return
            
            platform = Platform(
                id_platform=1,
                name="PrestaShop",
                url=url,
                api_key=api_key
            )
            
            db.add(platform)
            db.commit()
            print("PrestaShop platform created successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error initializing PrestaShop platform: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_prestashop_platform()
