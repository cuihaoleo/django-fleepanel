from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template import RequestContext, loader
from django.views.generic import ListView
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpResponse, Http404, HttpResponseBadRequest
from .models import Container, Template, Node
from django.db import IntegrityError

import json

@require_GET
@login_required
def container_list (request):
    userpro = request.user.userprofile
    container_list = userpro.container_set.all()
    context = RequestContext(request, {
        'container_list': container_list,
        'userpro': userpro,
        'template_list': Template.objects.all(),
        'node_list': Node.objects.filter(usable = True),
    })
    return render(request, 'container_list.html', context)


@require_GET
@login_required
def container_info (request, pk):
    userpro = request.user.userprofile
    container = get_object_or_404(Container, pk=pk, userpro=userpro)
    context = RequestContext(request, {
        'container': container,
        'state': container.container_state,
        'operation_list': container.operation_set.order_by("-created").all(),
    })
    return render(request, 'container_info.html', context)


@require_POST
@login_required
def container_action (request, pk):
    userpro = request.user.userprofile
    container = get_object_or_404(Container, pk=pk, userpro=userpro)

    action = request.body.decode()
    force = False 

    if action.startswith("force-"):
        force = True
        action = action.split("-", 1)[-1]

    if action in ['start', 'stop', 'restart']:
        return HttpResponse(container.do_action(action, force=force))
    else:
        raise Http404


@login_required
@require_POST
def create_container (request):
    if not all(request.POST.get(k)
            for k in ("hostname", "node", "template", "passwd")):
        return HttpResponseBadRequest(json.dumps(request.POST))

    userpro = request.user.userprofile
    con = Container(
            name = request.POST["hostname"],
            node = Node.objects.get(pk = request.POST["node"]),
            userpro = userpro,
          )

    try:
        con.save()
    except IntegrityError:
        return HttpResponse(json.dumps({ "error": "DBError"}))

    if con.create_container(
            passwd = request.POST["passwd"],
            template = Template.objects.get(pk = request.POST["template"])):
        return HttpResponse(json.dumps({}))
    else:
        return HttpResponse(json.dumps({ "error": "Something went wrong!"}))


@login_required
@require_POST
def delete_container (request, pk):
    userpro = request.user.userprofile
    container = get_object_or_404(Container, pk=pk, userpro=userpro)
    # 以后再加点验证吧
    container.delete()
    return HttpResponse("bye~")

