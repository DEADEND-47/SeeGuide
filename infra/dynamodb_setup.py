"""DynamoDB table setup: Provisions the SeeGuide telemetry traces table on AWS DynamoDB Free Tier."""

import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError


def setup_dynamodb_table(
    table_name: str = "seeguide-traces",
    region: str = "us-east-1",
    ttl_attribute: str = "expires_at"
) -> bool:
    """Provisions the DynamoDB traces table with on-demand capacity and 7-day TTL.
    
    Schema:
    - Partition Key: session_id (String)
    - Sort Key: timestamp (Number, ms epoch)
    - TTL Attribute: expires_at (Number, sec epoch)
    """
    try:
        dynamodb = boto3.client("dynamodb", region_name=region)
        
        # Check if table already exists
        existing_tables = dynamodb.list_tables().get("TableNames", [])
        if table_name in existing_tables:
            print(f"Table '{table_name}' already exists. Skipping creation.")
        else:
            print(f"Creating DynamoDB table '{table_name}' in region '{region}'...")
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {"AttributeName": "session_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"}
                ],
                AttributeDefinitions=[
                    {"AttributeName": "session_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "N"}
                ],
                BillingMode="PAY_PER_REQUEST"
            )
            print(f"Table creation initiated for '{table_name}'. Status: {table['TableDescription']['TableStatus']}")
            
            # Wait for table to be active
            waiter = dynamodb.get_waiter("table_exists")
            print("Waiting for table to become ACTIVE...")
            waiter.wait(TableName=table_name)
            print("Table is now ACTIVE.")

        # Configure 7-day TTL on expires_at attribute (NFR-6 compliance)
        print(f"Configuring TTL on attribute '{ttl_attribute}'...")
        try:
            dynamodb.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    "Enabled": True,
                    "AttributeName": ttl_attribute
                }
            )
            print(f"TTL successfully configured on '{ttl_attribute}'.")
        except ClientError as e:
            # If TTL is already enabled or in progress
            print(f"TTL configuration notice: {e}")

        print(f"DynamoDB setup complete for '{table_name}'.")
        return True

    except (NoCredentialsError, EndpointConnectionError) as e:
        print(f"AWS connection/credentials error: {e}")
        print("Note: If running in local or test mode without AWS credentials, mock storage is used.")
        return False
    except Exception as e:
        print(f"Error provisioning DynamoDB table: {e}")
        return False


def main():
    print("SeeGuide AWS DynamoDB Provisioner")
    success = setup_dynamodb_table()
    if not success:
        sys.exit(0)  # Exit gracefully for local development environments


if __name__ == "__main__":
    main()
