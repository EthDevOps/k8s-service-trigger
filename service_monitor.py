#!/usr/bin/env python3

import os
import logging
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

def trigger_github_workflow(gh_token, event_type):
    """
    Trigger GitHub Actions workflow with the specified parameters
    """
    try:
        g = Github(gh_token)
        repo = g.get_repo(GITHUB_REPO)
        
        # Get the workflow by filename
        workflow = None
        for wf in repo.get_workflows():
            if wf.path.endswith(WORKFLOW_FILE):
                workflow = wf
                break
        
        if workflow is None:
            logger.error(f"Workflow {WORKFLOW_FILE} not found")
            return False

        # Create workflow dispatch event with inputs
        workflow.create_dispatch(
            ref="main",  # You might want to make this configurable
            inputs={
                "tenant": TENANT,
                "project": PROJECT
            }
        )
        
        logger.info(f"Successfully triggered workflow for event: {event_type}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to trigger workflow: {str(e)}")
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
                        trigger_github_workflow(GITHUB_TOKEN, event_type)
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
            import time
            time.sleep(5)

if __name__ == "__main__":
    main()
