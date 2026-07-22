from django import forms


class ContactForm(forms.Form):
    """The theme's contact block, wired to something real.

    Widget placeholders replace labels because the theme styles these inputs
    borderless with no room for a label above them.
    """

    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email'}),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Message'}),
    )
