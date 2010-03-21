from pkg_resources import resource_filename

import colander
import peppercorn

from deform import template

class Widget(object):
    error = None
    default = None
    hidden = False

    def _make_default_renderer(self):
        defaultdir = resource_filename('deform', 'templates') + '/'
        loader = template.ChameleonZPTTemplateLoader([defaultdir])

        def renderer(template, **kw):
            return loader.load(template)(**kw)

        return renderer

    def __init__(self, schema, renderer=None):
        self.schema = schema
        if renderer is None:
            renderer = self._make_default_renderer()
        self.renderer = renderer
        self.name = self.schema.name
        self.title = self.schema.title
        self.description = self.schema.description
        self.required = self.schema.required
        self.widgets = []
        if not self.schema.required:
            self.default = self.schema.serialize(self.schema.default)
        for node in schema.nodes:
            widget_type = getattr(node.typ, 'widget_type', TextInputWidget)
            widget = widget_type(node, renderer=renderer)
            self.widgets.append(widget)

    def serialize(self, cstruct=None):
        """
        Serialize a cstruct value to a form rendering and return the
        rendering.  The result of this method should always be a
        string (containing HTML).
        """
        template = getattr(self, 'template', None)
        if template is not None:
            return self.renderer(self.template, widget=self, cstruct=cstruct)
        raise NotImplementedError

    def deserialize(self, pstruct=None):
        """
        Deserialize a pstruct value to a cstruct value and return the
        cstruct value.
        """
        raise NotImplementedError

    def validate(self, fields):
        pstruct = peppercorn.parse(fields)
        cstruct = self.deserialize(pstruct)
        try:
            return self.schema.deserialize(cstruct)
        except colander.Invalid, e:
            self.handle_error(e)
            raise

    def handle_error(self, error):
        self.error = error
        # XXX exponential time
        for e in error.children:
            for widget in self.widgets:
                if e.node is widget.schema:
                    widget.handle_error(e)

class TextInputWidget(Widget):
    def serialize(self, cstruct=None):
        name = self.schema.name
        if cstruct is None:
            cstruct = ''
        return '<input type="text" name="%s" value="%s"/>' % (name, cstruct)

    def deserialize(self, pstruct):
        if pstruct is None:
            pstruct = self.default
        if pstruct is None:
            pstruct = ''
        return pstruct

class CheckboxWidget(Widget):
    def serialize(self, cstruct=None):
        name = self.schema.name
        if cstruct == 'true':
            return '<input type="checkbox" name="%s" checked="true"/>' % name
        else:
            return '<input type="checkbox" name="%s"/>' % name

    def deserialize(self, pstruct):
        if pstruct is None:
            pstruct = self.default
        if pstruct == 'true':
            return 'true'
        return 'false'

class MappingWidget(Widget):
    def serialize(self, cstruct=None):
        if cstruct is None:
            cstruct = {}
        out = []
        out.append('<input type="hidden" name="__start__" '
                   'value="%s:mapping">' % self.schema.name)
        for widget in self.widgets:
            name = widget.name
            out.append(widget.serialize(cstruct.get(name)))
        out.append('<input type="hidden" name="__end__" '
                   'value="%s:mapping">' % self.schema.name)
        return '\n'.join(out)

    def deserialize(self, pstruct):

        result = {}

        if pstruct is None:
            pstruct = {}

        for num, widget in enumerate(self.widgets):
            name = widget.name
            substruct = pstruct.get(name)
            result[name] = widget.deserialize(substruct)

        return result

class SequenceWidget(Widget):
    def serialize(self, cstruct=None):
        out = []

        if cstruct is None:
            cstruct = []

        out.append('<input type="hidden" name="__start__" '
                   'value="%s:sequence">' % self.schema.name)
        for item in cstruct:
            widget = self.widgets[0]
            out.append(widget.serialize(item))
        out.append('<input type="hidden" name="__end__" '
                   'value="%s:sequence">' % self.schema.name)
        return '\n'.join(out)

    def deserialize(self, pstruct):
        result = []

        if pstruct is None:
            pstruct = []

        for num, substruct in enumerate(pstruct):
            val = self.widgets[0].deserialize(substruct)
            result.append(val)

        return result

class Button(object):
    def __init__(self, name='', title=None, value=None):
        if title is None:
            title = name
        if value is None:
            value = name
        self.name = name
        self.title = title
        self.value = value

class Form(MappingWidget):
    template = 'form.html'

    def __init__(self, schema, renderer=None, action='.', method='POST',
                 buttons=()):
        self.action = action
        self.method = method
        self.buttons = []
        for button in buttons:
            if isinstance(button, basestring):
                button = Button(button)
            self.buttons.append(button)
        MappingWidget.__init__(self, schema, renderer=renderer)

    def serialize(self, cstruct=None):
        """
        Serialize a cstruct value to a form rendering and return the
        rendering.  The result of this method should always be a
        string (containing HTML).
        """
        if cstruct is None:
            cstruct = {}
        return self.renderer(self.template, widget=self, cstruct=cstruct)