from django import forms
from .models import Container, Node, Template, UserProfile


class ContainerForm(forms.ModelForm):
    template = forms.ModelChoiceField(queryset=Template.objects.all(),
                                      empty_label=None)
    node = forms.ModelChoiceField(queryset=Node.objects.all(),
                                  empty_label=None)
    passwd = forms.CharField(max_length=256, widget=forms.PasswordInput())
    passwd.label = "Admin Password"

    userpro = forms.ModelChoiceField(queryset=UserProfile.objects.all(),
                                     widget=forms.HiddenInput(),
                                     label="")

    class Meta:
        model = Container
        fields = ['name', 'node', 'cpus', 'memory_mb', 'disk_mb', 'userpro']

    def clean(self):
        cleaned_data = super(ContainerForm, self).clean()
        userpro = cleaned_data.get("userpro")

        if userpro:
            for key, value in userpro.quota_stat.items():
                # why default 1? Cause container_num should increase 1...
                if cleaned_data.get(key, 1) + value > getattr(userpro, key):
                    msg = "Quota exceed..."
                    self.add_error(key, msg)
