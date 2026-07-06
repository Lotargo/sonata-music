from .account_state import get_account_profile


def account_profile(request):
    return {
        'account_profile': get_account_profile(request),
    }
