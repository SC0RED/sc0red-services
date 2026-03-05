#!/bin/bash
#
# Branch Name Checker
#
# Validates git branch names follow conventions:
# - Long-lived: development, testing, demo, production
# - Feature: feature/{ticket-id}-{description}
# - Bugfix: bugfix/{ticket-id}-{description}
# - Hotfix: hotfix/{ticket-id}-{description}
# - Chore: chore/{ticket-id}-{description}
# - Docs: docs/{ticket-id}-{description}
# - Refactor: refactor/{ticket-id}-{description}
# - Test: test/{ticket-id}-{description}
#

set -euo pipefail

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD)

error_exit() {
    echo ""
    echo "BRANCH NAME VIOLATION"
    echo ""
    echo "Error: $1"
    echo ""
    echo "Valid patterns:"
    echo "  Long-lived branches:"
    echo "    development, testing, demo, production"
    echo ""
    echo "  Work branches (require ticket ID):"
    echo "    feature/{TICKET-ID}-{description}  - New features"
    echo "    bugfix/{TICKET-ID}-{description}   - Bug fixes"
    echo "    hotfix/{TICKET-ID}-{description}   - Urgent fixes"
    echo "    chore/{TICKET-ID}-{description}    - Maintenance tasks"
    echo "    docs/{TICKET-ID}-{description}     - Documentation"
    echo "    refactor/{TICKET-ID}-{description} - Code refactoring"
    echo "    test/{TICKET-ID}-{description}     - Test additions"
    echo ""
    echo "Examples:"
    echo "    feature/SF-123-add-user-authentication"
    echo "    bugfix/PROJ-456-fix-login-timeout"
    echo "    hotfix/SF-789-critical-security-patch"
    echo ""
    echo "To rename your branch:"
    echo "    git branch -m <old-name> <new-name>"
    echo ""
    exit 1
}

validate_ticket_id() {
    local ticket_id="$1"

    if [[ ! $ticket_id =~ ^[A-Z]{2,}-[0-9]+$ ]]; then
        error_exit "Ticket ID '$ticket_id' must be format: {PROJECT}-{NUMBER} (e.g., SF-123, PROJ-456)"
    fi
}

validate_description() {
    local description="$1"

    if [[ ${#description} -lt 3 ]]; then
        error_exit "Description '$description' must be at least 3 characters"
    fi

    if [[ ${#description} -gt 50 ]]; then
        error_exit "Description '$description' must be 50 characters or less"
    fi

    if [[ ! $description =~ ^[a-z0-9-]+$ ]]; then
        error_exit "Description '$description' must contain only lowercase letters, numbers, and hyphens"
    fi

    if [[ $description =~ ^- ]] || [[ $description =~ -$ ]]; then
        error_exit "Description '$description' cannot start or end with hyphen"
    fi

    if [[ $description =~ -- ]]; then
        error_exit "Description '$description' cannot contain consecutive hyphens"
    fi
}

validate_branch_with_ticket() {
    local branch_type="$1"
    local branch_suffix="$2"

    if [[ ! $branch_suffix =~ ^([A-Z]{2,}-[0-9]+)-(.+)$ ]]; then
        error_exit "$branch_type branch must follow format: $branch_type/{ticket-id}-{description}"
    fi

    local ticket_id="${BASH_REMATCH[1]}"
    local description="${BASH_REMATCH[2]}"

    validate_ticket_id "$ticket_id"
    validate_description "$description"
}

case "$BRANCH_NAME" in
    development|testing|demo|production)
        echo "Valid environment branch: $BRANCH_NAME"
        exit 0
        ;;

    feature/*)
        branch_suffix="${BRANCH_NAME#feature/}"
        validate_branch_with_ticket "feature" "$branch_suffix"
        echo "Valid feature branch: $BRANCH_NAME"
        exit 0
        ;;

    bugfix/*)
        branch_suffix="${BRANCH_NAME#bugfix/}"
        validate_branch_with_ticket "bugfix" "$branch_suffix"
        echo "Valid bugfix branch: $BRANCH_NAME"
        exit 0
        ;;

    hotfix/*)
        branch_suffix="${BRANCH_NAME#hotfix/}"
        validate_branch_with_ticket "hotfix" "$branch_suffix"
        echo "Valid hotfix branch: $BRANCH_NAME"
        exit 0
        ;;

    chore/*)
        branch_suffix="${BRANCH_NAME#chore/}"
        validate_branch_with_ticket "chore" "$branch_suffix"
        echo "Valid chore branch: $BRANCH_NAME"
        exit 0
        ;;

    docs/*)
        branch_suffix="${BRANCH_NAME#docs/}"
        validate_branch_with_ticket "docs" "$branch_suffix"
        echo "Valid docs branch: $BRANCH_NAME"
        exit 0
        ;;

    refactor/*)
        branch_suffix="${BRANCH_NAME#refactor/}"
        validate_branch_with_ticket "refactor" "$branch_suffix"
        echo "Valid refactor branch: $BRANCH_NAME"
        exit 0
        ;;

    test/*)
        branch_suffix="${BRANCH_NAME#test/}"
        validate_branch_with_ticket "test" "$branch_suffix"
        echo "Valid test branch: $BRANCH_NAME"
        exit 0
        ;;

    HEAD|main|master)
        echo "Warning: Using special Git branch '$BRANCH_NAME'"
        echo "   Consider using environment branches: development, testing, demo, production"
        exit 0
        ;;

    *)
        error_exit "Branch name '$BRANCH_NAME' does not follow naming conventions"
        ;;
esac
