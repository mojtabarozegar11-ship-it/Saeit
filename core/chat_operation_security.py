"""Authorization boundary for high-impact operations created through site chat."""

def is_authorized_chat_operator(user) -> bool:
    """Only an active Django superuser can authorize an executable chat action.

    Staff membership and being the requester of an approval are insufficient.
    """
    return bool(
        user is not None
        and user.is_authenticated
        and user.is_active
        and user.is_superuser
    )
