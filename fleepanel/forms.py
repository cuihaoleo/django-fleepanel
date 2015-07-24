from django import forms
from .models import Container, Node, Template


class ContainerForm(forms.ModelForm):
    template = forms.ModelChoiceField(queryset=Template.objects.all(),
                                      empty_label=None)
    node = forms.ModelChoiceField(queryset=Node.objects.all(),
                                  empty_label=None)
    passwd = forms.CharField(max_length=256, widget=forms.PasswordInput())
    passwd.label = "Admin Password"

    class Meta:
        model = Container
        fields = ['name', 'node', 'cpus', 'memory_mb', 'disk_mb']
