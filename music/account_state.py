import os
from types import SimpleNamespace

from django.conf import settings
from django.core.files.storage import default_storage

from .models import UserProfile


SESSION_KEY = 'guest_account_profile'

PLAN_LABELS = {
    'standard': 'Standard',
    'pro': 'Pro',
}

QUALITY_LABELS = {
    'balanced': 'Balanced / 256 kbps',
    'high': 'High / 320 kbps',
    'lossless': 'Lossless / WAV',
}

DEFAULT_GUEST_PROFILE = {
    'display_name': '',
    'email': 'example@gmail.com',
    'plan': 'standard',
    'preferred_quality': 'high',
    'notifications_enabled': True,
    'library_auto_enhance': False,
    'avatar_path': '',
}


def get_guest_profile_data(request):
    return {**DEFAULT_GUEST_PROFILE, **request.session.get(SESSION_KEY, {})}


def clear_guest_profile(request):
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
        request.session.modified = True


def normalize_plan(value):
    return value if value in PLAN_LABELS else 'standard'


def normalize_quality(value):
    return value if value in QUALITY_LABELS else 'high'


def avatar_url_from_path(path):
    if not path:
        return None
    return f'{settings.MEDIA_URL}{path}'


def build_account_profile(data, username='User', is_guest=True):
    display_name = (data.get('display_name') or '').strip()
    plan = normalize_plan(data.get('plan'))
    preferred_quality = normalize_quality(data.get('preferred_quality'))
    public_name = display_name or username or 'User'
    avatar_url = data.get('avatar_url') or avatar_url_from_path(data.get('avatar_path'))

    return SimpleNamespace(
        display_name=display_name,
        public_name=public_name,
        username=username or 'User',
        subtitle='Гостевой режим' if is_guest else username,
        email=data.get('email') or 'example@gmail.com',
        plan=plan,
        plan_label=PLAN_LABELS[plan],
        is_pro=plan == 'pro',
        preferred_quality=preferred_quality,
        preferred_quality_label=QUALITY_LABELS[preferred_quality],
        notifications_enabled=bool(data.get('notifications_enabled')),
        library_auto_enhance=bool(data.get('library_auto_enhance')),
        avatar_url=avatar_url,
        avatar_initial=(public_name[:1] or 'U').upper(),
        is_guest=is_guest,
    )


def account_payload(account_profile):
    avatar_url = account_profile.avatar_url
    return {
        'display_name': account_profile.public_name,
        'username': account_profile.username,
        'avatar_initial': account_profile.avatar_initial,
        'email': account_profile.email,
        'plan': account_profile.plan,
        'plan_label': account_profile.plan_label,
        'is_pro': account_profile.is_pro,
        'preferred_quality': account_profile.preferred_quality,
        'notifications_enabled': account_profile.notifications_enabled,
        'library_auto_enhance': account_profile.library_auto_enhance,
        'avatar_url': avatar_url,
    }


def get_account_profile(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        avatar_url = profile.avatar.url if profile.avatar else None
        return build_account_profile(
            {
                'display_name': profile.display_name,
                'email': request.user.email or 'example@gmail.com',
                'plan': profile.plan,
                'preferred_quality': profile.preferred_quality,
                'notifications_enabled': profile.notifications_enabled,
                'library_auto_enhance': profile.library_auto_enhance,
                'avatar_url': avatar_url,
            },
            username=request.user.get_username(),
            is_guest=False,
        )

    data = get_guest_profile_data(request)
    return build_account_profile(data)


def save_account_profile(request):
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.display_name = request.POST.get('display_name', '').strip()
        profile.plan = normalize_plan(request.POST.get('plan', profile.plan))
        profile.preferred_quality = normalize_quality(request.POST.get('preferred_quality', profile.preferred_quality))
        profile.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        profile.library_auto_enhance = request.POST.get('library_auto_enhance') == 'on'

        email = request.POST.get('email', '').strip()
        if email and email != 'example@gmail.com':
            request.user.email = email
            request.user.save(update_fields=['email'])

        avatar = request.FILES.get('avatar')
        if avatar:
            profile.avatar = avatar

        profile.save()
        account_profile = get_account_profile(request)
        if profile.avatar:
            account_profile.avatar_url = f'{profile.avatar.url}?v={int(profile.updated_at.timestamp())}'
        return account_profile

    data = {**DEFAULT_GUEST_PROFILE, **request.session.get(SESSION_KEY, {})}
    data.update({
        'display_name': request.POST.get('display_name', '').strip(),
        'email': request.POST.get('email', '').strip() or 'example@gmail.com',
        'plan': normalize_plan(request.POST.get('plan', data.get('plan'))),
        'preferred_quality': normalize_quality(request.POST.get('preferred_quality', data.get('preferred_quality'))),
        'notifications_enabled': request.POST.get('notifications_enabled') == 'on',
        'library_auto_enhance': request.POST.get('library_auto_enhance') == 'on',
    })

    avatar = request.FILES.get('avatar')
    if avatar:
        if not request.session.session_key:
            request.session.create()
        filename = os.path.basename(avatar.name)
        path = os.path.join('avatars', 'guest', request.session.session_key, filename)
        data['avatar_path'] = default_storage.save(path, avatar)

    request.session[SESSION_KEY] = data
    request.session.modified = True
    account_profile = build_account_profile(data)
    if account_profile.avatar_url:
        account_profile.avatar_url = f'{account_profile.avatar_url}?v={request.session.session_key}'
    return account_profile
