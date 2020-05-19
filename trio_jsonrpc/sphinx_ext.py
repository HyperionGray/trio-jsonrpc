# type: ignore
"""
This module defines a Sphinx extension for Trio JSON-RPC methods and objects.
"""
from __future__ import annotations
from collections import defaultdict
from enum import Enum
from importlib import import_module
from inspect import Parameter, signature, Signature
import logging
import re
from textwrap import dedent
import typing

from docutils.statemachine import StringList
from sphinx import addnodes
from sphinx.directives import ObjectDescription, SphinxDirective
from sphinx.domains import Domain, Index
from sphinx.roles import XRefRole
from sphinx.util.docfields import Field, GroupedField, TypedField
from sphinx.util.docstrings import prepare_docstring
from sphinx.util.docutils import nodes, switch_source_input

if typing.TYPE_CHECKING:
    from sphinx.application import Sphinx
    from trio_jsonrpc import Dispatch


logger = logging.getLogger(__name__)
PARAM_RE = re.compile(r":param ([^:]+):(.*)")


def load_dispatch(location: str) -> Dispatch:
    """
    Location is a string like ``my.module.path::my_dispatch``. This function loads the
    module (e.g. ``my.module.path``) and returns the dispatch object in that module
    (e.g. ``my_dispatch``).

    :raises InvalidObjectLocation:
    """
    try:
        logger.debug("Load dispatch from %s", location)
        module_name, obj_name = location.strip().split(":")
        module = import_module(module_name)
        return getattr(module, obj_name)
    except (AttributeError, IndexError):
        raise Exception(
            "Object location must be a string containing a module and an object, i.e. "
            "`my.module.path:my_object`."
        )


class JsonRpcDispatch(SphinxDirective):
    """
    This directive defines how to load the Dispatch object. The object is stored in the
    Sphinx environment.
    """

    required_arguments = 1

    def run(self) -> typing.List[nodes.Node]:
        self.env.jsonrpc_dispatch = self.arguments[0]
        return []


class JsonRpcMethodCallStyle(Enum):
    BOTH = 0
    ARRAY = 1
    OBJECT = 2


class JsonRpcMethod(ObjectDescription):
    """ This directive is used for documenting JSON-RPC methods implemented by copying
    type annotations and docstrings from a Python handler function. """

    required_arguments = 1
    call_style: JsonRpcMethodCallStyle = JsonRpcMethodCallStyle.BOTH
    doc_field_types = [
        TypedField(
            "parameter",
            label="Parameters",
            names=("param",),  # All names need to be matched by PARAM_RE
            typerolename="obj",
            typenames=("paramtype",),
        ),
        Field("returnvalue", label="Returns", has_arg=False, names=("returns",)),
        Field(
            "returntype",
            label="Return Type",
            has_arg=False,
            names=("rtype",),
            bodyrolename="class",
        ),
        GroupedField("error", label="Errors", names=("error",),),
    ]
    __jsonrpc_method = None
    __inspect_sig = None
    __type_hints = None

    def add_target_and_index(self, name_cls, sig, signode):
        """ Create a target ID and add to the domain's list of methods. """
        signode["ids"].append(f"jsonrpc-method-{sig}")
        if "noindex" not in self.options:
            jsonrpc = self.env.get_domain("jsonrpc")
            jsonrpc.add_method(sig)

    def handle_signature(self, sig, signode):
        """ Generate the signature for the JSON-RPC method. """
        dispatch = load_dispatch(self.env.jsonrpc_dispatch)
        self.__jsonrpc_method = dispatch.get_handler(self.arguments[0])
        method_name = self.__jsonrpc_method.__name__
        self.__inspect_sig = signature(self.__jsonrpc_method)
        self.__type_hints = typing.get_type_hints(self.__jsonrpc_method)
        signode += [
            addnodes.desc_name(text=method_name),
            self._parse_params(),
            self._parse_return(),
        ]
        return method_name

    def before_content(self) -> None:
        """ Insert the docstring from the handler function. Insert any missing types
        into the docstring. """
        lines = [""]
        docstr = self.__jsonrpc_method.__doc__
        rtype_seen = False
        param_names = list(self.__type_hints.keys())[:-1]

        if docstr:
            lines.extend(prepare_docstring(docstr))

        # Add type information to any param that missing it
        for idx in range(len(lines)):
            line = lines[idx]
            match = PARAM_RE.match(line)
            if match:
                parts = match.group(1).split()
                param_name = parts[-1]
                param_names.remove(param_name)
                if len(parts) == 1:
                    type_ = self._annotation(self.__type_hints[param_name])
                    lines[idx] = ":param {} {}:{}".format(
                        type_, parts[0], match.group(2)
                    )
            elif line.startswith(":rtype:"):
                rtype_seen = True

        # Add any missing parameters
        for param_name in param_names:
            lines.insert(
                len(lines) - 1,
                ":param {} {}:".format(
                    self._annotation(self.__type_hints[param_name]), param_name
                ),
            )

        # Add return type if it's missing.
        if not rtype_seen:
            rtype = self._annotation(self.__type_hints["return"])
            lines.insert(len(lines) - 1, ":rtype: {}".format(rtype))
        print(lines)
        self.content += StringList(lines)

    def _parse_params(self) -> addnodes.desc_parameterlist:
        """ Convert the function's parameter list to a tree. """
        params = addnodes.desc_parameterlist()
        last_kind = None

        for param in self.__inspect_sig.parameters.values():
            if param.kind in (Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD):
                if self.call_style == JsonRpcMethodCallStyle.ARRAY:
                    raise Exception(
                        "A JSON-RPC method cannot contain both positional-only and "
                        "keyword-only arguments."
                    )
                else:
                    self.call_style = JsonRpcMethodCallStyle.OBJECT

            if param.kind in (Parameter.POSITIONAL_ONLY, Parameter.VAR_POSITIONAL):
                if self.call_style == JsonRpcMethodCallStyle.OBJECT:
                    raise Exception(
                        "A JSON-RPC method cannot contain both positional-only and "
                        "keyword-only arguments."
                    )
                else:
                    self.call_style = JsonRpcMethodCallStyle.ARRAY

            node = addnodes.desc_parameter()

            if param.annotation is not param.empty:
                ann = self._annotation(self.__type_hints[param.name])
                node += nodes.Text(f"{ann} ")

            node += addnodes.desc_sig_name("", param.name)

            if param.default is not param.empty:
                node += nodes.Text(f" [default {param.default}]")

            params += node

        return params

    def _parse_return(self) -> addnodes.desc_returns:
        """ Convert the function's return to a node. """
        if self.__inspect_sig.return_annotation is not self.__inspect_sig.empty:
            return addnodes.desc_returns(
                text=self._annotation(self.__type_hints["return"])
            )
        else:
            return addnodes.desc_returns(text="null")

    def _annotation(self, annotation):
        """ Convert a Python data type into a JSON-ish type name. """
        try:
            return {
                bool: "boolean",
                float: "float",
                int: "integer",
                list: "array",
                dict: "object",
                str: "string",
            }[annotation]
        except KeyError:
            logger.error("Cannot process annotation: %r", annotation)


class JsonRpcType(SphinxDirective):
    has_content = True

    def run(self):
        paragraph_node = nodes.paragraph(text=f"Hello type {self.content}")
        return [paragraph_node]


class JsonRpcIndex(Index):
    name = "index"
    localname = "JSON-RPC API Index"
    shortname = "Index"

    def generate(self, docnames=None):
        content = defaultdict(list)
        methods = sorted(self.domain.get_objects(), key=lambda m: m[0])
        for name, dispname, typ, docname, anchor, _ in methods:
            content[dispname[0].lower()].append(
                (dispname, 0, docname, anchor, docname, "", typ)
            )
        return sorted(content.items()), True


class JsonRpcDomain(Domain):
    name = "jsonrpc"
    label = "Trio JSON-RPC"
    roles = {
        "ref": XRefRole(),
    }
    directives = {
        "dispatch": JsonRpcDispatch,
        "method": JsonRpcMethod,
    }
    indices = {
        JsonRpcIndex,
    }
    initial_data: typing.Dict = {
        "objects": list(),
    }

    def add_method(self, signature):
        name = f"method.{signature}"
        anchor = f"method-{signature}"
        self.data["objects"].append(
            (name, signature, "Method", self.env.docname, anchor, 0)
        )

    def get_objects(self):
        for meth in self.data["objects"]:
            yield meth

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, countnode):
        match = [
            (docname, anchor)
            for name, sig, typ, docname, anchor, prio in self.get_objects()
            if sig == target
        ]
        if len(match) > 0:
            todocname = match[0][0]
            targ = match[0][1]
            return make_refnode(builder, fromdocname, todocname, targ, contnode, targ)
        else:
            logger.error("Cannot resolve xref: %s", target)
            return


def setup(app: Sphinx) -> typing.Dict[str, typing.Any]:
    app.add_domain(JsonRpcDomain)

    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
