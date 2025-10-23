#!/usr/bin/env python3
"""
Script per pulizia record di audit e documenti DHL scaduti
"""
import os
import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database import get_session
from src.repository.shipment_request_repository import ShipmentRequestRepository
from src.core.settings import get_cache_settings
from sqlalchemy import select, delete
from src.models.shipment_document import ShipmentDocument
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cleanup_expired_audit_records():
    """Cleanup expired shipment audit records"""
    try:
        session = get_session()
        shipment_repo = ShipmentRequestRepository(session)
        
        deleted_count = shipment_repo.cleanup_expired()
        logger.info(f"Cleaned up {deleted_count} expired audit records")
        
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up audit records: {str(e)}")
        return 0


async def cleanup_expired_documents():
    """Cleanup expired shipment documents from filesystem and database"""
    try:
        session = get_session()
        
        # Find expired documents
        now = datetime.utcnow()
        stmt = select(ShipmentDocument).where(ShipmentDocument.expires_at < now)
        expired_docs = session.execute(stmt).scalars().all()
        
        deleted_files = 0
        freed_bytes = 0
        
        for doc in expired_docs:
            try:
                # Delete file from filesystem
                file_path = Path(doc.file_path)
                if file_path.exists():
                    file_size = file_path.stat().st_size
                    file_path.unlink()
                    deleted_files += 1
                    freed_bytes += file_size
                    logger.info(f"Deleted expired document: {doc.file_path}")
                
                # Delete database record
                session.delete(doc)
                
            except Exception as e:
                logger.error(f"Error deleting document {doc.file_path}: {str(e)}")
                continue
        
        # Commit database changes
        session.commit()
        
        logger.info(f"Cleaned up {deleted_files} expired documents, freed {freed_bytes} bytes")
        return deleted_files, freed_bytes
        
    except Exception as e:
        logger.error(f"Error cleaning up documents: {str(e)}")
        session.rollback()
        return 0, 0


async def cleanup_orphaned_files():
    """Cleanup orphaned files in shipment directories"""
    try:
        settings = get_cache_settings()
        base_path = Path("media/shipments")
        
        if not base_path.exists():
            logger.info("No shipment documents directory found")
            return 0, 0
        
        deleted_files = 0
        freed_bytes = 0
        
        # Walk through all shipment directories
        for year_dir in base_path.iterdir():
            if not year_dir.is_dir():
                continue
                
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                    
                for awb_dir in month_dir.iterdir():
                    if not awb_dir.is_dir():
                        continue
                    
                    # Check if AWB directory is older than 1 year
                    dir_age = datetime.now() - datetime.fromtimestamp(awb_dir.stat().st_mtime)
                    if dir_age > timedelta(days=365):
                        try:
                            # Calculate size before deletion
                            dir_size = sum(f.stat().st_size for f in awb_dir.rglob('*') if f.is_file())
                            
                            # Delete directory and all contents
                            import shutil
                            shutil.rmtree(awb_dir)
                            
                            deleted_files += 1
                            freed_bytes += dir_size
                            logger.info(f"Deleted orphaned AWB directory: {awb_dir}")
                            
                        except Exception as e:
                            logger.error(f"Error deleting orphaned directory {awb_dir}: {str(e)}")
                            continue
        
        logger.info(f"Cleaned up {deleted_files} orphaned directories, freed {freed_bytes} bytes")
        return deleted_files, freed_bytes
        
    except Exception as e:
        logger.error(f"Error cleaning up orphaned files: {str(e)}")
        return 0, 0


async def main():
    """Main cleanup function"""
    logger.info("Starting DHL shipment cleanup process")
    
    try:
        # Cleanup expired audit records
        audit_deleted = await cleanup_expired_audit_records()
        
        # Cleanup expired documents
        docs_deleted, docs_freed = await cleanup_expired_documents()
        
        # Cleanup orphaned files
        orphaned_deleted, orphaned_freed = await cleanup_orphaned_files()
        
        # Summary
        total_deleted = audit_deleted + docs_deleted + orphaned_deleted
        total_freed = docs_freed + orphaned_freed
        
        logger.info(f"Cleanup completed:")
        logger.info(f"  - Audit records deleted: {audit_deleted}")
        logger.info(f"  - Documents deleted: {docs_deleted}")
        logger.info(f"  - Orphaned directories deleted: {orphaned_deleted}")
        logger.info(f"  - Total files/directories deleted: {total_deleted}")
        logger.info(f"  - Total bytes freed: {total_freed:,}")
        
        return {
            "audit_records_deleted": audit_deleted,
            "documents_deleted": docs_deleted,
            "orphaned_directories_deleted": orphaned_deleted,
            "total_deleted": total_deleted,
            "total_bytes_freed": total_freed
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        print(f"Cleanup completed successfully: {result}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        sys.exit(1)
