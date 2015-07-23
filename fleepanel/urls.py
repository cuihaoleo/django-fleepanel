from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.container_list, name='list'),
    url(r'^(?P<pk>\d+)/info$', views.container_info, name='info'),
    url(r'^(?P<pk>\d+)/action$', views.container_action, name='action'),
    url(r'^(?P<pk>\d+)/delete$$', views.delete_container, name='delete'),
    url(r'^create$', views.create_container, name='create'),
]
