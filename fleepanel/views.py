from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.views.decorators.http import require_GET, require_POST
from django.http import HttpResponse, Http404, \
                        JsonResponse, HttpResponseForbidden
from .models import Container, Template, Node
from .forms import ContainerForm


@require_GET
@login_required
def container_list(request):
    userpro = request.user.userprofile
    container_list = userpro.container_set.all()
    node_list = Node.objects.filter(usable=True)

    stats = userpro.quota_stat
    left = {}
    for key in stats:
        left[key] = getattr(userpro, key) - stats[key]

    context = RequestContext(request, {
        'left': left,
        'container_list': container_list,
        'userpro': userpro,
        'node_list': node_list,
        'template_list': Template.objects.all(),
        'node_list': Node.objects.filter(usable=True),
        'form': ContainerForm(initial={"userpro": userpro})
    })
    return render(request, 'container_list.html', context)


@require_GET
@login_required
def container_info(request, pk):
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
def container_action(request, pk):
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
def delete_container(request, pk):
    userpro = request.user.userprofile
    container = get_object_or_404(Container, pk=pk, userpro=userpro)
    # 以后再加点验证吧
    container.delete()
    return HttpResponse("bye~")


@login_required
@require_POST
def create_container(request):
    form = ContainerForm(request.POST)
    if form.is_valid():
        userpro = request.user.userprofile
        con = form.save(commit=False)

        if con.userpro != userpro:
            return HttpResponseForbidden("UserProfile not match.")
        else:
            con.save()

        if con.create_container(passwd=form.cleaned_data["passwd"],
                                template=form.cleaned_data["template"]):
            return JsonResponse({"error": False})
        else:
            return JsonResponse({
                "error": True,
                "verbose": {
                    "label": "Backend",
                    "message": "Something went wrong :3",
                },
            })
    else:
        error_list = []
        for fieldname, errors in form.errors.items():
            if fieldname != "__all__":
                error_list.append({
                    "id": form[fieldname].id_for_label,
                    "label": form[fieldname].label,
                    "message": ' '.join(errors),
                })
            else:
                error_list.append({
                    "label": "*",
                    "message": ' '.join(errors),
                })

        return JsonResponse({"error": True, "verbose": error_list})
