from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .settings import CONFIG

import json
import requests
import ipaddress
import random
import crypt
import os
from urllib.parse import urljoin
from datetime import timedelta


class UserProfile (models.Model):

    user = models.OneToOneField(User)
    container_limit = models.PositiveIntegerField()
    cpus = models.PositiveIntegerField()
    memory_mb = models.PositiveIntegerField()
    disk_mb = models.PositiveIntegerField()  # current no use
    expire_second = models.DurationField()

    def save(self, *args, **kwargs):
        if not self.container_limit:
            self.container_limit = CONFIG["user_container_limit"]
        if not self.cpus_limit:
            self.cpus_limit = CONFIG["user_cpus_limit"]
        if not self.memory_mb_limit:
            self.memory_mb_limit = CONFIG["user_memory_mb_limit"]
        if not self.disk_mb_limit:
            self.disk_mb_limit = CONFIG["user_disk_mb_limit"]
        if not self.expire_second:
            self.expire_second = timedelta(
                                     seconds=CONFIG["user_expire_second"])
        super(UserProfile, self).save(*args, **kwargs)


class IP4 (models.Model):

    ip4 = models.GenericIPAddressField(protocol="IPv4", unique=True)

    def __str__(self):
        return str(self.ip4)

    @classmethod
    def allocate_ip4(cls, cidr):
        it = iter(cidr)
        next(it)

        for ip in it:
            if not cls.objects.filter(ip4=str(ip)).exists():
                r = IP4(ip4=str(ip))
                r.save()
                return r


class Node (models.Model):

    name = models.CharField(max_length=20)
    url = models.URLField()
    usable = models.BooleanField(default=False)

    cert = models.FilePathField()
    key = models.FilePathField()

    gw4 = models.OneToOneField(IP4)
    nm4 = models.SmallIntegerField(
        default=24,
        validators=[
            MaxValueValidator(32),
            MinValueValidator(0)
        ]
    )

    def __str__(self):
        return "%s <%s>" % (self.name, self.url)

    def api(self, method, url, **kwargs):

        s = requests.Session()
        s.cert = (
            os.path.join(CONFIG["client_key_path_base"], self.cert),
            os.path.join(CONFIG["client_key_path_base"], self.key))
        s.verify = False
        url = urljoin(self.url, url)

        if method == "POST":
            res = s.post(url, **kwargs)
        elif method == "GET":
            res = s.get(url, **kwargs)
        elif method == "PUT":
            res = s.put(url, **kwargs)
        elif method == "DELETE":
            res = s.delete(url, **kwargs)

        d = res.json()
        s.close()

        return d

    @property
    def cidr(self):
        return ipaddress.IPv4Network(
                "%s/%d" % (self.gw4, self.nm4), strict=False)


class Template (models.Model):

    name = models.CharField(max_length=20)
    fingerprint = models.CharField(max_length=64)
    node = models.ForeignKey(Node)

    def __str__(self):
        return "%s <%s>" % (self.name, self.fingerprint)

    @property
    def source_dict(self):
        return {
             "type": "image",
             "mode": "pull",
             "server": str(self.node.url),
             "fingerprint": self.fingerprint,
        }


class Container (models.Model):

    name = models.CharField(max_length=16, unique=True,
                            verbose_name="Hostname")
    ip4 = models.OneToOneField(IP4, blank=True, null=True)
    node = models.ForeignKey(Node)
    userpro = models.ForeignKey(UserProfile)
    created = models.DateTimeField(auto_now_add=True)
   
    cpus = models.PositiveIntegerField(verbose_name="CPU")
    memory_mb = models.PositiveIntegerField(verbose_name="Memory (MB)")
    disk_mb = models.PositiveIntegerField(verbose_name="Storage (MB)")

    def create_container(self, passwd, template):
        if not self.ip4:
            ip4 = IP4.allocate_ip4(self.node.cidr)
            if ip4:
                self.ip4 = ip4
                self.save(update_fields=["ip4"])
            else:
                return False

        data = json.dumps({
            "name": self.name,
            "profiles": ["default"],
            "config": {
                "limits.cpus": str(self.cpus),
                "limits.memory": "{:d}m".format(self.memory_mb),
                "user.gw4": str(self.node.gw4),
                "user.ip4": str(self.ip4),
                "user.passwd":
                    crypt.crypt(passwd, "$6$%04x" % random.randint(0, 0xffff)),
            },
            "source": template.source_dict,
        })
        r = self.node.api("POST", "1.0/containers", data=data)

        # need to handle error properly
        return "error" not in r

    @property
    def container_config(self):
        r = self.node.api("GET", "1.0/containers/%s" % self.name)
        return r.get("metadata", {})

    def apply_config(self):
        conf = self.container_config
        newconf = {
            "config": conf.get("config", {}),
            "profiles": ["default"],
        }
        newconf["config"].update({
            "limits.cpus": str(self.cpus),
            "limits.memory": "{:d}m".format(self.memory_mb),
            "user.gw4": str(self.node.gw4),
            "user.ip4": str(self.ip4),
        })
        data = json.dumps(newconf)
        r = self.node.api("PUT", "1.0/containers/%s" % self.name, data=data)
        return r

    @property
    def container_state(self):
        r = self.node.api("GET", "1.0/containers/%s/state" % self.name)
        return r.get("metadata", {})

    def do_action(self, action, force=False, log=True):
        self.apply_config()  # 多 apply 几次也无妨

        data = json.dumps({
            "action": action,
            "timeout": 30,
            "force": force
        })
        r = self.node.api(
                "PUT", "1.0/containers/%s/state" % self.name, data=data)

        if 'error' not in r:
            uuid = r["operation"].rsplit('/', 1)[-1]
            op = Operation(
                    uuid=uuid,
                    what=("", "force-")[force] + action,
                    container=(None, self)[log]
                 )
            op.save()
            return op.status_str
        else:
            return None

    def delete_container(self, log=True):
        # 唔，lxc 有点 bug，删除容器还有些问题
        r = self.node.api("DELETE", "1.0/containers/%s" % self.name)

        uuid = r["operation"].rsplit('/', 1)[-1]
        op = Operation(
                uuid=uuid,
                what="delete",
                container=(None, self)[log]
        )
        op.save()

        return r


@receiver(post_delete, sender=Container)
def cleanup_after_container_deletion(sender, instance, using, **kwargs):
    if instance.container_state:
        instance.do_action("stop", True, log=False)
        instance.delete_container(log=False)
    if instance.ip4:
        instance.ip4.delete()


class Operation (models.Model):
    NOTFOUND_STATUS = 500
    uuid = models.UUIDField(primary_key=True, editable=False)
    what = models.CharField(max_length=10, blank=True)
    container = models.ForeignKey(Container, blank=True, null=True,
                                  editable=False, on_delete=models.SET_NULL)
    status_code = models.PositiveSmallIntegerField(default=100)
    created = models.DateTimeField(auto_now_add=True)

    def update_status(self):
        if not self.container:
            self.status_code = Operation.NOTFOUND_STATUS
            self.save(update_fields=["status_code"])
            return {}

        r = self.container.node.api(
                "GET", "1.0/operations/%s" % self.uuid)

        if r.get("error_code") == 404:
            self.status_code = Operation.NOTFOUND_STATUS
        elif "status_code" in r:
            self.status_code = r["status_code"]

        self.save(update_fields=["status_code"])
        return r

    @property
    def status_str(self):
        if self.status_code < 200:
            self.update_status()

        d = {
            100: "OK",
            101: "Started",
            102: "Stopped",
            103: "Running",
            104: "Cancelling",
            105: "Pending",
            200: "Success",
            400: "Failure",
            401: "Cancelled",
            Operation.NOTFOUND_STATUS: "None",
        }
        return d.get(self.status_code, "Unknown")
