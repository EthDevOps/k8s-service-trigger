# Kubernetes LoadBalancer Service Monitor

This tool monitors Kubernetes LoadBalancer services for changes and triggers GitHub Actions workflows in response to those changes.

## Overview

The service monitor watches for any changes (creation, modification, or deletion) to LoadBalancer services across all namespaces in your Kubernetes cluster. When a change is detected, it triggers the `ansible.yaml` workflow in the `ethdevops/internal-stack-iac` repository with specific parameters.

## Prerequisites

- Kubernetes cluster access
- GitHub Personal Access Token with workflow permissions
- Docker (for building the container image)
- kubectl configured with cluster access

## Configuration

### 1. Build the Docker Image

```bash
docker build -t your-registry/service-monitor:latest .
docker push your-registry/service-monitor:latest
```

### 2. Create GitHub Token Secret

Create a GitHub Personal Access Token with workflow permissions and create the secret:

```bash
# Replace YOUR_GITHUB_TOKEN with your actual token
kubectl create namespace monitoring
echo -n 'YOUR_GITHUB_TOKEN' | base64 | kubectl create secret generic github-token \
    --namespace monitoring \
    --from-file=GITHUB_TOKEN=/dev/stdin
```

### 3. Update Deployment Image

Edit `k8s/deployment.yaml` and update the image field with your registry path:

```yaml
image: your-registry/service-monitor:latest
```

### 4. Deploy to Kubernetes

```bash
kubectl apply -f k8s/rbac.yaml
kubectl apply -f k8s/deployment.yaml
```

## Verification

Check if the pod is running:

```bash
kubectl get pods -n monitoring
```

View the logs:

```bash
kubectl logs -n monitoring -l app=service-monitor -f
```

## How It Works

1. The service monitor uses the Kubernetes API to watch for changes in LoadBalancer services
2. When a change is detected, it triggers the GitHub Actions workflow with:
   - Tenant: ethquokkaops
   - Project: colo-loadbalancers

## Troubleshooting

### Check Pod Status
```bash
kubectl describe pod -n monitoring -l app=service-monitor
```

### Check Logs
```bash
kubectl logs -n monitoring -l app=service-monitor -f
```

### Common Issues

1. **Pod can't pull image**: Check your image registry credentials and image path
2. **Permission denied**: Verify RBAC permissions are correctly configured
3. **GitHub workflow not triggering**: Check the GitHub token permissions and validity

## Security Considerations

- The service runs with minimal permissions using RBAC
- The container runs as a non-root user
- The filesystem is read-only
- The container has resource limits defined

## Maintenance

- Regularly update the dependencies in `requirements.txt`
- Monitor the pod's resource usage and adjust limits as needed
- Rotate the GitHub token periodically
- Keep the Docker base image updated for security patches
