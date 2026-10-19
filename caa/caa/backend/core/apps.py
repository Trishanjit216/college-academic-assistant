from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from django.db.models.signals import post_delete, post_save, pre_save
        from . import notify
        from .models import Event, SyllabusEntry
        pre_save.connect(notify.event_pre_save, sender=Event, dispatch_uid="caa_event_pre")
        post_save.connect(notify.event_post_save, sender=Event, dispatch_uid="caa_event_post")
        post_delete.connect(notify.event_post_delete, sender=Event, dispatch_uid="caa_event_del")
        pre_save.connect(notify.syllabus_pre_save, sender=SyllabusEntry, dispatch_uid="caa_syl_pre")
        post_save.connect(notify.syllabus_post_save, sender=SyllabusEntry, dispatch_uid="caa_syl_post")
        post_delete.connect(notify.syllabus_post_delete, sender=SyllabusEntry, dispatch_uid="caa_syl_del")
