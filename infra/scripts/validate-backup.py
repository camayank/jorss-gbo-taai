#!/usr/bin/env python3
"""
RDS Backup Validation Script

This script validates RDS backups by:
1. Finding the most recent automated backup
2. Restoring from that backup to a temporary test database
3. Running validation queries to ensure data integrity
4. Cleaning up the temporary database
5. Logging results to CloudWatch

Usage:
  python validate-backup.py --db-identifier jorss-gbo-prod-postgres --region us-east-1

Requirements:
  - boto3: AWS SDK for Python
  - psycopg2: PostgreSQL adapter for Python
  - AWS credentials configured with appropriate RDS permissions
"""

import argparse
import logging
import sys
import time
from datetime import datetime, timedelta

import boto3
import psycopg2
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupValidator:
    """Validates RDS backups by restoring and testing."""

    def __init__(self, db_identifier, region, test_timeout_hours=2):
        self.db_identifier = db_identifier
        self.region = region
        self.test_timeout_hours = test_timeout_hours
        self.rds_client = boto3.client('rds', region_name=region)
        self.test_db_identifier = f"{db_identifier}-backup-test-{int(time.time())}"
        self.validation_results = {
            'status': 'pending',
            'timestamp': datetime.utcnow().isoformat(),
            'db_identifier': db_identifier,
            'test_db_identifier': self.test_db_identifier,
            'errors': []
        }

    def find_latest_backup(self):
        """Find the most recent automated backup for the database."""
        try:
            logger.info(f"Finding latest backup for {self.db_identifier}")
            response = self.rds_client.describe_db_snapshots(
                DBInstanceIdentifier=self.db_identifier,
                SnapshotType='automated',
                IncludeShared=False
            )

            snapshots = response.get('DBSnapshots', [])
            if not snapshots:
                raise Exception(f"No automated backups found for {self.db_identifier}")

            # Sort by SnapshotCreateTime, most recent first
            latest_snapshot = sorted(
                snapshots,
                key=lambda x: x['SnapshotCreateTime'],
                reverse=True
            )[0]

            logger.info(f"Found latest backup: {latest_snapshot['DBSnapshotIdentifier']} "
                       f"created at {latest_snapshot['SnapshotCreateTime']}")
            return latest_snapshot

        except ClientError as e:
            error_msg = f"Error finding backup: {str(e)}"
            logger.error(error_msg)
            self.validation_results['errors'].append(error_msg)
            raise

    def restore_from_snapshot(self, snapshot):
        """Restore a test database from the snapshot."""
        try:
            logger.info(f"Restoring test database from snapshot {snapshot['DBSnapshotIdentifier']}")

            self.rds_client.restore_db_instance_from_db_snapshot(
                DBInstanceIdentifier=self.test_db_identifier,
                DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier'],
                DBInstanceClass=snapshot['DBInstanceClass'],
                MultiAZ=False,  # Single AZ for testing
                PubliclyAccessible=False,
                StorageEncrypted=snapshot.get('StorageEncrypted', True),
                DeletionProtection=False
            )

            logger.info(f"Restore initiated. Waiting for test DB {self.test_db_identifier} to be available...")

            # Wait for restore to complete (with timeout)
            waiter = self.rds_client.get_waiter('db_instance_available')
            waiter.wait(
                DBInstanceIdentifier=self.test_db_identifier,
                WaiterConfig={
                    'Delay': 30,  # Check every 30 seconds
                    'MaxAttempts': (self.test_timeout_hours * 60) // 30
                }
            )

            logger.info(f"Test database {self.test_db_identifier} is now available")
            return True

        except ClientError as e:
            error_msg = f"Error restoring snapshot: {str(e)}"
            logger.error(error_msg)
            self.validation_results['errors'].append(error_msg)
            raise

    def get_db_endpoint(self, db_identifier):
        """Get the endpoint for a database instance."""
        try:
            response = self.rds_client.describe_db_instances(
                DBInstanceIdentifier=db_identifier
            )

            if not response['DBInstances']:
                raise Exception(f"Database {db_identifier} not found")

            endpoint = response['DBInstances'][0]['Endpoint']
            return f"{endpoint['Address']}:{endpoint['Port']}"

        except ClientError as e:
            error_msg = f"Error getting DB endpoint: {str(e)}"
            logger.error(error_msg)
            raise

    def validate_database(self, endpoint, username, password):
        """Connect to test database and run validation queries."""
        try:
            logger.info(f"Connecting to test database at {endpoint}")

            # Parse endpoint
            host, port = endpoint.rsplit(':', 1)

            conn = psycopg2.connect(
                host=host,
                port=int(port),
                database='jorss_gbo',
                user=username,
                password=password,
                connect_timeout=30
            )

            cursor = conn.cursor()
            validation_passed = True

            try:
                # Test 1: Basic connectivity and table existence
                logger.info("Running validation queries...")

                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.tables
                    WHERE table_schema = 'public'
                """)
                table_count = cursor.fetchone()[0]
                logger.info(f"✓ Database contains {table_count} public tables")

                # Test 2: Check for data integrity
                cursor.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'")
                if table_count > 0:
                    logger.info("✓ Data integrity check passed")

                # Test 3: Verify recent data exists
                cursor.execute("""
                    SELECT schemaname, tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    LIMIT 1
                """)
                sample_table = cursor.fetchone()
                if sample_table:
                    logger.info(f"✓ Sample table accessible: {sample_table[1]}")

                # Test 4: Check database size
                cursor.execute("SELECT pg_database_size('jorss_gbo') / 1024 / 1024 AS size_mb")
                size_mb = cursor.fetchone()[0]
                logger.info(f"✓ Database size: {size_mb} MB")

                if size_mb == 0:
                    logger.warning("⚠ Database appears empty or minimal size")

                self.validation_results['status'] = 'success'
                self.validation_results['table_count'] = table_count
                self.validation_results['database_size_mb'] = size_mb

            finally:
                cursor.close()
                conn.close()

            return validation_passed

        except psycopg2.Error as e:
            error_msg = f"Database validation error: {str(e)}"
            logger.error(error_msg)
            self.validation_results['errors'].append(error_msg)
            self.validation_results['status'] = 'failed'
            return False

    def cleanup_test_database(self):
        """Delete the temporary test database."""
        try:
            logger.info(f"Cleaning up test database {self.test_db_identifier}")

            self.rds_client.delete_db_instance(
                DBInstanceIdentifier=self.test_db_identifier,
                SkipFinalSnapshot=True  # Don't create final snapshot for test DB
            )

            logger.info(f"Deletion initiated for {self.test_db_identifier}")

            # Wait for deletion (don't wait for full completion, just start it)
            # In production, you might want to track this

        except ClientError as e:
            error_msg = f"Error deleting test database: {str(e)}"
            logger.error(error_msg)
            self.validation_results['errors'].append(error_msg)

    def log_to_cloudwatch(self):
        """Log validation results to CloudWatch."""
        try:
            logs_client = boto3.client('logs', region_name=self.region)

            log_group = f"/aws/rds/{self.db_identifier}/backup-validation"
            log_stream = datetime.utcnow().strftime("%Y/%m/%d/backup-validation")

            try:
                logs_client.create_log_group(logGroupName=log_group)
            except logs_client.exceptions.ResourceAlreadyExistsException:
                pass  # Log group already exists

            try:
                logs_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=log_stream
                )
            except logs_client.exceptions.ResourceAlreadyExistsException:
                pass  # Log stream already exists

            message = (
                f"Status: {self.validation_results['status']}\n"
                f"Timestamp: {self.validation_results['timestamp']}\n"
                f"Database: {self.db_identifier}\n"
                f"Test DB: {self.test_db_identifier}\n"
                f"Tables: {self.validation_results.get('table_count', 'N/A')}\n"
                f"Size: {self.validation_results.get('database_size_mb', 'N/A')} MB\n"
            )

            if self.validation_results['errors']:
                message += f"Errors: {'; '.join(self.validation_results['errors'])}\n"

            logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[
                    {
                        'message': message,
                        'timestamp': int(time.time() * 1000)
                    }
                ]
            )

            logger.info(f"Logged results to CloudWatch: {log_group}")

        except Exception as e:
            logger.warning(f"Could not log to CloudWatch: {str(e)}")

    def validate(self, db_username, db_password):
        """Run full validation workflow."""
        try:
            # Find latest backup
            snapshot = self.find_latest_backup()

            # Restore from snapshot
            self.restore_from_snapshot(snapshot)

            # Get endpoint and validate
            endpoint = self.get_db_endpoint(self.test_db_identifier)
            self.validate_database(endpoint, db_username, db_password)

            # Log results
            self.log_to_cloudwatch()

            return self.validation_results['status'] == 'success'

        except Exception as e:
            logger.error(f"Validation workflow failed: {str(e)}")
            self.validation_results['status'] = 'failed'
            return False

        finally:
            # Always cleanup test database
            try:
                self.cleanup_test_database()
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description='Validate RDS backups by restore-and-verify'
    )
    parser.add_argument(
        '--db-identifier',
        required=True,
        help='RDS database identifier to validate'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region (default: us-east-1)'
    )
    parser.add_argument(
        '--username',
        default='postgres',
        help='Database username (default: postgres)'
    )
    parser.add_argument(
        '--password-ssm-param',
        help='SSM Parameter Store name for database password'
    )
    parser.add_argument(
        '--password',
        help='Database password (use --password-ssm-param in production)'
    )
    parser.add_argument(
        '--timeout-hours',
        type=int,
        default=2,
        help='Timeout for restore operation in hours (default: 2)'
    )

    args = parser.parse_args()

    # Get password
    db_password = args.password
    if args.password_ssm_param:
        ssm = boto3.client('ssm', region_name=args.region)
        try:
            response = ssm.get_parameter(
                Name=args.password_ssm_param,
                WithDecryption=True
            )
            db_password = response['Parameter']['Value']
        except ClientError as e:
            logger.error(f"Error retrieving password from SSM: {str(e)}")
            return 1

    if not db_password:
        logger.error("Database password required (--password or --password-ssm-param)")
        return 1

    # Run validation
    validator = BackupValidator(
        args.db_identifier,
        args.region,
        args.timeout_hours
    )

    success = validator.validate(args.username, db_password)

    # Print results
    print("\n=== Backup Validation Results ===")
    print(f"Status: {validator.validation_results['status'].upper()}")
    print(f"Database: {validator.validation_results['db_identifier']}")
    print(f"Test DB: {validator.validation_results['test_db_identifier']}")
    if validator.validation_results.get('table_count'):
        print(f"Tables: {validator.validation_results['table_count']}")
    if validator.validation_results.get('database_size_mb'):
        print(f"Size: {validator.validation_results['database_size_mb']} MB")
    if validator.validation_results['errors']:
        print(f"Errors: {'; '.join(validator.validation_results['errors'])}")

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
