"""
Status-Based Permission Control

This module provides status-based permission logic for tax returns.
While rbac/permissions.py defines what permissions each role has,
this module defines WHEN those permissions can be exercised based on return status.

Flow:
1. DRAFT: Client can edit ✅
2. IN_REVIEW: CPA can edit, client read-only ✅
3. CPA_APPROVED: Both read-only (locked) ✅

This implements the state machine for return lifecycle and CPA approval workflow.
"""

from enum import Enum
from typing import Optional
from src.rbac.permissions import Role, Permission


class ReturnStatus(str, Enum):
    """
    Tax return status states.

    Maps to return_status.status column in database.
    """
    DRAFT = "DRAFT"                     # Initial state, editable by client
    IN_REVIEW = "IN_REVIEW"             # Submitted to CPA, locked for client
    CPA_APPROVED = "CPA_APPROVED"       # Signed by CPA, locked for everyone
    EFILED = "EFILED"                   # E-filed with IRS
    ACCEPTED = "ACCEPTED"               # Accepted by IRS
    REJECTED = "REJECTED"               # Rejected by IRS, back to DRAFT


def can_edit_return(
    status: ReturnStatus,
    role: Role,
    is_assigned_cpa: bool = False,
    is_owner: bool = False
) -> bool:
    """
    Check if user can edit a tax return based on its status.

    Args:
        status: Current status of the return
        role: User's role
        is_assigned_cpa: Whether user is the assigned CPA for this return
        is_owner: Whether user owns this return (for SELF_EDIT_RETURN)

    Returns:
        True if user can edit, False otherwise

    Examples:
        >>> can_edit_return(ReturnStatus.DRAFT, Role.FIRM_CLIENT, is_owner=True)
        True
        >>> can_edit_return(ReturnStatus.IN_REVIEW, Role.FIRM_CLIENT, is_owner=True)
        False
        >>> can_edit_return(ReturnStatus.IN_REVIEW, Role.STAFF, is_assigned_cpa=True)
        True
        >>> can_edit_return(ReturnStatus.CPA_APPROVED, Role.STAFF)
        False
    """
    # DRAFT: Owner can edit (client or CPA preparing)
    if status == ReturnStatus.DRAFT:
        # Clients can edit their own drafts
        if role in {Role.FIRM_CLIENT, Role.DIRECT_CLIENT} and is_owner:
            return True
        # CPAs can edit any draft they're assigned to
        if role in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN} and is_assigned_cpa:
            return True
        return False

    # IN_REVIEW: Only assigned CPA can edit
    elif status == ReturnStatus.IN_REVIEW:
        if role in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN} and is_assigned_cpa:
            return True
        return False

    # CPA_APPROVED: Locked, no one can edit (must be reverted first)
    elif status == ReturnStatus.CPA_APPROVED:
        return False

    # EFILED: Locked, can't edit filed returns
    elif status == ReturnStatus.EFILED:
        return False

    # ACCEPTED: Locked
    elif status == ReturnStatus.ACCEPTED:
        return False

    # REJECTED: CPA can edit to fix and refile
    elif status == ReturnStatus.REJECTED:
        if role in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN} and is_assigned_cpa:
            return True
        return False

    # Unknown status: deny by default
    return False


def can_approve_return(
    status: ReturnStatus,
    role: Role,
    is_assigned_cpa: bool = False
) -> bool:
    """
    Check if user can approve a tax return.

    Only CPAs can approve, and only if return is IN_REVIEW.

    Args:
        status: Current status of the return
        role: User's role
        is_assigned_cpa: Whether user is the assigned CPA

    Returns:
        True if user can approve, False otherwise
    """
    # Must be a CPA role
    if role not in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN}:
        return False

    # Must be assigned to this return
    if not is_assigned_cpa:
        return False

    # Can only approve if IN_REVIEW
    if status == ReturnStatus.IN_REVIEW:
        return True

    return False


def can_submit_for_review(
    status: ReturnStatus,
    role: Role,
    is_owner: bool = False
) -> bool:
    """
    Check if user can submit a return for CPA review.

    Args:
        status: Current status of the return
        role: User's role
        is_owner: Whether user owns this return

    Returns:
        True if user can submit for review, False otherwise
    """
    # Can only submit DRAFT returns
    if status != ReturnStatus.DRAFT:
        return False

    # Clients can submit their own returns
    if role in {Role.FIRM_CLIENT, Role.DIRECT_CLIENT} and is_owner:
        return True

    # CPAs can submit on behalf of clients
    if role in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN}:
        return True

    return False


def can_revert_status(
    status: ReturnStatus,
    role: Role,
    is_assigned_cpa: bool = False
) -> bool:
    """
    Check if user can revert a return to DRAFT status.

    Useful for fixing approved returns or unlocking after rejection.

    Args:
        status: Current status of the return
        role: User's role
        is_assigned_cpa: Whether user is the assigned CPA

    Returns:
        True if user can revert, False otherwise
    """
    # Only CPAs and admins can revert
    if role not in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN}:
        return False

    # Must be assigned (or admin)
    if not is_assigned_cpa and role != Role.PLATFORM_ADMIN:
        return False

    # Can revert from these statuses
    if status in {ReturnStatus.IN_REVIEW, ReturnStatus.CPA_APPROVED, ReturnStatus.REJECTED}:
        return True

    # Cannot revert filed or accepted returns
    if status in {ReturnStatus.EFILED, ReturnStatus.ACCEPTED}:
        return False

    return False


def can_efile_return(
    status: ReturnStatus,
    role: Role,
    is_assigned_cpa: bool = False
) -> bool:
    """
    Check if user can e-file a return with IRS.

    Args:
        status: Current status of the return
        role: User's role
        is_assigned_cpa: Whether user is the assigned CPA

    Returns:
        True if user can e-file, False otherwise
    """
    # Only CPAs can e-file
    if role not in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN}:
        return False

    # Must be assigned (or admin)
    if not is_assigned_cpa and role != Role.PLATFORM_ADMIN:
        return False

    # Can only e-file CPA_APPROVED returns
    if status == ReturnStatus.CPA_APPROVED:
        return True

    return False


def can_view_return(
    status: ReturnStatus,
    role: Role,
    is_owner: bool = False,
    is_assigned_cpa: bool = False
) -> bool:
    """
    Check if user can view a tax return.

    Generally more permissive than edit permissions.

    Args:
        status: Current status of the return
        role: User's role
        is_owner: Whether user owns this return
        is_assigned_cpa: Whether user is the assigned CPA

    Returns:
        True if user can view, False otherwise
    """
    # Owner can always view their own return
    if is_owner and role in {Role.FIRM_CLIENT, Role.DIRECT_CLIENT}:
        return True

    # Assigned CPA can view
    if is_assigned_cpa and role in {Role.STAFF, Role.PARTNER}:
        return True

    # Platform admin can view all
    if role == Role.PLATFORM_ADMIN:
        return True

    # CPA_MANAGER can view all returns in their firm
    if role == Role.CPA_MANAGER:
        return True

    return False


def get_allowed_transitions(
    current_status: ReturnStatus,
    role: Role,
    is_assigned_cpa: bool = False
) -> list[ReturnStatus]:
    """
    Get list of statuses the return can transition to from current status.

    Args:
        current_status: Current status
        role: User's role
        is_assigned_cpa: Whether user is the assigned CPA

    Returns:
        List of valid next statuses
    """
    transitions = []

    # Only CPAs and admins can change status
    if role not in {Role.STAFF, Role.PARTNER, Role.PLATFORM_ADMIN, Role.CPA_MANAGER}:
        return transitions

    # Must be assigned (or admin)
    if not is_assigned_cpa and role not in {Role.PLATFORM_ADMIN, Role.CPA_MANAGER}:
        return transitions

    # Define state machine
    if current_status == ReturnStatus.DRAFT:
        transitions = [ReturnStatus.IN_REVIEW]

    elif current_status == ReturnStatus.IN_REVIEW:
        transitions = [ReturnStatus.CPA_APPROVED, ReturnStatus.DRAFT]  # Approve or send back

    elif current_status == ReturnStatus.CPA_APPROVED:
        transitions = [ReturnStatus.EFILED, ReturnStatus.DRAFT]  # E-file or revert

    elif current_status == ReturnStatus.EFILED:
        transitions = [ReturnStatus.ACCEPTED, ReturnStatus.REJECTED]

    elif current_status == ReturnStatus.REJECTED:
        transitions = [ReturnStatus.DRAFT]  # Fix and start over

    elif current_status == ReturnStatus.ACCEPTED:
        transitions = []  # Final state

    return transitions


def get_status_display_name(status: ReturnStatus) -> str:
    """Get user-friendly display name for status."""
    display_names = {
        ReturnStatus.DRAFT: "Draft",
        ReturnStatus.IN_REVIEW: "Under Review",
        ReturnStatus.CPA_APPROVED: "CPA Approved",
        ReturnStatus.EFILED: "E-Filed",
        ReturnStatus.ACCEPTED: "Accepted by IRS",
        ReturnStatus.REJECTED: "Rejected by IRS"
    }
    return display_names.get(status, str(status))


def get_status_description(status: ReturnStatus) -> str:
    """Get detailed description of what status means."""
    descriptions = {
        ReturnStatus.DRAFT: "Return is being prepared and can be edited.",
        ReturnStatus.IN_REVIEW: "Return has been submitted for CPA review. Client cannot edit.",
        ReturnStatus.CPA_APPROVED: "Return has been reviewed and approved by CPA. Ready to file.",
        ReturnStatus.EFILED: "Return has been e-filed with the IRS. Awaiting response.",
        ReturnStatus.ACCEPTED: "Return has been accepted by the IRS. Filing complete.",
        ReturnStatus.REJECTED: "Return was rejected by the IRS. Needs corrections."
    }
    return descriptions.get(status, "Unknown status")
