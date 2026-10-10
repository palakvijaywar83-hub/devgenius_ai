from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css}".strip()
