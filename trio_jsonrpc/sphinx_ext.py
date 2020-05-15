"""
This module defines a Sphinx extension for Trio JSON-RPC methods and objects.
"""
from __future__ import annotations
from collections import defaultdict
from enum import Enum
from importlib import import_module
from inspect import Parameter, signature, Signature
import logging
import typing

from docutils.statemachine import StringList
from sphinx import addnodes
from sphinx.directives import ObjectDescription, SphinxDirective
from sphinx.domains import Domain, Index
from sphinx.roles import XRefRole
from sphinx.util.docstrings import prepare_docstring
from sphinx.util.docutils import nodes


if typing.TYPE_CHECKING:
    from sphinx.application import Sphinx
    from trio_jsonrpc import Dispatch


logger = logging.getLogger(__name__)


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


class TrioJsonRpcDispatch(SphinxDirective):
    """
    This directive defines how to load the Dispatch object. The object is stored in the
    Sphinx environment.
    """

    required_arguments = 1

    def run(self) -> typing.List[nodes.Node]:
        self.env.trio_jsonrpc_dispatch = self.arguments[0]
        return []


class TrioJsonRpcMethodCallStyle(Enum):
    BOTH = 0
    ARRAY = 1
    OBJECT = 2


class TrioJsonRpcMethod(ObjectDescription):
    required_arguments = 1
    call_style: TrioJsonRpcMethodCallStyle = TrioJsonRpcMethodCallStyle.BOTH
    __trio_jsonrpc_method = None

    def add_target_and_index(self, name_cls, sig, signode):
        signode["ids"].append(f"trio-jsonrpc-method-{sig}")
        if "noindex" not in self.options:
            trio_jsonrpc = self.env.get_domain("trio-jsonrpc")
            trio_jsonrpc.add_method(sig)

    def handle_signature(self, sig, signode):
        """ Generate the signature for the JSON-RPC method. """
        dispatch = load_dispatch(self.env.trio_jsonrpc_dispatch)
        self.__trio_jsonrpc_method = dispatch.get_handler(self.arguments[0])
        method_name = self.__trio_jsonrpc_method.__name__
        isig = signature(self.__trio_jsonrpc_method)
        signode += [
            addnodes.desc_name(text=method_name),
            self._parse_params(isig),
            self._parse_return(isig),
        ]
        return method_name

    def before_content(self) -> None:
        """ Insert docstring from the handler function. """
        docstr = self.__trio_jsonrpc_method.__doc__
        if docstr:
            self.content = StringList(prepare_docstring(docstr))

    # def transform_content(self, contentnode: addnodes.desc_content) -> None:
    #     print("content", type(self.content), repr(self.content))
    #     for line in prepare_docstring(self.__trio_jsonrpc_method.__doc__):
    #         contentnode += nodes.Text(line)
    #     return contentnode

    def _parse_params(self, isig: Signature) -> addnodes.desc_parameterlist:
        params = addnodes.desc_parameterlist()
        last_kind = None

        for param in isig.parameters.values():
            if param.kind in (Parameter.KEYWORD_ONLY, Parameter.VAR_KEYWORD):
                if self.call_style == TrioJsonRpcMethodCallStyle.ARRAY:
                    raise Exception(
                        "A JSON-RPC method cannot contain both positional-only and "
                        "keyword-only arguments."
                    )
                else:
                    self.call_style = TrioJsonRpcMethodCallStyle.OBJECT

            if param.kind in (Parameter.POSITIONAL_ONLY, Parameter.VAR_POSITIONAL):
                if self.call_style == TrioJsonRpcMethodCallStyle.OBJECT:
                    raise Exception(
                        "A JSON-RPC method cannot contain both positional-only and "
                        "keyword-only arguments."
                    )
                else:
                    self.call_style = TrioJsonRpcMethodCallStyle.ARRAY

            node = addnodes.desc_parameter()

            if param.annotation is not param.empty:
                print(f"param.annotation {type(param.annotation)}")
                ann = self._annotation(param.annotation)
                node += nodes.Text(f"{ann} ")

            node += addnodes.desc_sig_name("", param.name)

            if param.default is not param.empty:
                node += nodes.Text(f" [default {param.default}]")

            params += node

        return params

    def _parse_return(self, isig: Signature) -> addnodes.desc_returns:
        if isig.return_annotation is not isig.empty:
            return addnodes.desc_returns(text=self._annotation(isig.return_annotation))
        else:
            return addnodes.desc_returns(text="null")

    def _annotation(self, annotation):
        if isinstance(annotation, str):
            return {
                "bool": "boolean",
                "float": "float",
                "int": "integer",
                "list": "array",
                "dict": "object",
                "str": "string",
            }[annotation]
        else:
            raise NotImplementedError()


class TrioJsonRpcType(SphinxDirective):
    has_content = True

    def run(self):
        paragraph_node = nodes.paragraph(text=f"Hello type {self.content}")
        return [paragraph_node]


class TrioJsonRpcIndex(Index):
    name = "index"
    localname = "Trio JSON-RPC Index"
    shortname = "Index"

    def generate(self, docnames=None):
        content = defaultdict(list)
        methods = sorted(self.domain.get_objects(), key=lambda m: m[0])
        for name, dispname, typ, docname, anchor, _ in methods:
            content[dispname[0].lower()].append(
                (dispname, 0, docname, anchor, docname, "", typ)
            )
        return sorted(content.items()), True


class TrioJsonRpcDomain(Domain):
    name = "trio-jsonrpc"
    label = "Trio JSON-RPC"
    roles = {
        "ref": XRefRole(),
    }
    directives = {
        "dispatch": TrioJsonRpcDispatch,
        "method": TrioJsonRpcMethod,
    }
    indices = {
        TrioJsonRpcIndex,
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
    app.add_domain(TrioJsonRpcDomain)

    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
