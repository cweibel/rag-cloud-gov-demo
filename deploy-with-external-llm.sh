#!/bin/bash
# deploy.sh - Simple deployment script for embedded model

echo "RAG Demo Deployment (Embedded Model)"
echo "===================================="

# Check if database already exists
if cf service my-rag-db > /dev/null 2>&1; then
    echo "Database service 'my-rag-db' already exists"
else
    echo "Creating PostgreSQL service..."
    cf create-service aws-rds micro-psql my-rag-db
    
    echo "Waiting for service to provision (this may take 5-10 minutes)..."
    while true; do
        STATUS=$(cf service my-rag-db | grep "status:" | awk '{print $2}')
        if [ "$STATUS" = "create" ] && [ "$(cf service my-rag-db | grep "status:" | awk '{print $3}')" = "succeeded" ]; then
            echo "Database provisioned successfully!"
            break
        fi
        echo "Still waiting for database... (current status: $STATUS)"
        sleep 30
    done
fi

echo "Deploying application..."
cf push

# Get app status
APP_STATUS=$(cf app rag-demo | grep "#0" | awk '{print $2}')
if [ "$APP_STATUS" != "running" ]; then
    echo "Waiting for app to start..."
    sleep 30
fi

# Get the app URL
APP_URL=$(cf app rag-demo | grep "routes:" | awk '{print $2}')

if [ -z "$APP_URL" ]; then
    echo "Error: Could not determine app URL"
    exit 1
fi

echo "App deployed at: https://$APP_URL"

# Load sample data
echo "Loading sample data..."
UPLOAD_RESPONSE=$(curl -s -X POST "https://${APP_URL}/upload" \
  -H "Content-Type: application/json" \
  -d @data/sample_documents.json)

echo "Upload response: $UPLOAD_RESPONSE"

# Check configuration
echo "Checking configuration..."
CONFIG_RESPONSE=$(curl -s "https://${APP_URL}/config")
echo "Configuration: $CONFIG_RESPONSE"

# Test status endpoint
echo "Checking application status..."
STATUS_RESPONSE=$(curl -s "https://${APP_URL}/status")
echo "Status: $STATUS_RESPONSE"

echo ""
echo "Deployment complete!"
echo "===================="
echo "Application URL: https://$APP_URL"
echo ""
echo "Try these commands to test:"
echo "  curl https://${APP_URL}/status"
echo "  curl -X POST https://${APP_URL}/query -H 'Content-Type: application/json' -d '{\"question\": \"What is Cloud.gov?\"}'"