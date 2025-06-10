# ADK Voice Agent - Google Cloud Run Deployment Guide

This guide provides step-by-step instructions for deploying the ADK Voice Agent to Google Cloud Run for production use.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setting Up Your Google Cloud Project](#setting-up-your-google-cloud-project)
3. [Managing Secrets](#managing-secrets)
4. [Deploying to Cloud Run](#deploying-to-cloud-run)
5. [Setting Up Custom Domain (Optional)](#setting-up-custom-domain-optional)
6. [Connecting Frontend to Backend](#connecting-frontend-to-backend)
7. [Monitoring and Scaling](#monitoring-and-scaling)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying to Google Cloud Run, ensure you have:

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed locally
- [Docker](https://docs.docker.com/get-docker/) installed locally
- A Google Cloud account and billing enabled
- The ADK Voice Agent code repository cloned locally
- Gemini API key (obtain from [Google AI Studio](https://makersuite.google.com/app/apikey))
- Google Calendar API credentials (`credentials.json`)

## Setting Up Your Google Cloud Project

### 1. Create or select a project

```bash
# Create a new project
gcloud projects create YOUR_PROJECT_ID --name="ADK Voice Agent"

# Or select an existing project
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable required APIs

```bash
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  calendar-json.googleapis.com
```

### 3. Set up billing

Ensure billing is enabled for your project through the [Google Cloud Console](https://console.cloud.google.com/billing).

## Managing Secrets

The ADK Voice Agent requires several sensitive configuration values that should be stored securely.

### 1. Create secrets in Secret Manager

```bash
# API key for backend access
gcloud secrets create api-key --data-file=<(echo -n "your-secure-api-key")

# Gemini API key
gcloud secrets create gemini-api-key --data-file=<(echo -n "your-gemini-api-key")

# Google Calendar credentials
gcloud secrets create google-calendar-credentials --data-file=credentials.json
```

### 2. Grant access to your Cloud Run service

```bash
# Set environment variables for your service account
PROJECT_ID=$(gcloud config get-value project)
SERVICE_ACCOUNT="service-${PROJECT_ID}@gcp-sa-cloudrun.iam.gserviceaccount.com"

# Grant Secret Manager Secret Accessor role
gcloud secrets add-iam-policy-binding api-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
  
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
  
gcloud secrets add-iam-policy-binding google-calendar-credentials \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## Deploying to Cloud Run

### 1. Build and push the container

You can deploy directly from source or build the container separately:

#### Option A: Deploy directly from source

```bash
gcloud run deploy adk-voice-agent \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ALLOWED_ORIGINS=https://your-frontend-domain.com" \
  --update-secrets="API_KEY=api-key:latest" \
  --update-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --mount="type=secret,target=/secrets/google-calendar-credentials,source=google-calendar-credentials"
```

#### Option B: Build and deploy separately

```bash
# Build using Cloud Build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/adk-voice-agent

# Deploy to Cloud Run
gcloud run deploy adk-voice-agent \
  --image gcr.io/YOUR_PROJECT_ID/adk-voice-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "ALLOWED_ORIGINS=https://your-frontend-domain.com" \
  --update-secrets="API_KEY=api-key:latest" \
  --update-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --mount="type=secret,target=/secrets/google-calendar-credentials,source=google-calendar-credentials"
```

### 2. Verify the deployment

```bash
# Get the service URL
gcloud run services describe adk-voice-agent \
  --platform managed \
  --region us-central1 \
  --format="value(status.url)"
  
# Test the API endpoint
curl -H "X-API-Key: your-api-key" [SERVICE_URL]/api/status
```

## Setting Up Custom Domain (Optional)

### 1. Map a custom domain to your service

```bash
# Verify domain ownership through Google Cloud Console first

# Map your domain
gcloud beta run domain-mappings create \
  --service adk-voice-agent \
  --domain api.yourdomain.com \
  --region us-central1
```

### 2. Configure DNS for your domain

Add the provided verification records to your domain's DNS configuration.

## Connecting Frontend to Backend

Update your frontend application to connect to the Cloud Run service:

```javascript
// Replace with your Cloud Run URL or custom domain
const API_URL = 'https://adk-voice-agent-xxxx-xx.a.run.app';
// or
const API_URL = 'https://api.yourdomain.com';

// For WebSocket connections
const WS_URL = API_URL.replace('https://', 'wss://');
```

## Monitoring and Scaling

### Viewing logs

```bash
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=adk-voice-agent" \
  --limit=10
```

### Setting up scaling

Cloud Run automatically scales based on traffic, but you can configure:

```bash
# Configure max instances
gcloud run services update adk-voice-agent \
  --max-instances=10

# Configure memory and CPU
gcloud run services update adk-voice-agent \
  --memory=512Mi \
  --cpu=1
```

## Troubleshooting

### Common issues and solutions:

1. **WebSocket connection issues**

   - Ensure your frontend WebSocket URL uses `wss://` (secure WebSocket)
   - Check CORS settings match your frontend domain

2. **Missing credentials**

   - Verify the secrets are correctly mounted using:
     ```bash
     gcloud run services describe adk-voice-agent
     ```
   - Check application logs for credential loading errors

3. **API key errors**

   - Confirm your frontend is passing the correct API key header
   - Verify the API_KEY environment variable is correctly set

4. **Google Calendar access issues**

   - Check that the Calendar API is enabled
   - Ensure the credentials.json file contains the correct scopes
   - Verify the service account has permission to access the calendars

### Viewing detailed logs

```bash
# View application logs in real-time
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=adk-voice-agent" \
  --limit=50 \
  --format="value(textPayload)" \
  --freshness=1h
```

---

## Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)
- [Google Calendar API Documentation](https://developers.google.com/calendar/api/guides/overview)
- [Google ADK Documentation](https://developers.google.com/adk)
