from django.conf import settings

CONFIG = {
    "user_container_limit": 4,
    "user_cpus_limit": 6,
    "user_memory_mb_limit": 2048,
    "user_disk_mb_limit": 10000,
    "user_expire_second": 30*24*3600,
    "client_key_path_base": "/",
}

CONFIG.update(getattr(settings, 'FLEEPANEL_CONFIG', {}))
