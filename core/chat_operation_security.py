"""Authorization boundary for high-impact operations created through site chat."""

def is_authorized_chat_operator(user) -> bool:
    """Only an active Django superuser can authorize an executable chat action.

    Staff membership and being the requester of an approval are insufficient.
    """
    return (
        user is not None
        and getattr(user, "is_authenticated", False) is True
        and getattr(user, "is_active", False) is True
        and getattr(user, "is_superuser", False) is True
    )
