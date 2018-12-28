from typing import Callable, Optional, Type

import mypy.types
from mypy.nodes import NameExpr, TypeInfo
from mypy.plugin import FunctionContext, Plugin

ATTR_FULL_NAME = 'pynamodb.attributes.Attribute'
NULL_ATTR_FULL_NAME = 'pynamodb.attributes._NullableAttribute'


class PynamodbPlugin(Plugin):
    def get_function_hook(self, fullname: str) -> Optional[Callable[[FunctionContext], mypy.types.Type]]:
        node = self.lookup_fully_qualified(fullname)
        if (
            node and
            isinstance(node.node, TypeInfo) and
            node.node.has_base(ATTR_FULL_NAME) and
            # TODO: any better way to tell apart instantiation from a function call?
            fullname == node.node.fullname()
        ):
            return _function_hook_callback


def _function_hook_callback(ctx: FunctionContext) -> mypy.types.Type:
    attr_type = ctx.default_return_type
    base_type = next(base for base in attr_type.type.bases
                     if base.type.fullname() == ATTR_FULL_NAME)
    try:
        (underlying_type,) = base_type.args
    except ValueError:
        ctx.api.fail(f'Unexpected number of type arguments to {ATTR_FULL_NAME}', ctx.context)
        return ctx.default_return_type

    # If initializer is passed null=True, wrap in _NullableAttribute
    # to make the underlying type optional
    for arg_name, arg_exprs in zip(ctx.callee_arg_names, ctx.args):
        if arg_name != 'null' or not arg_exprs:
            continue
        try:
            (arg_expr,) = arg_exprs
        except ValueError:
            ctx.api.fail("Unexpected number of expressions in 'null' argument", ctx.context)
            continue

        if isinstance(arg_expr, NameExpr) and arg_expr.fullname == 'builtins.True':
            return ctx.api.named_generic_type(NULL_ATTR_FULL_NAME, [
                attr_type,
                underlying_type,
            ])

    return ctx.default_return_type


def plugin(version: str) -> Type[PynamodbPlugin]:
    return PynamodbPlugin
