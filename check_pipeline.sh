#!/bin/bash

# Script to check GitHub Actions pipeline status efficiently
# Usage: ./check_pipeline.sh [workflow_name]

set -e

WORKFLOW_NAME=${1:-"CI"}
REPO_PATH=$(pwd)

echo "=== GitHub Actions Pipeline Status Check ==="
echo "Repository: $(basename "$REPO_PATH")"
echo "Workflow: $WORKFLOW_NAME"
echo "Time: $(date)"
echo

# Get the latest workflow runs
echo "📊 Latest workflow runs:"
gh run list --workflow="$WORKFLOW_NAME" --limit=3 --json status,conclusion,createdAt,headBranch,event,databaseId,displayTitle

echo
echo "🔍 Most recent run details:"
LATEST_RUN_ID=$(gh run list --workflow="$WORKFLOW_NAME" --limit=1 --json databaseId --jq '.[0].databaseId')

if [ -n "$LATEST_RUN_ID" ] && [ "$LATEST_RUN_ID" != "null" ]; then
    echo "Run ID: $LATEST_RUN_ID"
    
    # Get run status
    RUN_STATUS=$(gh run view "$LATEST_RUN_ID" --json status,conclusion,createdAt,headBranch,event,jobs --jq '.status')
    RUN_CONCLUSION=$(gh run view "$LATEST_RUN_ID" --json status,conclusion,createdAt,headBranch,event,jobs --jq '.conclusion // "in_progress"')
    
    echo "Status: $RUN_STATUS"
    echo "Conclusion: $RUN_CONCLUSION"
    
    # Show job summary
    echo
    echo "📋 Job Summary:"
    gh run view "$LATEST_RUN_ID" --json jobs --jq '.jobs[] | "\(.name): \(.status) (\(.conclusion // "running"))"'
    
    # If completed, show summary
    if [ "$RUN_STATUS" = "completed" ]; then
        echo
        if [ "$RUN_CONCLUSION" = "success" ]; then
            echo "✅ Pipeline completed successfully!"
            
            # Check if docker-publish job ran
            DOCKER_JOB_STATUS=$(gh run view "$LATEST_RUN_ID" --json jobs --jq '.jobs[] | select(.name == "docker-publish") | .conclusion // "not_found"')
            if [ "$DOCKER_JOB_STATUS" = "success" ]; then
                echo "🐳 Docker publish job completed successfully!"
                echo
                echo "🔧 You can test the Docker image with:"
                echo "docker pull ghcr.io/rwese/obsidian-postprocessor:latest"
            elif [ "$DOCKER_JOB_STATUS" = "not_found" ]; then
                echo "ℹ️  Docker publish job was skipped (likely not on main branch)"
            else
                echo "❌ Docker publish job failed or didn't run"
            fi
        else
            echo "❌ Pipeline failed with conclusion: $RUN_CONCLUSION"
            
            # Show failed jobs
            echo
            echo "💥 Failed jobs:"
            gh run view "$LATEST_RUN_ID" --json jobs --jq '.jobs[] | select(.conclusion == "failure") | "\(.name): \(.conclusion)"'
        fi
    else
        echo "⏳ Pipeline is still running..."
        
        # Show running jobs
        echo
        echo "🏃 Currently running jobs:"
        gh run view "$LATEST_RUN_ID" --json jobs --jq '.jobs[] | select(.status == "in_progress") | "\(.name): \(.status)"'
    fi
    
    echo
    echo "🔗 View full details: $(gh run view "$LATEST_RUN_ID" --json url --jq '.url')"
else
    echo "❌ No workflow runs found for '$WORKFLOW_NAME'"
fi

echo
echo "=== End of Pipeline Status ==="