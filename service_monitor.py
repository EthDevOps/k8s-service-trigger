#!/usr/bin/env python3

import os
import logging
import time
from typing import Dict
from kubernetes import client, config, watch
from github import Github

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPO')
WORKFLOW_FILE = os.environ.get('WORKFLOW_FILE')
TENANT = os.environ.get('TENANT')
PROJECT = os.environ.get('PROJECT')

# Store the last trigger time globally
last_trigger_global = 0
DEBOUNCE_INTERVAL = 180  # 3 minutes in seconds

def set_last_trigger(timestamp: float) -> None:
    """Update the last trigger timestamp"""
    global last_trigger_global
    last_trigger_global = timestamp

def get_last_trigger() -> float:
    """Get the last trigger timestamp"""
    global last_trigger_global
    return last_trigger_global

def trigger_github_workflow(gh_token: str, event_type: str, service_key: str) -> bool:
    """
    Trigger GitHub Actions workflow with debouncing and detailed error logging
    
    Args:
        gh_token: GitHub authentication token
        event_type: Type of the Kubernetes event
        service_key: Unique identifier for the service (namespace/name)
        
    Returns:
        bool: True if workflow was triggered, False otherwise
    """
    if not GITHUB_REPO:
        logger.error("GITHUB_REPO environment variable not set")
        return False
    
    if not WORKFLOW_FILE:
        logger.error("WORKFLOW_FILE environment variable not set")
        return False

    current_time = time.time()
    last_trigger_time = get_last_trigger()
    
    # Check if enough time has passed since the last trigger
    time_since_last = current_time - last_trigger_time
    if time_since_last < DEBOUNCE_INTERVAL:
        logger.info(f"Skipping workflow trigger for {service_key} due to debouncing (last trigger was {int(time_since_last)} seconds ago)")
        return False

    try:
        logger.info(f"Connecting to GitHub repo: {GITHUB_REPO}")
        g = Github(gh_token)
        repo = g.get_repo(GITHUB_REPO)
        
        # Get all workflows and log them for debugging
        workflows = list(repo.get_workflows())
        logger.info(f"Found {len(workflows)} workflows in repository")
        for wf in workflows:
            logger.info(f"Available workflow: {wf.path} (ID: {wf.id})")
        
        # Get the workflow by filename
        workflow = None
        for wf in workflows:
            if wf.path.endswith(WORKFLOW_FILE):
                workflow = wf
                logger.info(f"Found matching workflow: {wf.path} (ID: {wf.id})")
                break
        
        if workflow is None:
            logger.error(f"Workflow {WORKFLOW_FILE} not found in repository {GITHUB_REPO}")
            return False

        # Prepare inputs
        inputs = {
            "team": TENANT or "",
            "project": PROJECT or ""
        }
        
        logger.info(f"Triggering workflow dispatch for {workflow.path} with inputs: {inputs}")
        
        # Create workflow dispatch event with inputs
        try:
            workflow.create_dispatch(
                ref="main",  # You might want to make this configurable
                inputs=inputs
            )
            # Update the last trigger time only on successful dispatch
            set_last_trigger(current_time)
            logger.info(f"Successfully triggered workflow {workflow.path} for event: {event_type} (service: {service_key})")
            return True
            
        except Exception as dispatch_error:
            logger.error(f"Failed to dispatch workflow: {str(dispatch_error)}")
            # Try to get more details about the error
            if hasattr(dispatch_error, 'response'):
                response = getattr(dispatch_error, 'response')
                if response:
                    logger.error(f"GitHub API Response: {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Failed to trigger workflow: {str(e)}")
        # Try to get more details about the error
        if hasattr(e, 'response'):
            response = getattr(e, 'response')
            if response:
                logger.error(f"GitHub API Response: {response.status_code} - {response.text}")
        return False

def watch_services():
    """
    Watch for changes in LoadBalancer services
    """
    try:
        # Try to load in-cluster config first
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        v1 = client.CoreV1Api()
        w = watch.Watch()
        
        logger.info("Starting to watch LoadBalancer services...")
        
        for event in w.stream(v1.list_service_for_all_namespaces):
            service = event['object']
            
            # Only process LoadBalancer services
            if service.spec.type == 'LoadBalancer':
                event_type = event['type']
                logger.info(f"LoadBalancer service event: {event_type} - {service.metadata.namespace}/{service.metadata.name}")
                
                # Trigger workflow for relevant events
                if event_type in ['ADDED', 'MODIFIED', 'DELETED']:
                    if GITHUB_TOKEN:
                        service_key = f"{service.metadata.namespace}/{service.metadata.name}"
                        trigger_github_workflow(GITHUB_TOKEN, event_type, service_key)
                    else:
                        logger.error("GITHUB_TOKEN environment variable not set")

    except Exception as e:
        logger.error(f"Error watching services: {str(e)}")
        raise

def main():
    """
    Main function to start the service monitor
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN environment variable must be set")
        exit(1)

    while True:
        try:
            watch_services()
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            # Wait a bit before retrying
            time.sleep(5)

if __name__ == "__main__":
    main()
